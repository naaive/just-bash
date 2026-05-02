"""``cp``, ``mv``, ``rm``, and a stub ``ln`` (no symlinks in MVP)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, write_err
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def cmd_cp(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-r", "-R", "-f", "-i", "-v"})
    except ValueError as e:
        write_err(io_ctx, f"cp: {e}\n")
        return 2
    if len(paths) < 2:
        write_err(io_ctx, b"cp: missing operand\n")
        return 1
    sources, dest = paths[:-1], paths[-1]
    recursive = bool(flags.get("-r") or flags.get("-R"))
    rc = 0
    for src in sources:
        try:
            interp.fs.copy(src, dest, recursive=recursive)
        except FsError as e:
            write_err(io_ctx, f"cp: {e}\n")
            rc = 1
    return rc


def cmd_mv(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-f", "-i", "-v"})
    except ValueError as e:
        write_err(io_ctx, f"mv: {e}\n")
        return 2
    del flags
    if len(paths) < 2:
        write_err(io_ctx, b"mv: missing operand\n")
        return 1
    sources, dest = paths[:-1], paths[-1]
    rc = 0
    for src in sources:
        try:
            interp.fs.move(src, dest)
        except FsError as e:
            write_err(io_ctx, f"mv: {e}\n")
            rc = 1
    return rc


def cmd_rm(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-r", "-R", "-f", "-i", "-v"})
    except ValueError as e:
        write_err(io_ctx, f"rm: {e}\n")
        return 2
    recursive = bool(flags.get("-r") or flags.get("-R"))
    force = bool(flags.get("-f"))
    if not paths:
        if force:
            return 0
        write_err(io_ctx, b"rm: missing operand\n")
        return 1
    rc = 0
    for p in paths:
        try:
            interp.fs.rm(p, recursive=recursive, force=force)
        except FsError as e:
            if not force:
                write_err(io_ctx, f"rm: {e}\n")
                rc = 1
    return rc


def cmd_ln(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    # Symlinks are intentionally unsupported in the MVP; report as such.
    write_err(io_ctx, b"ln: symbolic links not supported in this sandbox\n")
    return 1


__all__ = ["cmd_cp", "cmd_ln", "cmd_mv", "cmd_rm"]
