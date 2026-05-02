"""Phase-4 commands: cmp, fold, expand, unexpand, mktemp, getopt, dd, cksum,
true, false (registered as commands too), pushd/popd/dirs (builtins),
alias/unalias/shopt/time (builtins).
"""

from __future__ import annotations

import binascii
import zlib
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# cmp
# ---------------------------------------------------------------------------


def cmd_cmp(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-s", "-l"})
    except ValueError as e:
        write_err(io_ctx, f"cmp: {e}\n")
        return 2
    if len(paths) != 2:
        write_err(io_ctx, b"cmp: expected 2 file operands\n")
        return 2
    try:
        a = interp.fs.read_file(paths[0])
        b = interp.fs.read_file(paths[1])
    except FsError as e:
        write_err(io_ctx, f"cmp: {e}\n")
        return 2
    if a == b:
        return 0
    if not flags.get("-s"):
        for i, (x, y) in enumerate(zip(a, b, strict=False), start=1):
            if x != y:
                line = a[:i].count(b"\n") + 1
                write_out(
                    io_ctx,
                    f"{paths[0]} {paths[1]} differ: byte {i}, line {line}\n",
                )
                break
        else:
            shorter = paths[0] if len(a) < len(b) else paths[1]
            write_out(io_ctx, f"cmp: EOF on {shorter}\n")
    return 1


# ---------------------------------------------------------------------------
# fold
# ---------------------------------------------------------------------------


def cmd_fold(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-w"}, boolean={"-s", "-b"})
    except ValueError as e:
        write_err(io_ctx, f"fold: {e}\n")
        return 2
    width = int(flags.get("-w", 80))
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    out: list[str] = []
    for line in text.split("\n"):
        if not line:
            out.append("")
            continue
        for i in range(0, len(line), width):
            out.append(line[i : i + width])
    write_out(io_ctx, "\n".join(out))
    return rc


# ---------------------------------------------------------------------------
# expand / unexpand
# ---------------------------------------------------------------------------


def cmd_expand(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-t"}, boolean={"-i"})
    except ValueError as e:
        write_err(io_ctx, f"expand: {e}\n")
        return 2
    tab = int(flags.get("-t", 8))
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    write_out(io_ctx, text.expandtabs(tab))
    return rc


def cmd_unexpand(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-t"}, boolean={"-a"})
    except ValueError as e:
        write_err(io_ctx, f"unexpand: {e}\n")
        return 2
    tab = int(flags.get("-t", 8))
    all_runs = bool(flags.get("-a"))
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    out: list[str] = []
    for line in text.split("\n"):
        out.append(_unexpand_line(line, tab, all_runs=all_runs))
    write_out(io_ctx, "\n".join(out))
    return rc


def _unexpand_line(line: str, tab: int, *, all_runs: bool) -> str:
    """Replace runs of spaces with tabs at column boundaries."""
    if not all_runs:
        # Default: only the leading-whitespace run.
        i = 0
        while i < len(line) and line[i] in " \t":
            i += 1
        prefix = line[:i]
        rest = line[i:]
        col = 0
        out: list[str] = []
        for ch in prefix:
            if ch == "\t":
                col = (col // tab + 1) * tab
                out.append("\t")
                continue
            col += 1
            out.append(ch)
        # Re-collapse expanded run back into tabs.
        expanded = "".join(out).expandtabs(tab)
        compacted: list[str] = []
        col = 0
        i = 0
        while i < len(expanded):
            if expanded[i] == " ":
                next_tab = (col // tab + 1) * tab
                run = next_tab - col
                if i + run <= len(expanded) and expanded[i : i + run].count(" ") == run:
                    compacted.append("\t")
                    col = next_tab
                    i += run
                    continue
            compacted.append(expanded[i])
            col += 1
            i += 1
        return "".join(compacted) + rest
    # ``-a``: collapse anywhere on the line.
    out_a: list[str] = []
    col = 0
    i = 0
    while i < len(line):
        if line[i] == " ":
            run_len = 0
            while i + run_len < len(line) and line[i + run_len] == " ":
                run_len += 1
            # Walk the run and pack into tabs at column boundaries.
            end = i + run_len
            while i < end:
                next_tab = (col // tab + 1) * tab
                gap = next_tab - col
                if gap <= end - i:
                    out_a.append("\t")
                    col = next_tab
                    i += gap
                else:
                    out_a.append(" " * (end - i))
                    col += end - i
                    i = end
            continue
        out_a.append(line[i])
        col += 1
        i += 1
    return "".join(out_a)


# ---------------------------------------------------------------------------
# mktemp
# ---------------------------------------------------------------------------


_MKTEMP_COUNTER = [0]


def cmd_mktemp(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, args = parse_flags(argv, boolean={"-d", "--directory"})
    except ValueError as e:
        write_err(io_ctx, f"mktemp: {e}\n")
        return 2
    template = args[0] if args else "/tmp/tmp.XXXXXX"
    if "X" not in template:
        template += ".XXXXXX"
    _MKTEMP_COUNTER[0] += 1
    rand = f"{_MKTEMP_COUNTER[0]:06d}"
    # Replace trailing run of X's with deterministic chars.
    result = list(template)
    j = len(result) - 1
    pos = len(rand) - 1
    while j >= 0 and result[j] == "X" and pos >= 0:
        result[j] = rand[pos]
        j -= 1
        pos -= 1
    path = "".join(result)
    parent = path.rsplit("/", 1)[0] if "/" in path else ""
    if parent:
        import contextlib

        with contextlib.suppress(FsError):
            interp.fs.mkdir(parent, parents=True, exist_ok=True)
    if flags.get("-d") or flags.get("--directory"):
        try:
            interp.fs.mkdir(path, parents=True, exist_ok=True)
        except FsError as e:
            write_err(io_ctx, f"mktemp: {e}\n")
            return 1
    else:
        try:
            interp.fs.write_file(path, b"")
        except FsError as e:
            write_err(io_ctx, f"mktemp: {e}\n")
            return 1
    write_out(io_ctx, path + "\n")
    return 0


# ---------------------------------------------------------------------------
# getopt (POSIX-style)
# ---------------------------------------------------------------------------


def cmd_getopt(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``getopt OPTSTRING ARGS...`` - emit a normalized argv on stdout.

    Supports the legacy ``getopt`` form: a flag string like ``ab:c`` and a
    list of positional words. Letters with ``:`` take an argument.
    """
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"getopt: missing operand\n")
        return 2
    optstr = args[0]
    rest = args[1:]
    needs_arg: dict[str, bool] = {}
    i = 0
    while i < len(optstr):
        c = optstr[i]
        wants = i + 1 < len(optstr) and optstr[i + 1] == ":"
        needs_arg[c] = wants
        i += 2 if wants else 1
    out_argv: list[str] = []
    positional: list[str] = []
    j = 0
    while j < len(rest):
        a = rest[j]
        if a == "--":
            positional.extend(rest[j + 1 :])
            break
        if a.startswith("-") and len(a) > 1:
            for k, c in enumerate(a[1:], start=1):
                if c not in needs_arg:
                    write_err(io_ctx, f"getopt: invalid option -- '{c}'\n".encode())
                    return 1
                if needs_arg[c]:
                    if k < len(a) - 1:
                        out_argv.append(f"-{c}")
                        out_argv.append(f"'{a[k + 1 :]}'")
                        break
                    j += 1
                    if j >= len(rest):
                        write_err(io_ctx, f"getopt: option requires argument -- '{c}'\n".encode())
                        return 1
                    out_argv.append(f"-{c}")
                    out_argv.append(f"'{rest[j]}'")
                    break
                out_argv.append(f"-{c}")
        else:
            positional.append(a)
        j += 1
    out_argv.append("--")
    out_argv.extend(f"'{p}'" for p in positional)
    write_out(io_ctx, " ".join(out_argv) + "\n")
    return 0


# ---------------------------------------------------------------------------
# dd (subset)
# ---------------------------------------------------------------------------


def cmd_dd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``dd if=FILE of=FILE bs=N count=N`` - block copy with limited operands."""
    params: dict[str, str] = {}
    for arg in argv[1:]:
        if "=" not in arg:
            continue
        k, _, v = arg.partition("=")
        params[k] = v
    bs = int(params.get("bs", 512))
    count = int(params["count"]) if "count" in params else None
    try:
        if "if" in params:
            data = interp.fs.read_file(params["if"])
        else:
            data = io_ctx.stdin
    except FsError as e:
        write_err(io_ctx, f"dd: {e}\n")
        return 1
    chunks: list[bytes] = []
    n_blocks = 0
    for i in range(0, len(data), bs):
        if count is not None and n_blocks >= count:
            break
        chunks.append(data[i : i + bs])
        n_blocks += 1
    out = b"".join(chunks)
    if "of" in params:
        try:
            interp.fs.write_file(params["of"], out)
        except FsError as e:
            write_err(io_ctx, f"dd: {e}\n")
            return 1
    else:
        io_ctx.stdout.write(out)
    write_err(io_ctx, f"{n_blocks}+0 records in\n{n_blocks}+0 records out\n".encode())
    return 0


# ---------------------------------------------------------------------------
# cksum (BSD CRC32)
# ---------------------------------------------------------------------------


def cmd_cksum(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    paths = argv[1:]
    if not paths:
        data = io_ctx.stdin
        crc = zlib.crc32(data) & 0xFFFFFFFF
        write_out(io_ctx, f"{crc} {len(data)}\n")
        return 0
    rc = 0
    for path in paths:
        try:
            data = interp.fs.read_file(path)
        except FsError as e:
            write_err(io_ctx, f"cksum: {e}\n")
            rc = 1
            continue
        crc = zlib.crc32(data) & 0xFFFFFFFF
        write_out(io_ctx, f"{crc} {len(data)} {path}\n")
    return rc


# ---------------------------------------------------------------------------
# crc32-ish standalone via binascii (also exposed)
# ---------------------------------------------------------------------------


def cmd_crc32(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    paths = argv[1:]
    if not paths:
        data = io_ctx.stdin
        write_out(io_ctx, f"{binascii.crc32(data):08x}\n")
        return 0
    rc = 0
    for p in paths:
        try:
            data = interp.fs.read_file(p)
        except FsError as e:
            write_err(io_ctx, f"crc32: {e}\n")
            rc = 1
            continue
        write_out(io_ctx, f"{binascii.crc32(data):08x}  {p}\n")
    return rc


__all__ = [
    "cmd_cksum",
    "cmd_cmp",
    "cmd_crc32",
    "cmd_dd",
    "cmd_expand",
    "cmd_fold",
    "cmd_getopt",
    "cmd_mktemp",
    "cmd_unexpand",
]
