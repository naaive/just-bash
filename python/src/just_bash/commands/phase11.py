"""Phase-11 commands: directory tree, modern command aliases (rg, fd, bat,
sd, ag, fzf, hexyl, xargs0), CSV/TSV translators, and small system-info
helpers (getconf, locale, iconv)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import read_input, write_err, write_out
from just_bash.commands.basic import cmd_cat
from just_bash.commands.find_cmd import cmd_find
from just_bash.commands.grep_cmd import cmd_grep
from just_bash.commands.more import cmd_hexdump
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# tree - print a directory tree
# ---------------------------------------------------------------------------


def cmd_tree(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``tree [-L N] [-a] [PATH]`` - render a directory hierarchy.

    Supports ``-L N`` (max depth), ``-a`` (include dotfiles), and a single
    path argument. Output format mimics ``tree`` (ASCII connectors and a
    ``N directories, M files`` summary).
    """
    args = argv[1:]
    max_depth: int | None = None
    show_hidden = False
    paths: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-L" and i + 1 < len(args):
            try:
                max_depth = int(args[i + 1])
            except ValueError:
                write_err(io_ctx, f"tree: invalid level: {args[i + 1]}\n")
                return 2
            i += 2
            continue
        if a == "-a":
            show_hidden = True
            i += 1
            continue
        if a.startswith("-"):
            i += 1
            continue
        paths.append(a)
        i += 1
    if not paths:
        paths = ["."]
    rc = 0
    dir_count = 0
    file_count = 0

    def render(root: str, prefix: str, depth: int) -> None:
        nonlocal dir_count, file_count
        if max_depth is not None and depth > max_depth:
            return
        try:
            entries = sorted(interp.fs.listdir(root))
        except FsError as e:
            write_err(io_ctx, f"tree: {root}: {e}\n")
            return
        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]
        for idx, name in enumerate(entries):
            full = root.rstrip("/") + "/" + name if root != "/" else "/" + name
            last = idx == len(entries) - 1
            connector = "`-- " if last else "|-- "
            write_out(io_ctx, f"{prefix}{connector}{name}\n")
            if interp.fs.is_dir(full):
                dir_count += 1
                next_prefix = prefix + ("    " if last else "|   ")
                render(full, next_prefix, depth + 1)
            else:
                file_count += 1

    for p in paths:
        write_out(io_ctx, f"{p}\n")
        try:
            interp.fs.stat(p)
        except FsError as e:
            write_err(io_ctx, f"tree: {p}: {e}\n")
            rc = 1
            continue
        if interp.fs.is_dir(p):
            render(p, "", 1)
    write_out(io_ctx, f"\n{dir_count} directories, {file_count} files\n")
    return rc


# ---------------------------------------------------------------------------
# rg - alias for ``grep -r --color=never``
# ---------------------------------------------------------------------------


def cmd_rg(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """Lightweight ripgrep alias backed by ``grep -r``."""
    args = argv[1:]
    fwd: list[str] = ["grep", "-r"]
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("--no-heading", "--color=never", "-S", "--smart-case"):
            i += 1
            continue
        if a == "-n":
            fwd.append("-n")
            i += 1
            continue
        if a == "-i":
            fwd.append("-i")
            i += 1
            continue
        fwd.append(a)
        i += 1
    return cmd_grep(interp, fwd, io_ctx)


# ---------------------------------------------------------------------------
# ag - the silver searcher: also a recursive grep alias
# ---------------------------------------------------------------------------


def cmd_ag(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_rg(interp, argv, io_ctx)


# ---------------------------------------------------------------------------
# fd - find by name with friendly defaults
# ---------------------------------------------------------------------------


def cmd_fd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``fd PATTERN [PATH]`` - find files matching the pattern.

    Translates to ``find PATH -name '*PATTERN*'``. ``-t f`` / ``-t d`` map to
    ``find -type f`` / ``-type d``.
    """
    args = argv[1:]
    pattern: str | None = None
    path = "."
    type_arg: str | None = None
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-t", "--type") and i + 1 < len(args):
            kind = args[i + 1]
            type_arg = "f" if kind in ("f", "file") else "d" if kind in ("d", "dir") else None
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        if pattern is None:
            pattern = a
        else:
            path = a
        i += 1
    fwd: list[str] = ["find", path]
    if pattern is not None:
        fwd.extend(["-name", f"*{pattern}*"])
    if type_arg is not None:
        fwd.extend(["-type", type_arg])
    return cmd_find(interp, fwd, io_ctx)


# ---------------------------------------------------------------------------
# fdfind - Debian's name for fd
# ---------------------------------------------------------------------------


def cmd_fdfind(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_fd(interp, argv, io_ctx)


# ---------------------------------------------------------------------------
# bat - cat with line numbers (alias for ``cat -n``)
# ---------------------------------------------------------------------------


def cmd_bat(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    fwd = ["cat", "-n", *argv[1:]]
    return cmd_cat(interp, fwd, io_ctx)


# ---------------------------------------------------------------------------
# sd - simple find/replace (literal strings, not regex)
# ---------------------------------------------------------------------------


def cmd_sd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``sd FIND REPLACE [FILE...]`` - literal substitution."""
    args = argv[1:]
    if len(args) < 2:
        write_err(io_ctx, b"sd: usage: sd FIND REPLACE [FILE...]\n")
        return 2
    find = args[0]
    replace = args[1]
    paths = args[2:]
    if not paths:
        data = io_ctx.stdin.decode("utf-8", errors="replace")
        write_out(io_ctx, data.replace(find, replace))
        return 0
    rc = 0
    for path in paths:
        try:
            data = interp.fs.read_file(path).decode("utf-8", errors="replace")
        except FsError as e:
            write_err(io_ctx, f"sd: {e}\n")
            rc = 1
            continue
        interp.fs.write_file(path, data.replace(find, replace).encode("utf-8"))
    return rc


# ---------------------------------------------------------------------------
# fzf - fuzzy finder (deterministic stub: prints first matching line)
# ---------------------------------------------------------------------------


def cmd_fzf(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """Sandbox-safe ``fzf`` stub: when ``-f QUERY`` is given, emits matching
    input lines (substring match); otherwise emits the first input line so
    scripts that pipe into ``fzf`` for selection produce deterministic
    results."""
    args = argv[1:]
    query: str | None = None
    i = 0
    while i < len(args):
        if args[i] in ("-f", "--filter") and i + 1 < len(args):
            query = args[i + 1]
            i += 2
            continue
        i += 1
    lines = io_ctx.stdin.decode("utf-8", errors="replace").splitlines()
    if query is not None:
        out = [line for line in lines if query in line]
    elif lines:
        out = [lines[0]]
    else:
        out = []
    if out:
        write_out(io_ctx, "\n".join(out) + "\n")
    return 0 if out else 1


# ---------------------------------------------------------------------------
# hexyl - alias for ``hexdump -C``
# ---------------------------------------------------------------------------


def cmd_hexyl(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_hexdump(interp, ["hexdump", "-C", *argv[1:]], io_ctx)


# ---------------------------------------------------------------------------
# CSV / TSV translators
# ---------------------------------------------------------------------------


def cmd_csv2tsv(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    out_lines: list[str] = []
    for line in text.splitlines():
        out_lines.append(_split_csv_row(line))
    suffix = "\n" if text.endswith("\n") else ""
    write_out(io_ctx, "\n".join(out_lines) + suffix)
    return rc


def _split_csv_row(line: str) -> str:
    """Split a CSV row honouring double-quoted fields, then join with TAB."""
    fields: list[str] = []
    buf: list[str] = []
    in_quotes = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == '"':
            if in_quotes and i + 1 < len(line) and line[i + 1] == '"':
                buf.append('"')
                i += 2
                continue
            in_quotes = not in_quotes
            i += 1
            continue
        if ch == "," and not in_quotes:
            fields.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    fields.append("".join(buf))
    return "\t".join(fields)


def cmd_tsv2csv(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    out_lines: list[str] = []
    for line in text.splitlines():
        cells = line.split("\t")
        out_lines.append(",".join(_quote_csv_field(c) for c in cells))
    suffix = "\n" if text.endswith("\n") else ""
    write_out(io_ctx, "\n".join(out_lines) + suffix)
    return rc


def _quote_csv_field(field: str) -> str:
    if any(c in field for c in (",", '"', "\n")):
        return '"' + field.replace('"', '""') + '"'
    return field


# ---------------------------------------------------------------------------
# xargs0 - alias for ``xargs -0``
# ---------------------------------------------------------------------------


def cmd_xargs0(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    from just_bash.commands.extra import cmd_xargs

    return cmd_xargs(interp, ["xargs", "-0", *argv[1:]], io_ctx)


# ---------------------------------------------------------------------------
# getconf - canned table of common system limits
# ---------------------------------------------------------------------------


_GETCONF_TABLE: dict[str, str] = {
    "PAGE_SIZE": "4096",
    "PAGESIZE": "4096",
    "_NPROCESSORS_ONLN": "4",
    "_NPROCESSORS_CONF": "4",
    "ARG_MAX": "2097152",
    "OPEN_MAX": "1024",
    "LINE_MAX": "2048",
    "NAME_MAX": "255",
    "PATH_MAX": "4096",
    "LONG_BIT": "64",
    "INT_MAX": "2147483647",
    "LONG_MAX": "9223372036854775807",
    "_POSIX_VERSION": "200809",
    "CLK_TCK": "100",
}


def cmd_getconf(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] == "-a":
        for k, v in _GETCONF_TABLE.items():
            write_out(io_ctx, f"{k}                       {v}\n")
        return 0
    if not args:
        write_err(io_ctx, b"getconf: usage: getconf NAME | -a\n")
        return 2
    name = args[0]
    val = _GETCONF_TABLE.get(name)
    if val is None:
        write_err(io_ctx, f"getconf: Unrecognized variable '{name}'\n")
        return 1
    write_out(io_ctx, f"{val}\n")
    return 0


# ---------------------------------------------------------------------------
# locale - canned C-locale info
# ---------------------------------------------------------------------------


def cmd_locale(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        keys = (
            "LANG",
            "LC_CTYPE",
            "LC_NUMERIC",
            "LC_TIME",
            "LC_COLLATE",
            "LC_MONETARY",
            "LC_MESSAGES",
            "LC_ALL",
        )
        for k in keys:
            v = interp.env.get(k) or "C"
            if k != "LANG" and k != "LC_ALL" and not interp.env.get(k):
                write_out(io_ctx, f'{k}="C"\n')
            else:
                write_out(io_ctx, f"{k}={v}\n")
        return 0
    if args[0] == "-a":
        for v in ("C", "C.UTF-8", "POSIX", "en_US.UTF-8"):
            write_out(io_ctx, f"{v}\n")
        return 0
    return 0


# ---------------------------------------------------------------------------
# iconv - charset conversion (limited: utf-8 ↔ ascii is identity for ASCII)
# ---------------------------------------------------------------------------


def cmd_iconv(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``iconv -f FROM -t TO [FILE]`` - conversion between common charsets."""
    args = argv[1:]
    from_enc = "utf-8"
    to_enc = "utf-8"
    paths: list[str] = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in ("-f", "--from-code") and i + 1 < len(args):
            from_enc = args[i + 1].lower()
            i += 2
            continue
        if a in ("-t", "--to-code") and i + 1 < len(args):
            to_enc = args[i + 1].lower()
            i += 2
            continue
        if a == "-c":
            i += 1
            continue
        paths.append(a)
        i += 1
    data, rc = read_input(interp, io_ctx, paths)
    try:
        text = data.decode(from_enc, errors="replace")
    except LookupError:
        write_err(io_ctx, f"iconv: unknown encoding: {from_enc}\n")
        return 1
    try:
        out = text.encode(to_enc, errors="replace")
    except LookupError:
        write_err(io_ctx, f"iconv: unknown encoding: {to_enc}\n")
        return 1
    write_out(io_ctx, out)
    return rc


# ---------------------------------------------------------------------------
# yq - tiny YAML (one-key) lookup. We don't ship a real YAML parser; we
# extract scalar values for ``yq '.key'`` style queries on simple inputs.
# ---------------------------------------------------------------------------


def cmd_yq(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    query = args[0] if args else "."
    paths = args[1:]
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    if query == "." or query == "":
        write_out(io_ctx, text if text.endswith("\n") else text + "\n")
        return rc
    if not query.startswith("."):
        write_err(io_ctx, b"yq: only .key style queries are supported\n")
        return 2
    key = query[1:]
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith(f"{key}:"):
            value = stripped[len(key) + 1 :].strip()
            write_out(io_ctx, f"{value}\n")
            return rc
    write_out(io_ctx, "null\n")
    return rc


__all__ = [
    "cmd_ag",
    "cmd_bat",
    "cmd_csv2tsv",
    "cmd_fd",
    "cmd_fdfind",
    "cmd_fzf",
    "cmd_getconf",
    "cmd_hexyl",
    "cmd_iconv",
    "cmd_locale",
    "cmd_rg",
    "cmd_sd",
    "cmd_tree",
    "cmd_tsv2csv",
    "cmd_xargs0",
    "cmd_yq",
]
