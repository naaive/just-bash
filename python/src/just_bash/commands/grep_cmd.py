"""``grep`` - print lines matching a pattern.

Supports a useful subset:
  - ``-i`` case-insensitive
  - ``-v`` invert
  - ``-n`` line numbers
  - ``-c`` count only
  - ``-l`` files-with-matches
  - ``-H`` / ``-h`` filename prefix control
  - ``-r`` recursive
  - ``-E`` extended regex (default on - we always use Python ``re``)
  - ``-F`` fixed string
  - ``-w`` word match
  - ``-x`` line match
  - ``-q`` quiet
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, write_err, write_out
from just_bash.fs.vfs import Directory, FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def cmd_grep(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, positional = parse_flags(
            argv,
            boolean={
                "-i",
                "-v",
                "-n",
                "-c",
                "-l",
                "-H",
                "-h",
                "-r",
                "-R",
                "-E",
                "-F",
                "-P",
                "-w",
                "-x",
                "-q",
                "-s",
                "-o",
            },
            valued={"-e", "-f", "-A", "-B", "-C"},
        )
    except ValueError as e:
        write_err(io_ctx, f"grep: {e}\n")
        return 2
    pattern: str | None = None
    files: list[str] = []
    if "-e" in flags:
        pattern = str(flags["-e"])
        files = positional
    elif positional:
        pattern = positional[0]
        files = positional[1:]
    if pattern is None:
        write_err(io_ctx, b"grep: missing pattern\n")
        return 2
    fixed = bool(flags.get("-F"))
    extended = bool(flags.get("-E") or flags.get("-P"))
    if fixed:
        pattern = re.escape(pattern)
    elif not extended:
        # Plain ``grep`` is BRE: ``\(``/``\)``/``\|``/``\+``/``\?``/``\{`` are
        # the metacharacters; bare ``+``/``?``/etc. are literal. Translate to
        # Python ``re`` (which is ERE/Perl flavour).
        pattern = _bre_to_python(pattern)
    if flags.get("-w"):
        pattern = r"\b(?:" + pattern + r")\b"
    if flags.get("-x"):
        pattern = r"\A(?:" + pattern + r")\Z"
    re_flags = re.IGNORECASE if flags.get("-i") else 0
    try:
        rx = re.compile(pattern, re_flags)
    except re.error as e:
        write_err(io_ctx, f"grep: invalid pattern: {e}\n")
        return 2
    invert = bool(flags.get("-v"))
    show_lineno = bool(flags.get("-n"))
    count_only = bool(flags.get("-c"))
    list_files = bool(flags.get("-l"))
    quiet = bool(flags.get("-q"))
    recursive = bool(flags.get("-r") or flags.get("-R"))
    show_filename = flags.get("-H") or (len(files) > 1 and not flags.get("-h"))

    targets: list[tuple[str, str]] = []  # (label, content)
    if not files:
        targets.append(("(stdin)", io_ctx.stdin.decode("utf-8", errors="replace")))
        show_filename = bool(flags.get("-H"))
    else:
        for f in files:
            if recursive:
                try:
                    node = interp.fs.stat(f)
                except FsError as e:
                    if not flags.get("-s"):
                        write_err(io_ctx, f"grep: {e}\n")
                    continue
                if isinstance(node, Directory):
                    for dirpath, _dirs, fnames in interp.fs.walk(f):
                        for name in fnames:
                            full = dirpath.rstrip("/") + "/" + name
                            try:
                                content = interp.fs.read_text(full)
                            except FsError:
                                continue
                            targets.append((full, content))
                    continue
                try:
                    targets.append((f, interp.fs.read_text(f)))
                except FsError as e:
                    if not flags.get("-s"):
                        write_err(io_ctx, f"grep: {e}\n")
            else:
                try:
                    targets.append((f, interp.fs.read_text(f)))
                except FsError as e:
                    if not flags.get("-s"):
                        write_err(io_ctx, f"grep: {e}\n")
        if len(targets) > 1:
            show_filename = not flags.get("-h")
    only_matching = bool(flags.get("-o"))
    after = int(flags.get("-A", flags.get("-C", 0)) or 0)
    before = int(flags.get("-B", flags.get("-C", 0)) or 0)
    any_match = False
    for label, content in targets:
        lines = content.splitlines()
        matched_idx: list[int] = []
        match_objs: dict[int, re.Match[str]] = {}
        for i, line in enumerate(lines, 1):
            m = rx.search(line)
            if (m is not None) ^ invert:
                matched_idx.append(i)
                if m is not None:
                    match_objs[i] = m
        if matched_idx:
            any_match = True
        if quiet:
            continue
        if list_files:
            if matched_idx:
                write_out(io_ctx, label + "\n")
            continue
        if count_only:
            prefix = f"{label}:" if show_filename else ""
            write_out(io_ctx, f"{prefix}{len(matched_idx)}\n")
            continue
        # ``-o`` mode: print every non-overlapping match on its own line.
        if only_matching:
            for i, line in enumerate(lines, 1):
                for m in rx.finditer(line):
                    prefix_parts: list[str] = []
                    if show_filename:
                        prefix_parts.append(label)
                    if show_lineno:
                        prefix_parts.append(str(i))
                    prefix = ":".join(prefix_parts)
                    if prefix:
                        write_out(io_ctx, prefix + ":" + m.group(0) + "\n")
                    else:
                        write_out(io_ctx, m.group(0) + "\n")
            continue
        # Compute the union of context windows around matched lines.
        emit_set: set[int] = set()
        for idx in matched_idx:
            for j in range(max(1, idx - before), min(len(lines), idx + after) + 1):
                emit_set.add(j)
        prev_emitted = 0
        for i, line in enumerate(lines, 1):
            if i not in emit_set:
                continue
            sep = "-" if i not in match_objs else ":"
            if (after or before) and prev_emitted and i - prev_emitted > 1:
                write_out(io_ctx, "--\n")
            prev_emitted = i
            prefix_parts: list[str] = []
            if show_filename:
                prefix_parts.append(label)
            if show_lineno:
                prefix_parts.append(str(i))
            prefix = sep.join(prefix_parts) if (after or before) else ":".join(prefix_parts)
            if prefix:
                write_out(io_ctx, prefix + sep + line + "\n")
            else:
                write_out(io_ctx, line + "\n")
    return 0 if any_match else 1


def _bre_to_python(pat: str) -> str:
    """Translate ``grep`` BRE (default) into Python regex.

    In BRE: ``\\(``/``\\)``/``\\|``/``\\+``/``\\?``/``\\{`` are metacharacters,
    while bare ``(``/``)``/``|``/``+``/``?``/``{`` are literal. Python ``re``
    uses the opposite convention.
    """
    out: list[str] = []
    i = 0
    while i < len(pat):
        ch = pat[i]
        if ch == "\\" and i + 1 < len(pat):
            nxt = pat[i + 1]
            if nxt in "(){}|+?":
                out.append(nxt)
                i += 2
                continue
            out.append(ch)
            out.append(nxt)
            i += 2
            continue
        if ch in "(){}|+?":
            out.append("\\" + ch)
            i += 1
            continue
        if ch == "$" and i + 1 < len(pat):
            out.append(r"\$")
            i += 1
            continue
        if ch == "^" and i > 0:
            out.append(r"\^")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


__all__ = ["cmd_grep"]
