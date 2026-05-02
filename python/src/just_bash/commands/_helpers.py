"""Shared helpers for command implementations."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def write_out(io_ctx: IO, text: str | bytes) -> None:
    if isinstance(text, str):
        io_ctx.stdout.write(text.encode("utf-8"))
    else:
        io_ctx.stdout.write(text)


def write_err(io_ctx: IO, text: str | bytes) -> None:
    if isinstance(text, str):
        io_ctx.stderr.write(text.encode("utf-8"))
    else:
        io_ctx.stderr.write(text)


def read_input(interp: Interpreter, io_ctx: IO, paths: list[str]) -> tuple[bytes, int]:
    """Read input bytes from ``paths`` (``-`` means stdin) or just stdin if empty.

    Returns ``(data, exit_code)`` so the caller can short-circuit on errors.
    """
    if not paths:
        return io_ctx.stdin, 0
    chunks: list[bytes] = []
    rc = 0
    for path in paths:
        if path == "-":
            chunks.append(io_ctx.stdin)
            continue
        try:
            chunks.append(interp.fs.read_file(path))
        except FsError as e:
            write_err(io_ctx, f"{path}: {e}\n")
            rc = 1
    return b"".join(chunks), rc


def split_lines(data: bytes, *, keepends: bool = False) -> list[str]:
    text = data.decode("utf-8", errors="replace")
    return text.splitlines(keepends=keepends)


def parse_flags(
    argv: list[str],
    *,
    boolean: set[str] | None = None,
    valued: set[str] | None = None,
) -> tuple[dict[str, str | bool], list[str]]:
    """Tiny ad-hoc flag parser tailored for the command surface we ship.

    Returns ``(flags, positional)``. ``--`` ends flag parsing; bare ``-`` is
    positional (means stdin). Combined short flags (``-rn``) are split.
    """
    boolean = boolean or set()
    valued = valued or set()
    flags: dict[str, str | bool] = {}
    pos: list[str] = []
    i = 1  # skip argv[0] = command name
    while i < len(argv):
        a = argv[i]
        if a == "--":
            pos.extend(argv[i + 1 :])
            break
        if a == "-" or not a.startswith("-"):
            pos.append(a)
            i += 1
            continue
        if a.startswith("--"):
            name, _, value = a.partition("=")
            if name in valued:
                if value:
                    flags[name] = value
                    i += 1
                    continue
                if i + 1 >= len(argv):
                    raise ValueError(f"option {name} requires a value")
                flags[name] = argv[i + 1]
                i += 2
                continue
            if name in boolean:
                flags[name] = True
                i += 1
                continue
            raise ValueError(f"unknown option: {a}")
        # Short flags.
        rest = a[1:]
        j = 0
        while j < len(rest):
            ch = rest[j]
            short = "-" + ch
            if short in valued:
                value = rest[j + 1 :]
                if not value:
                    if i + 1 >= len(argv):
                        raise ValueError(f"option {short} requires a value")
                    value = argv[i + 1]
                    i += 1
                flags[short] = value
                j = len(rest)
                continue
            if short in boolean:
                flags[short] = True
                j += 1
                continue
            raise ValueError(f"unknown option: {short}")
        i += 1
    return flags, pos


__all__ = ["parse_flags", "read_input", "split_lines", "write_err", "write_out"]
