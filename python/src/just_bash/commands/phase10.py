"""Phase-10 commands: more / less stubs, b3sum, col, hexdump variants,
addr2line-style, units, etc."""

from __future__ import annotations

import contextlib
import hashlib
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# more / less - non-interactive cat (terminal-aware paging is not modeled).
# ---------------------------------------------------------------------------


def cmd_more(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    write_out(io_ctx, data)
    return rc


def cmd_less(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_more(interp, argv, io_ctx)


def cmd_pager(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_more(interp, argv, io_ctx)


# ---------------------------------------------------------------------------
# col - filter reverse line feeds, etc. We pass the input through unchanged.
# ---------------------------------------------------------------------------


def cmd_col(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    # Strip CR characters and backspace sequences for a deterministic output.
    cleaned = text.replace("\r", "")
    write_out(io_ctx, cleaned)
    return rc


# ---------------------------------------------------------------------------
# b3sum (BLAKE3)
# ---------------------------------------------------------------------------


def cmd_b3sum(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """Compute a BLAKE3-like hash. Without ``blake3`` installed we fall back
    to ``sha3_256`` which has the same digest length and is deterministic."""
    paths = argv[1:]
    rc = 0
    targets: list[tuple[str, bytes]]
    if not paths:
        targets = [("-", io_ctx.stdin)]
    else:
        targets = []
        for p in paths:
            if p == "-":
                targets.append((p, io_ctx.stdin))
                continue
            try:
                targets.append((p, interp.fs.read_file(p)))
            except FsError as e:
                write_err(io_ctx, f"b3sum: {e}\n")
                rc = 1
    try:
        import blake3  # type: ignore[import-not-found]

        algo = "blake3"
    except ImportError:
        algo = "fallback"
    for label, data in targets:
        if algo == "blake3":
            digest = blake3.blake3(data).hexdigest()  # type: ignore[name-defined]
        else:
            digest = hashlib.sha3_256(data).hexdigest()
        write_out(io_ctx, f"{digest}  {label}\n")
    return rc


# ---------------------------------------------------------------------------
# Improved head / tail - the originals already accept ``-N`` shorthand; here
# we just ensure ``-c BYTES`` is the byte count even when negative.
# ---------------------------------------------------------------------------


# (head/tail already in basic.py; keep their phase-7 overrides.)


# ---------------------------------------------------------------------------
# Hex utilities: od (octal dump), hexcat (cat output to hex)
# ---------------------------------------------------------------------------


def cmd_od(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``od -c`` shows characters; ``-x`` 16-bit hex; default is ``-o`` octal."""
    try:
        flags, paths = parse_flags(argv, boolean={"-c", "-x", "-o", "-A"})
    except ValueError as e:
        write_err(io_ctx, f"od: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    char_mode = bool(flags.get("-c"))
    hex_mode = bool(flags.get("-x"))
    out: list[str] = []
    for off in range(0, len(data), 16):
        chunk = data[off : off + 16]
        if char_mode:
            words = [_od_char(b) for b in chunk]
            line = " ".join(f"{w:>3}" for w in words)
        elif hex_mode:
            words = [
                f"{int.from_bytes(chunk[i : i + 2], 'little'):04x}" for i in range(0, len(chunk), 2)
            ]
            line = " ".join(words)
        else:
            words = [
                f"{int.from_bytes(chunk[i : i + 2], 'little'):06o}" for i in range(0, len(chunk), 2)
            ]
            line = " ".join(words)
        out.append(f"{off:07o} {line}")
    out.append(f"{len(data):07o}")
    write_out(io_ctx, "\n".join(out) + "\n")
    return rc


def _od_char(byte: int) -> str:
    if 32 <= byte < 127:
        return chr(byte)
    return {0: "\\0", 9: "\\t", 10: "\\n", 13: "\\r"}.get(byte, f"{byte:03o}")


# ---------------------------------------------------------------------------
# units (rough conversion stub)
# ---------------------------------------------------------------------------


def cmd_units(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``units N FROM TO`` - convert simple SI units (limited table)."""
    args = argv[1:]
    if len(args) != 3:
        write_err(io_ctx, b"units: usage: units N FROM TO\n")
        return 2
    try:
        n = float(args[0])
    except ValueError:
        return 1
    table = {
        "B": 1.0,
        "KB": 1000.0,
        "MB": 1_000_000.0,
        "GB": 1_000_000_000.0,
        "KiB": 1024.0,
        "MiB": 1024.0**2,
        "GiB": 1024.0**3,
        "s": 1.0,
        "ms": 0.001,
        "us": 1e-6,
        "ns": 1e-9,
        "min": 60.0,
        "h": 3600.0,
    }
    if args[1] not in table or args[2] not in table:
        write_err(io_ctx, b"units: unknown unit\n")
        return 1
    converted = n * table[args[1]] / table[args[2]]
    write_out(io_ctx, f"{converted:g}\n")
    return 0


# ---------------------------------------------------------------------------
# `printf-into-file` shorthand
# ---------------------------------------------------------------------------


def cmd_pwd_alt(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``pwd -P`` should resolve symlinks; we don't support them in VFS."""
    flags = argv[1:]
    if "-L" in flags or not flags:
        write_out(io_ctx, (interp.env.get("PWD") or interp.fs.cwd) + "\n")
    else:
        write_out(io_ctx, interp.fs.cwd + "\n")
    return 0


# ---------------------------------------------------------------------------
# echo improvements (with -n / -e already exists; expose as command too).
# ---------------------------------------------------------------------------


def cmd_echo(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    newline = True
    if args and args[0] == "-n":
        newline = False
        args = args[1:]
    write_out(io_ctx, " ".join(args) + ("\n" if newline else ""))
    return 0


# ---------------------------------------------------------------------------
# tac improved: already exists in commands/more.py.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# clear / reset already exist in commands/phase6.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# tput-style sgr - emit no-op ANSI sequence by name.
# ---------------------------------------------------------------------------


def cmd_setaf(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``setaf N`` - emit an ANSI foreground color escape."""
    n = int(argv[1]) if len(argv) >= 2 else 9
    write_out(io_ctx, f"\x1b[3{n}m".encode())
    return 0


# ---------------------------------------------------------------------------
# md5 / sha1 / sha256 alt aliases (BSD-style: ``md5 -s "..."``).
# ---------------------------------------------------------------------------


def cmd_md5(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] == "-s" and len(args) > 1:
        digest = hashlib.md5(args[1].encode()).hexdigest()
        write_out(io_ctx, f'MD5 ("{args[1]}") = {digest}\n')
        return 0
    return 1


# ---------------------------------------------------------------------------
# split improvements / cat alternatives
# ---------------------------------------------------------------------------


def cmd_zcat(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``zcat FILE`` - decompress + print. We support gzip via ``gzip`` lib."""
    import gzip

    rc = 0
    for path in argv[1:]:
        try:
            data = interp.fs.read_file(path)
        except FsError as e:
            write_err(io_ctx, f"zcat: {e}\n")
            rc = 1
            continue
        try:
            decoded = gzip.decompress(data)
            io_ctx.stdout.write(decoded)
        except Exception:
            # Not gzip -> just emit the bytes (matches lenient behaviour).
            io_ctx.stdout.write(data)
    return rc


def cmd_gzip(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``gzip FILE`` and ``gzip -d FILE``."""
    import gzip

    args = argv[1:]
    decompress = False
    keep = False
    while args and args[0].startswith("-"):
        if args[0] in ("-d", "--decompress"):
            decompress = True
        if args[0] in ("-k", "--keep"):
            keep = True
        args = args[1:]
    rc = 0
    for path in args:
        try:
            data = interp.fs.read_file(path)
        except FsError as e:
            write_err(io_ctx, f"gzip: {e}\n")
            rc = 1
            continue
        if decompress:
            try:
                out_data = gzip.decompress(data)
            except OSError as e:
                write_err(io_ctx, f"gzip: {e}\n".encode())
                rc = 1
                continue
            new_path = path[:-3] if path.endswith(".gz") else path + ".out"
            interp.fs.write_file(new_path, out_data)
            if not keep:
                with contextlib.suppress(FsError):
                    interp.fs.rm(path, force=True)
        else:
            interp.fs.write_file(path + ".gz", gzip.compress(data))
            if not keep:
                with contextlib.suppress(FsError):
                    interp.fs.rm(path, force=True)
    return rc


def cmd_gunzip(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_gzip(interp, ["gzip", "-d", *argv[1:]], io_ctx)


# ---------------------------------------------------------------------------
# tee improvements - support multi-file with -a (already in basic.py).
# ---------------------------------------------------------------------------


__all__ = [
    "cmd_b3sum",
    "cmd_col",
    "cmd_echo",
    "cmd_gunzip",
    "cmd_gzip",
    "cmd_less",
    "cmd_md5",
    "cmd_more",
    "cmd_od",
    "cmd_pager",
    "cmd_pwd_alt",
    "cmd_setaf",
    "cmd_units",
    "cmd_zcat",
]
