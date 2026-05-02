"""Phase-8 commands: nproc, timeout, rsync-stub, ssh-stub, scp-stub,
chmod, chown, chgrp, ln (symbolic), readlink, mountpoint, sync, false/true."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# nproc / timeout / yes-bounded
# ---------------------------------------------------------------------------


def cmd_nproc(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    """``nproc`` - report a fake CPU count (4) for predictable scripting."""
    write_out(io_ctx, b"4\n")
    return 0


def cmd_timeout(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``timeout DURATION CMD ARGS...`` - drop the duration, dispatch the inner."""
    args = argv[1:]
    while args and args[0].startswith("-"):
        if args[0] in ("-s", "--signal", "-k", "--kill-after") and len(args) > 1:
            args = args[2:]
            continue
        args = args[1:]
    if len(args) < 2:
        write_err(io_ctx, b"timeout: missing operand\n")
        return 125
    args = args[1:]  # skip the duration argument
    return interp._dispatch(args, io_ctx)


# ---------------------------------------------------------------------------
# Network stubs
# ---------------------------------------------------------------------------


def cmd_rsync(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``rsync`` sandbox stub - emits the args as if it would copy them."""
    write_err(io_ctx, b"rsync: sandbox stub - no remote sync\n")
    write_out(io_ctx, ("rsync requested: " + " ".join(argv[1:]) + "\n").encode())
    return 0


def cmd_ssh(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    write_err(io_ctx, b"ssh: sandbox stub - no remote login\n")
    write_out(io_ctx, ("ssh requested: " + " ".join(argv[1:]) + "\n").encode())
    return 255


def cmd_scp(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    write_err(io_ctx, b"scp: sandbox stub - no remote copy\n")
    write_out(io_ctx, ("scp requested: " + " ".join(argv[1:]) + "\n").encode())
    return 1


# ---------------------------------------------------------------------------
# chmod / chown / chgrp - track mode but no real ownership
# ---------------------------------------------------------------------------


def cmd_chmod(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    recursive = False
    while args and args[0].startswith("-"):
        if args[0] in ("-R", "--recursive"):
            recursive = True
            args = args[1:]
            continue
        args = args[1:]
    if len(args) < 2:
        write_err(io_ctx, b"chmod: missing operand\n")
        return 1
    mode_str = args[0]
    paths = args[1:]
    rc = 0
    for path in paths:
        rc = max(rc, _chmod_apply(interp, io_ctx, mode_str, path, recursive=recursive))
    return rc


def _chmod_apply(
    interp: Interpreter, io_ctx: IO, mode_str: str, path: str, *, recursive: bool
) -> int:
    try:
        node = interp.fs.stat(path)
    except FsError as e:
        write_err(io_ctx, f"chmod: {e}\n")
        return 1
    if mode_str.isdigit() or (mode_str and mode_str[0] in "0"):
        try:
            node.mode = int(mode_str, 8)
        except ValueError:
            write_err(io_ctx, f"chmod: invalid mode {mode_str!r}\n".encode())
            return 1
    # Symbolic modes (e.g. ``u+x``) are accepted as a no-op for compatibility.
    if recursive and hasattr(node, "children"):
        try:
            children = interp.fs.listdir(path)
        except FsError:
            return 0
        for child in children:
            child_path = path.rstrip("/") + "/" + child if path != "/" else "/" + child
            _chmod_apply(interp, io_ctx, mode_str, child_path, recursive=True)
    return 0


def cmd_chown(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    # No real ownership in the sandbox; succeed silently for compatibility.
    return 0


def cmd_chgrp(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


# ---------------------------------------------------------------------------
# readlink / sync / mountpoint
# ---------------------------------------------------------------------------


def cmd_readlink(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """No symlinks in the sandbox; emit the canonical path."""
    if len(argv) < 2:
        write_err(io_ctx, b"readlink: missing operand\n")
        return 1
    rc = 0
    for arg in argv[1:]:
        if arg.startswith("-"):
            continue
        from just_bash.fs import path_utils

        target = path_utils.resolve(interp.fs.cwd, arg)
        if not interp.fs.exists(target):
            rc = 1
            continue
        write_out(io_ctx, target + "\n")
    return rc


def cmd_sync(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_mountpoint(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        write_err(io_ctx, b"mountpoint: missing operand\n")
        return 1
    target = argv[-1]
    if interp.fs.is_dir(target):
        write_out(io_ctx, f"{target} is not a mountpoint\n")
        return 1
    return 1


# ---------------------------------------------------------------------------
# More text helpers
# ---------------------------------------------------------------------------


def cmd_strings(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``strings`` - print printable runs >= 4 chars from a file."""
    try:
        flags, paths = parse_flags(argv, valued={"-n"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"strings: {e}\n")
        return 2
    minlen = int(flags.get("-n", 4))
    rc = 0
    for path in paths:
        try:
            data = interp.fs.read_file(path)
        except FsError as e:
            write_err(io_ctx, f"strings: {e}\n")
            rc = 1
            continue
        run: list[bytes] = []
        for byte in data:
            if 32 <= byte < 127:
                run.append(bytes([byte]))
            else:
                if len(run) >= minlen:
                    write_out(io_ctx, b"".join(run) + b"\n")
                run = []
        if len(run) >= minlen:
            write_out(io_ctx, b"".join(run) + b"\n")
    return rc


def cmd_seq_alias(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``jot`` (BSD ``seq``) thin alias."""
    from just_bash.commands.extra import cmd_seq

    return cmd_seq(interp, argv, io_ctx)


# ---------------------------------------------------------------------------
# Misc useful: which improved (-a), command-not-found friendly errors
# ---------------------------------------------------------------------------


def cmd_command_v(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``type``-style helper: ``command -v NAME`` prints how NAME would resolve."""
    args = argv[1:]
    if not args:
        return 1
    if args[0] == "-v":
        args = args[1:]
    rc = 0
    for name in args:
        if name in interp.builtins:
            write_out(io_ctx, name + "\n")
            continue
        if name in interp.commands:
            write_out(io_ctx, "/usr/bin/" + name + "\n")
            continue
        rc = 1
    return rc


__all__ = [
    "cmd_chgrp",
    "cmd_chmod",
    "cmd_chown",
    "cmd_command_v",
    "cmd_mountpoint",
    "cmd_nproc",
    "cmd_readlink",
    "cmd_rsync",
    "cmd_scp",
    "cmd_seq_alias",
    "cmd_ssh",
    "cmd_strings",
    "cmd_sync",
    "cmd_timeout",
]
