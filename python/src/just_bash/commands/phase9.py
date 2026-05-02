"""Phase-9 commands: process / system / misc stubs.

These are stable enough surfaces for shell scripts to expect, but the real
implementation would require host-OS integration. We emit deterministic
placeholder data instead.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# Process control stubs
# ---------------------------------------------------------------------------


def cmd_kill(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``kill [-SIG] PID...`` - sandbox no-op success unless ``-l`` is asked."""
    args = argv[1:]
    if args and args[0] in ("-l", "-L"):
        write_out(io_ctx, b"HUP INT QUIT TERM USR1 USR2 KILL\n")
        return 0
    return 0


def cmd_killall(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_pgrep(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``pgrep PATTERN`` - emit a single matching pseudo-PID for ``just-bash``."""
    args = argv[1:]
    pattern = args[-1] if args else ""
    if pattern in ("just-bash", "bash") or not pattern:
        write_out(io_ctx, b"1\n")
        return 0
    return 1


def cmd_pkill(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_fuser(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_pwait(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


# ---------------------------------------------------------------------------
# Account / session stubs
# ---------------------------------------------------------------------------


def cmd_who(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"user     pts/0        2024-01-01 00:00 (sandbox)\n")
    return 0


def cmd_w(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b" 00:00:00 up 0 days,  0:00,  1 user,  load average: 0.00, 0.00, 0.00\n"
        b"USER     TTY   FROM      LOGIN@  IDLE   WHAT\n"
        b"user     pts/0 sandbox   00:00   00:00  -bash\n",
    )
    return 0


def cmd_last(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"user     pts/0   sandbox   Mon Jan  1 00:00   still logged in\n"
        b"\nwtmp begins Mon Jan  1 00:00:00 2024\n",
    )
    return 0


def cmd_logname(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"user\n")
    return 0


def cmd_groups(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"user\n")
    return 0


def cmd_tty(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"not a tty\n")
    return 1


# ---------------------------------------------------------------------------
# Hardware / kernel info
# ---------------------------------------------------------------------------


def cmd_lscpu(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"Architecture:        x86_64\n"
        b"CPU(s):              4\n"
        b"Model name:          just-bash sandbox CPU\n"
        b"CPU MHz:             3000.000\n",
    )
    return 0


def cmd_lsmem(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"RANGE                                 SIZE  STATE\n")
    return 0


def cmd_dmesg(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"[    0.000000] just-bash sandbox kernel\n")
    return 0


def cmd_uptime(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b" 00:00:00 up 0 days,  load average: 0.00, 0.00, 0.00\n")
    return 0


def cmd_time_p(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``\\time -p CMD`` - external ``/usr/bin/time``. Reports zero seconds."""
    args = argv[1:]
    if args and args[0] == "-p":
        args = args[1:]
    rc = 0
    if args:
        rc = interp._dispatch(args, io_ctx)
    io_ctx.stderr.write(b"real 0.00\nuser 0.00\nsys 0.00\n")
    return rc


# ---------------------------------------------------------------------------
# More text helpers
# ---------------------------------------------------------------------------


def cmd_split_simple(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """A second, more permissive ``split`` is registered as an alias only.

    The original implementation in ``commands/more.cmd_split`` keeps its
    semantics; this helper exists as an alias and as a place to add
    flag-compatibility shims later.
    """
    from just_bash.commands.more import cmd_split

    return cmd_split(interp, argv, io_ctx)


def cmd_csplit(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``csplit FILE /pattern/`` - split a file at lines matching pattern.

    Minimal subset: ``csplit FILE /PAT/`` writes ``xx00``/``xx01``/...
    """
    import re

    args = argv[1:]
    if len(args) < 2:
        write_err(io_ctx, b"csplit: usage: csplit FILE PATTERN\n")
        return 2
    path, pat = args[0], args[1]
    try:
        text = interp.fs.read_text(path)
    except FsError as e:
        write_err(io_ctx, f"csplit: {e}\n")
        return 1
    if not (pat.startswith("/") and pat.endswith("/")):
        write_err(io_ctx, b"csplit: pattern must be /regex/\n")
        return 2
    rx = re.compile(pat[1:-1])
    chunks: list[list[str]] = [[]]
    for line in text.splitlines(keepends=True):
        if rx.search(line) and chunks[-1]:
            chunks.append([line])
        else:
            chunks[-1].append(line)
    for i, chunk in enumerate(chunks):
        out_path = f"xx{i:02d}"
        body = "".join(chunk)
        try:
            interp.fs.write_file(out_path, body)
        except FsError as e:
            write_err(io_ctx, f"csplit: {e}\n")
            return 1
        write_out(io_ctx, f"{len(body)}\n")
    return 0


__all__ = [
    "cmd_csplit",
    "cmd_dmesg",
    "cmd_fuser",
    "cmd_groups",
    "cmd_kill",
    "cmd_killall",
    "cmd_last",
    "cmd_logname",
    "cmd_lscpu",
    "cmd_lsmem",
    "cmd_pgrep",
    "cmd_pkill",
    "cmd_pwait",
    "cmd_split_simple",
    "cmd_time_p",
    "cmd_tty",
    "cmd_uptime",
    "cmd_w",
    "cmd_who",
]
