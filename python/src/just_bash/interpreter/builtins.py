"""Shell builtins.

These run inside the interpreter's process, so they can mutate the environment
(``cd``, ``export``, ``unset``...) and the filesystem state directly.
"""

from __future__ import annotations

import re
import shlex
from collections.abc import Callable
from typing import TYPE_CHECKING

from just_bash.fs.vfs import FsError
from just_bash.interpreter.conditionals import eval_test_args
from just_bash.interpreter.errors import (
    BreakException,
    ContinueException,
    ExitException,
    ReturnException,
)

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


Builtin = Callable[["Interpreter", "list[str]", "IO"], int]


def default_builtins() -> dict[str, Builtin]:
    return {
        ":": _b_colon,
        "true": _b_true,
        "false": _b_false,
        "echo": _b_echo,
        "printf": _b_printf,
        "cd": _b_cd,
        "pwd": _b_pwd,
        "export": _b_export,
        "unset": _b_unset,
        "set": _b_set,
        "read": _b_read,
        "exit": _b_exit,
        "return": _b_return,
        "shift": _b_shift,
        "test": _b_test,
        "[": _b_bracket_test,
        "local": _b_local,
        "eval": _b_eval,
        ".": _b_source,
        "source": _b_source,
        "type": _b_type,
        "command": _b_command,
        "let": _b_let,
        "break": _b_break,
        "continue": _b_continue,
        "declare": _b_declare,
        "typeset": _b_declare,
        "trap": _b_trap,
        "pushd": _b_pushd,
        "popd": _b_popd,
        "dirs": _b_dirs,
        "alias": _b_alias,
        "unalias": _b_unalias,
        "shopt": _b_shopt,
        "time": _b_time,
        "umask": _b_umask,
        "ulimit": _b_ulimit,
        "history": _b_history,
        "help": _b_help,
    }


# ---------------------------------------------------------------------------
# Trivial
# ---------------------------------------------------------------------------


def _b_colon(_i: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def _b_true(_i: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def _b_false(_i: Interpreter, _argv: list[str], _io: IO) -> int:
    return 1


# ---------------------------------------------------------------------------
# echo / printf
# ---------------------------------------------------------------------------


def _b_echo(_i: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    newline = True
    interpret_escapes = False
    while args and args[0].startswith("-") and args[0] != "-":
        flag = args[0]
        if flag == "-n":
            newline = False
            args = args[1:]
            continue
        if flag == "-e":
            interpret_escapes = True
            args = args[1:]
            continue
        if flag == "-E":
            interpret_escapes = False
            args = args[1:]
            continue
        if all(c in "neE" for c in flag[1:]):
            for c in flag[1:]:
                if c == "n":
                    newline = False
                elif c == "e":
                    interpret_escapes = True
                elif c == "E":
                    interpret_escapes = False
            args = args[1:]
            continue
        break
    text = " ".join(args)
    if interpret_escapes:
        text = _interpret_escapes(text)
    if newline:
        text += "\n"
    io_ctx.stdout.write(text.encode("utf-8"))
    return 0


def _interpret_escapes(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != "\\" or i + 1 >= len(s):
            out.append(ch)
            i += 1
            continue
        nxt = s[i + 1]
        i += 2
        mapping = {
            "n": "\n",
            "t": "\t",
            "r": "\r",
            "\\": "\\",
            "a": "\a",
            "b": "\b",
            "f": "\f",
            "v": "\v",
            "0": "\0",
        }
        out.append(mapping.get(nxt, "\\" + nxt))
    return "".join(out)


def _b_printf(_i: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        io_ctx.stderr.write(b"printf: usage: printf format [arguments]\n")
        return 2
    fmt_raw = _interpret_escapes(argv[1])
    args = argv[2:]
    output: list[str] = []
    while True:
        rendered, args = _render_printf(fmt_raw, args)
        output.append(rendered)
        if not args:
            break
    io_ctx.stdout.write("".join(output).encode("utf-8"))
    return 0


_PRINTF_FMT = re.compile(
    r"%(?P<flags>[-+ 0#]*)(?P<width>\d*)(?:\.(?P<prec>\d+))?(?P<conv>[%dsioxXc])"
)


def _render_printf(fmt: str, args: list[str]) -> tuple[str, list[str]]:
    out: list[str] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch != "%":
            out.append(ch)
            i += 1
            continue
        m = _PRINTF_FMT.match(fmt, i)
        if m is None:
            out.append(ch)
            i += 1
            continue
        conv = m.group("conv")
        i = m.end()
        if conv == "%":
            out.append("%")
            continue
        if not args:
            arg = ""
        else:
            arg = args[0]
            args = args[1:]
        out.append(_format_printf(arg, m))
    return "".join(out), args


def _format_printf(arg: str, m: re.Match[str]) -> str:
    conv = m.group("conv")
    flags = m.group("flags") or ""
    width = m.group("width") or ""
    prec = m.group("prec")
    spec = "%" + flags + width + (f".{prec}" if prec is not None else "") + conv
    if conv == "s":
        return spec % arg
    if conv in ("d", "i"):
        try:
            value = int(arg) if arg else 0
        except ValueError:
            value = 0
        return spec % value
    if conv in ("o", "x", "X"):
        try:
            value = int(arg) if arg else 0
        except ValueError:
            value = 0
        return spec % value
    if conv == "c":
        return arg[:1]
    return spec % arg


# ---------------------------------------------------------------------------
# Filesystem
# ---------------------------------------------------------------------------


def _b_cd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) > 2:
        io_ctx.stderr.write(b"cd: too many arguments\n")
        return 1
    target = argv[1] if len(argv) == 2 else interp.env.get("HOME") or "/"
    if target == "-":
        target = interp.env.get("OLDPWD") or interp.fs.cwd
    try:
        old = interp.fs.cwd
        interp.fs.chdir(target)
        interp.env.set_var("OLDPWD", old, exported=True)
        interp.env.set_var("PWD", interp.fs.cwd, exported=True)
        return 0
    except FsError as e:
        io_ctx.stderr.write(f"cd: {e}\n".encode())
        return 1


def _b_pwd(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    io_ctx.stdout.write((interp.fs.cwd + "\n").encode("utf-8"))
    return 0


# ---------------------------------------------------------------------------
# Variables
# ---------------------------------------------------------------------------


def _b_export(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) == 1:
        for name in interp.env.all_var_names():
            v = interp.env.get_var(name)
            if v is not None and v.exported:
                io_ctx.stdout.write(f"declare -x {name}={shlex.quote(v.value)}\n".encode())
        return 0
    for arg in argv[1:]:
        if "=" in arg:
            name, _, value = arg.partition("=")
            interp.env.export(name, value)
        else:
            interp.env.export(arg)
    return 0


def _b_unset(interp: Interpreter, argv: list[str], _io: IO) -> int:
    for arg in argv[1:]:
        if arg in {"-f", "-v"}:
            continue
        interp.env.unset(arg)
    return 0


def _b_set(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        for name in interp.env.all_var_names():
            v = interp.env.get_var(name)
            if v is not None:
                io_ctx.stdout.write(f"{name}={v.value}\n".encode())
        return 0
    # ``set -e``, ``set +e`` etc.: just track the flags.
    pos: list[str] = []
    parsed_flags = False
    for arg in args:
        if not parsed_flags and arg.startswith("-") and len(arg) > 1 and not arg.startswith("--"):
            for c in arg[1:]:
                interp.env.shell_options.add(c)
            continue
        if not parsed_flags and arg.startswith("+") and len(arg) > 1:
            for c in arg[1:]:
                interp.env.shell_options.discard(c)
            continue
        if arg == "--":
            parsed_flags = True
            continue
        pos.append(arg)
    if pos:
        interp.env.positional = pos
    return 0


def _b_read(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    raw_argv = argv[1:]
    var_names: list[str] = []
    raw = False
    delim = "\n"
    i = 0
    while i < len(raw_argv):
        a = raw_argv[i]
        if a == "-r":
            raw = True
            i += 1
            continue
        if a == "-d" and i + 1 < len(raw_argv):
            delim = raw_argv[i + 1]
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        var_names.append(a)
        i += 1
    data = io_ctx.stdin.decode("utf-8", errors="replace")
    line, _, rest = data.partition(delim or "\n")
    io_ctx.stdin = rest.encode("utf-8")
    if not raw:
        line = line.replace("\\\n", "")
    if not var_names:
        var_names = ["REPLY"]
    ifs = interp.env.get("IFS") or " \t\n"
    if len(var_names) == 1:
        interp.env.set_var(var_names[0], line)
        return 0
    fields = _ifs_split(line, ifs)
    for i, name in enumerate(var_names):
        if i == len(var_names) - 1:
            # Last variable absorbs the remaining fields.
            interp.env.set_var(
                name, (ifs[0] if ifs else " ").join(fields[i:]) if fields[i:] else ""
            )
        else:
            interp.env.set_var(name, fields[i] if i < len(fields) else "")
    return 0


def _ifs_split(line: str, ifs: str) -> list[str]:
    if not line:
        return []
    fields = [""]
    for ch in line:
        if ch in ifs:
            if ch in " \t\n":
                if fields[-1] != "":
                    fields.append("")
                continue
            fields.append("")
            continue
        fields[-1] += ch
    if fields and fields[-1] == "" and any(c in " \t\n" for c in ifs):
        fields.pop()
    return fields


# ---------------------------------------------------------------------------
# Control-flow keywords
# ---------------------------------------------------------------------------


def _b_exit(_i: Interpreter, argv: list[str], _io: IO) -> int:
    code = int(argv[1]) if len(argv) > 1 else 0
    raise ExitException(code)


def _b_return(_i: Interpreter, argv: list[str], _io: IO) -> int:
    code = int(argv[1]) if len(argv) > 1 else 0
    raise ReturnException(code)


def _b_break(_i: Interpreter, argv: list[str], _io: IO) -> int:
    levels = int(argv[1]) if len(argv) > 1 else 1
    raise BreakException(levels)


def _b_continue(_i: Interpreter, argv: list[str], _io: IO) -> int:
    levels = int(argv[1]) if len(argv) > 1 else 1
    raise ContinueException(levels)


def _b_shift(interp: Interpreter, argv: list[str], _io: IO) -> int:
    n = int(argv[1]) if len(argv) > 1 else 1
    if n < 0 or n > len(interp.env.positional):
        return 1
    interp.env.positional = interp.env.positional[n:]
    return 0


# ---------------------------------------------------------------------------
# test / [
# ---------------------------------------------------------------------------


def _b_test(interp: Interpreter, argv: list[str], _io: IO) -> int:
    args = argv[1:]
    if not args:
        return 1
    return 0 if eval_test_args(interp, args) else 1


def _b_bracket_test(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args or args[-1] != "]":
        io_ctx.stderr.write(b"[: missing ']'\n")
        return 2
    return 0 if eval_test_args(interp, args[:-1]) else 1


# ---------------------------------------------------------------------------
# local
# ---------------------------------------------------------------------------


def _b_local(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if not interp.env.in_function():
        io_ctx.stderr.write(b"local: can only be used in a function\n")
        return 1
    for arg in argv[1:]:
        if "=" in arg:
            name, _, value = arg.partition("=")
            interp.env.set_var(name, value, local=True)
        else:
            interp.env.set_var(arg, "", local=True)
    return 0


# ---------------------------------------------------------------------------
# eval / source
# ---------------------------------------------------------------------------


def _b_eval(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    from just_bash.parser.parser import parse

    src = " ".join(argv[1:])
    if not src.strip():
        return 0
    script = parse(src)
    last = 0
    for stmt in script.statements:
        last = interp._run_statement(stmt, io_ctx)
    return last


def _b_source(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        io_ctx.stderr.write(b"source: filename argument required\n")
        return 2
    path = argv[1]
    try:
        text = interp.fs.read_text(path)
    except FsError as e:
        io_ctx.stderr.write(f"source: {e}\n".encode())
        return 1
    from just_bash.parser.parser import parse

    script = parse(text)
    saved_pos = interp.env.positional
    if len(argv) > 2:
        interp.env.positional = argv[2:]
    try:
        last = 0
        for stmt in script.statements:
            last = interp._run_statement(stmt, io_ctx)
        return last
    except ReturnException as e:
        return e.code
    finally:
        interp.env.positional = saved_pos


# ---------------------------------------------------------------------------
# type / command / let / declare
# ---------------------------------------------------------------------------


def _b_type(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for name in argv[1:]:
        if name in interp.builtins:
            io_ctx.stdout.write(f"{name} is a shell builtin\n".encode())
            continue
        if interp.env.get_function(name) is not None:
            io_ctx.stdout.write(f"{name} is a function\n".encode())
            continue
        if name in interp.commands:
            io_ctx.stdout.write(f"{name} is a builtin command\n".encode())
            continue
        io_ctx.stderr.write(f"type: {name}: not found\n".encode())
        rc = 1
    return rc


def _b_command(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    while args and args[0].startswith("-"):
        args = args[1:]
    if not args:
        return 0
    return interp._dispatch(args, io_ctx)


def _b_let(interp: Interpreter, argv: list[str], _io: IO) -> int:
    from just_bash.interpreter.arithmetic import eval_arith
    from just_bash.parser.arithmetic_parser import parse_arith_text

    last = 0
    for expr_text in argv[1:]:
        expr = parse_arith_text(expr_text)
        last = eval_arith(interp, expr)
    return 0 if last != 0 else 1


def _b_declare(interp: Interpreter, argv: list[str], _io: IO) -> int:
    args = argv[1:]
    exported = False
    assoc = False
    indexed = False
    while args and (args[0].startswith(("-", "+"))) and args[0] not in ("-", "--"):
        flag = args[0]
        if flag.startswith("-"):
            if "x" in flag[1:]:
                exported = True
            if "A" in flag[1:]:
                assoc = True
            if "a" in flag[1:]:
                indexed = True
        args = args[1:]
    if args and args[0] == "--":
        args = args[1:]
    for arg in args:
        if "=" in arg:
            name, _, value = arg.partition("=")
            if assoc:
                interp.env.declare_assoc(name, exported=exported)
            elif indexed:
                interp.env.set_array(name, [value], exported=exported)
            else:
                interp.env.set_var(name, value, exported=exported)
        elif assoc:
            interp.env.declare_assoc(arg, exported=exported)
        elif indexed:
            interp.env.set_array(arg, [], exported=exported)
        else:
            interp.env.set_var(arg, "", exported=exported)
    return 0


_VALID_SIGNALS = frozenset(
    {"EXIT", "ERR", "DEBUG", "RETURN", "INT", "TERM", "HUP", "QUIT", "USR1", "USR2"}
)


def _b_trap(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``trap [HANDLER] SIGNAL...`` register / clear signal handlers.

    Bash semantics: ``trap`` with no args lists current handlers; ``trap -``
    or ``trap '' SIG`` clears (default vs ignore - we treat both as remove).
    """
    args = argv[1:]
    if not args:
        for sig, cmd in sorted(interp.env.traps.items()):
            io_ctx.stdout.write(f"trap -- {cmd!r} {sig}\n".encode())
        return 0
    if args[0] == "-l":
        io_ctx.stdout.write(b"EXIT ERR DEBUG RETURN INT TERM HUP QUIT USR1 USR2\n")
        return 0
    handler = args[0]
    signals = args[1:]
    if not signals:
        io_ctx.stderr.write(b"trap: usage: trap [HANDLER] SIGNAL...\n")
        return 2
    for sig in signals:
        sig_name = sig.upper().removeprefix("SIG")
        if sig_name not in _VALID_SIGNALS:
            io_ctx.stderr.write(f"trap: {sig}: invalid signal specification\n".encode())
            return 1
        if handler in ("-", ""):
            interp.env.traps.pop(sig_name, None)
        else:
            interp.env.traps[sig_name] = handler
    return 0


# ---------------------------------------------------------------------------
# Phase-4 builtins
# ---------------------------------------------------------------------------


_DIR_STACK: list[str] = []
_ALIASES: dict[str, str] = {}
_SHOPT: dict[str, bool] = {}


def _b_pushd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``pushd DIR`` - save current dir on the stack and chdir to ``DIR``.

    Bash semantics: the directory stack always has the current directory at
    its head. With no argument, swap the top two entries.
    """
    args = argv[1:]
    # Lazy-init the stack with the current directory.
    if not _DIR_STACK:
        _DIR_STACK.append(interp.fs.cwd)
    if not args:
        if len(_DIR_STACK) < 2:
            io_ctx.stderr.write(b"pushd: no other directory\n")
            return 1
        _DIR_STACK[0], _DIR_STACK[1] = _DIR_STACK[1], _DIR_STACK[0]
        try:
            interp.fs.chdir(_DIR_STACK[0])
        except FsError as e:
            io_ctx.stderr.write(f"pushd: {e}\n".encode())
            return 1
        io_ctx.stdout.write((" ".join(_DIR_STACK) + "\n").encode())
        return 0
    target = args[0]
    try:
        interp.fs.chdir(target)
    except FsError as e:
        io_ctx.stderr.write(f"pushd: {e}\n".encode())
        return 1
    _DIR_STACK.insert(0, interp.fs.cwd)
    io_ctx.stdout.write((" ".join(_DIR_STACK) + "\n").encode())
    return 0


def _b_popd(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    if len(_DIR_STACK) < 2:
        io_ctx.stderr.write(b"popd: directory stack empty\n")
        return 1
    _DIR_STACK.pop(0)
    try:
        interp.fs.chdir(_DIR_STACK[0])
    except FsError as e:
        io_ctx.stderr.write(f"popd: {e}\n".encode())
        return 1
    io_ctx.stdout.write((" ".join(_DIR_STACK) + "\n").encode())
    return 0


def _b_dirs(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    stack = _DIR_STACK if _DIR_STACK else [interp.fs.cwd]
    io_ctx.stdout.write((" ".join(stack) + "\n").encode())
    return 0


def _b_alias(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        for k, v in sorted(_ALIASES.items()):
            io_ctx.stdout.write(f"alias {k}='{v}'\n".encode())
        return 0
    rc = 0
    for arg in args:
        if "=" in arg:
            name, _, value = arg.partition("=")
            _ALIASES[name] = value.strip("'\"")
        else:
            v = _ALIASES.get(arg)
            if v is None:
                io_ctx.stderr.write(f"alias: {arg}: not found\n".encode())
                rc = 1
            else:
                io_ctx.stdout.write(f"alias {arg}='{v}'\n".encode())
    return rc


def _b_unalias(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for arg in argv[1:]:
        if arg in _ALIASES:
            del _ALIASES[arg]
        else:
            io_ctx.stderr.write(f"unalias: {arg}: not found\n".encode())
            rc = 1
    return rc


def _b_shopt(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    set_mode = True
    if args and args[0] == "-s":
        set_mode = True
        args = args[1:]
    elif args and args[0] == "-u":
        set_mode = False
        args = args[1:]
    if not args:
        for k, v in sorted(_SHOPT.items()):
            io_ctx.stdout.write(f"{k:<30}\t{'on' if v else 'off'}\n".encode())
        return 0
    for opt in args:
        _SHOPT[opt] = set_mode
    return 0


def _b_time(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``time CMD ARGS`` - run cmd, emit pseudo-real/user/sys lines on stderr.

    The sandbox is deterministic so we emit zeros; the practical purpose is
    to allow scripts that use ``time foo`` not to break.
    """
    if len(argv) < 2:
        io_ctx.stderr.write(b"\nreal\t0m0.000s\nuser\t0m0.000s\nsys\t0m0.000s\n")
        return 0
    rc = interp._dispatch(argv[1:], io_ctx)
    io_ctx.stderr.write(b"\nreal\t0m0.000s\nuser\t0m0.000s\nsys\t0m0.000s\n")
    return rc


def _b_umask(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) == 1:
        io_ctx.stdout.write(b"0022\n")
    return 0


def _b_ulimit(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    io_ctx.stdout.write(b"unlimited\n")
    return 0


def _b_history(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def _b_help(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    io_ctx.stdout.write(b"GNU bash, sandboxed (just-bash-py): see README for supported builtins.\n")
    return 0


__all__ = ["Builtin", "default_builtins"]
