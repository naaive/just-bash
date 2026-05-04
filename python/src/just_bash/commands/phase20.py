"""Phase-20 commands: ``bash`` / ``sh`` re-entrant interpreter dispatch.

These let scripts call ``bash other.sh`` / ``bash -c '...'`` and have the
inner script execute in a child interpreter that shares the parent's
filesystem. The child gets a fresh environment scope (with PATH/HOME
inherited) so variable mutations don't leak back, matching real bash's
process-isolation semantics.
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from just_bash.commands._helpers import write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def cmd_bash(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``bash [-c CMD | FILE] [ARG...]`` - run an inner script.

    Reuses the parent's FS so writes from the child are visible after.
    Variable mutations are isolated.
    """
    args = argv[1:]
    if not args:
        # Interactive mode would normally drop into a REPL. Here we just
        # report an empty-script success — there's nothing to read.
        return 0

    if args[0] in ("--version", "-V"):
        write_out(io_ctx, b"GNU bash, version 5.2.21(1)-just-bash-py\n")
        return 0

    source: str
    positional: list[str]
    if args[0] == "-c":
        if len(args) < 2:
            write_err(io_ctx, b"bash: -c: option requires an argument\n")
            return 2
        source = args[1]
        # ``bash -c CMD ARG0 ARG1 ...`` sets $0 = ARG0, $1 = ARG1 ...
        positional = args[3:] if len(args) >= 3 else []
    else:
        path = args[0]
        try:
            source = interp.fs.read_text(path)
        except FsError as e:
            write_err(io_ctx, f"bash: {path}: {e}\n")
            return 127
        positional = args[1:]

    return _run_inner(interp, source, positional, io_ctx)


def cmd_sh(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """POSIX ``sh`` — alias to the bash dispatcher in our sandbox."""
    return cmd_bash(interp, argv, io_ctx)


def _run_inner(parent: Interpreter, source: str, positional: list[str], io_ctx: IO) -> int:
    """Parse + execute ``source`` in a child interpreter sharing the FS."""
    from just_bash.interpreter.environment import Environment
    from just_bash.interpreter.errors import ExitException
    from just_bash.interpreter.interpreter import IO as _IO
    from just_bash.interpreter.interpreter import Interpreter as _Interp
    from just_bash.parser.parser import ParseError, parse

    # Inherit exported variables from the parent so PATH / HOME / etc.
    # are visible to the child.
    inherited: dict[str, str] = {}
    for name in parent.env.all_var_names():
        v = parent.env.get_var(name)
        if v is not None and v.exported and v.value is not None:
            inherited[name] = v.value

    child_env = Environment(initial_env=inherited)
    child_env.positional = list(positional)
    child = _Interp(fs=parent.fs, env=child_env)
    child_io = _IO(stdin=io_ctx.stdin, stdout=io.BytesIO(), stderr=io.BytesIO())

    try:
        script = parse(source)
    except ParseError as e:
        write_err(io_ctx, f"bash: parse error: {e}\n")
        return 2

    try:
        for stmt in script.statements:
            child._run_statement(stmt, child_io)
        rc = child_env.last_exit
    except ExitException as e:
        rc = e.code
    except Exception as e:
        write_err(io_ctx, f"bash: {e}\n")
        rc = 1

    # Forward captured streams to the parent's IO.
    io_ctx.stdout.write(child_io.stdout.getvalue())
    io_ctx.stderr.write(child_io.stderr.getvalue())
    return rc


__all__ = ["cmd_bash", "cmd_sh"]
