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
                "-w",
                "-x",
                "-q",
                "-s",
                "-o",
            },
            valued={"-e", "-f"},
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
    if fixed:
        pattern = re.escape(pattern)
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
    any_match = False
    for label, content in targets:
        lines = content.splitlines()
        matched_lines: list[tuple[int, str]] = []
        for i, line in enumerate(lines, 1):
            m = rx.search(line)
            if (m is not None) ^ invert:
                matched_lines.append((i, line))
        if matched_lines:
            any_match = True
        if quiet:
            continue
        if list_files:
            if matched_lines:
                write_out(io_ctx, label + "\n")
            continue
        if count_only:
            prefix = f"{label}:" if show_filename else ""
            write_out(io_ctx, f"{prefix}{len(matched_lines)}\n")
            continue
        for lineno, line in matched_lines:
            prefix_parts: list[str] = []
            if show_filename:
                prefix_parts.append(label)
            if show_lineno:
                prefix_parts.append(str(lineno))
            prefix = ":".join(prefix_parts)
            if prefix:
                write_out(io_ctx, prefix + ":" + line + "\n")
            else:
                write_out(io_ctx, line + "\n")
    return 0 if any_match else 1


__all__ = ["cmd_grep"]
