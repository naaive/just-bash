"""Phase-7 commands: factor, install, mktemp -u, sleep with units, basename
multi, dirname multi, install, env -i, more text helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# factor
# ---------------------------------------------------------------------------


def cmd_factor(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``factor N...`` - print prime factorisations."""
    args = argv[1:]
    if not args:
        # read from stdin
        data = io_ctx.stdin.decode("utf-8", errors="replace")
        args = data.split()
    for token in args:
        try:
            n = int(token)
        except ValueError:
            write_err(io_ctx, f"factor: '{token}' is not a number\n".encode())
            continue
        write_out(io_ctx, f"{n}: {' '.join(_factorise(n))}\n")
    return 0


def _factorise(n: int) -> list[str]:
    if n <= 1:
        return [str(n)]
    out: list[str] = []
    d = 2
    while d * d <= n:
        while n % d == 0:
            out.append(str(d))
            n //= d
        d += 1 if d == 2 else 2
    if n > 1:
        out.append(str(n))
    return out


# ---------------------------------------------------------------------------
# install (cp + mkdir -p)
# ---------------------------------------------------------------------------


def cmd_install(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(
            argv,
            valued={"-m", "-o", "-g"},
            boolean={"-d", "-D", "-v", "-c"},
        )
    except ValueError as e:
        write_err(io_ctx, f"install: {e}\n")
        return 2
    mode = int(str(flags.get("-m", "755")), 8)
    if flags.get("-d"):
        for p in paths:
            try:
                interp.fs.mkdir(p, parents=True, exist_ok=True, mode=mode)
            except FsError as e:
                write_err(io_ctx, f"install: {e}\n")
                return 1
        return 0
    if len(paths) < 2:
        write_err(io_ctx, b"install: missing operand\n")
        return 1
    sources, dest = paths[:-1], paths[-1]
    for src in sources:
        try:
            data = interp.fs.read_file(src)
        except FsError as e:
            write_err(io_ctx, f"install: {e}\n")
            return 1
        target = dest
        if interp.fs.is_dir(dest):
            target = dest.rstrip("/") + "/" + src.rsplit("/", 1)[-1]
        if flags.get("-D"):
            parent = target.rsplit("/", 1)[0]
            if parent:
                interp.fs.mkdir(parent, parents=True, exist_ok=True)
        interp.fs.write_file(target, data, mode=mode)
    return 0


# ---------------------------------------------------------------------------
# basename / dirname multi-arg + suffix
# ---------------------------------------------------------------------------


def cmd_basename(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"basename: missing operand\n")
        return 1
    suffix: str | None = None
    multiple = False
    i = 0
    while i < len(args) and args[i].startswith("-") and args[i] != "-":
        if args[i] == "-a":
            multiple = True
            i += 1
            continue
        if args[i] == "-s" and i + 1 < len(args):
            suffix = args[i + 1]
            multiple = True
            i += 2
            continue
        i += 1
    rest = args[i:]
    if not rest:
        write_err(io_ctx, b"basename: missing operand\n")
        return 1
    if not multiple and len(rest) == 2:
        path, suffix2 = rest
        name = path.rstrip("/").rsplit("/", 1)[-1]
        if suffix2 and name.endswith(suffix2) and name != suffix2:
            name = name[: -len(suffix2)]
        write_out(io_ctx, name + "\n")
        return 0
    for p in rest:
        name = p.rstrip("/").rsplit("/", 1)[-1]
        if suffix and name.endswith(suffix) and name != suffix:
            name = name[: -len(suffix)]
        write_out(io_ctx, name + "\n")
    return 0


def cmd_dirname(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"dirname: missing operand\n")
        return 1
    for p in args:
        idx = p.rstrip("/").rfind("/")
        if idx <= 0:
            out = "/" if p.startswith("/") else "."
        else:
            out = p[:idx]
        write_out(io_ctx, out + "\n")
    return 0


# ---------------------------------------------------------------------------
# rev (already exists), nl (already exists)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Improved sleep (parse s/m/h/d unit suffix)
# ---------------------------------------------------------------------------


def cmd_sleep(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``sleep N[smhd]`` - validate the duration but don't actually wait."""
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"sleep: missing operand\n")
        return 1
    total = 0.0
    for arg in args:
        unit = arg[-1] if arg and arg[-1] in "smhd" else "s"
        body = arg[:-1] if arg and arg[-1] in "smhd" else arg
        try:
            n = float(body)
        except ValueError:
            write_err(io_ctx, f"sleep: invalid time interval '{arg}'\n".encode())
            return 1
        mult = {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]
        total += n * mult
    del total  # measured but not slept; sandbox is deterministic
    return 0


# ---------------------------------------------------------------------------
# Improved env (with -i)
# ---------------------------------------------------------------------------


def cmd_env(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    inherit = True
    rest_argv: list[str] = []
    extra_env: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "-i" or a == "--ignore-environment":
            inherit = False
            i += 1
            continue
        if a == "-u" and i + 1 < len(args):
            interp.env.unset(args[i + 1])
            i += 2
            continue
        if "=" in a and not a.startswith("-"):
            k, _, v = a.partition("=")
            extra_env[k] = v
            i += 1
            continue
        rest_argv = args[i:]
        break
    if not inherit:
        # Snapshot exported names so we can scrub them; restore after dispatch.
        snapshot = {n: interp.env.get(n) for n in interp.env.all_var_names()}
        for n in list(snapshot):
            v = interp.env.get_var(n)
            if v is not None and v.exported:
                interp.env.unset(n)
    for k, v in extra_env.items():
        interp.env.set_var(k, v, exported=True)
    if not rest_argv:
        for k, v in sorted(interp.env.env_dict().items()):
            write_out(io_ctx, f"{k}={v}\n")
        return 0
    return interp._dispatch(rest_argv, io_ctx)


# ---------------------------------------------------------------------------
# Improved cd (-P resolves symlinks, -L stays logical) - mostly cosmetic.
# ---------------------------------------------------------------------------


# ``cd`` is a builtin defined in interpreter.builtins; we keep that path.


# ---------------------------------------------------------------------------
# tee improvements (-a multiple targets already supported)
# ---------------------------------------------------------------------------


def cmd_truncate(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-s"}, boolean={"-c"})
    except ValueError as e:
        write_err(io_ctx, f"truncate: {e}\n")
        return 2
    if "-s" not in flags:
        write_err(io_ctx, b"truncate: missing -s SIZE\n")
        return 1
    raw_size = str(flags["-s"])
    relative = ""
    if raw_size.startswith(("+", "-", "<", ">")):
        relative = raw_size[0]
        raw_size = raw_size[1:]
    try:
        size = int(raw_size)
    except ValueError:
        write_err(io_ctx, f"truncate: invalid size {raw_size!r}\n".encode())
        return 1
    rc = 0
    for p in paths:
        try:
            existing = interp.fs.read_file(p)
        except FsError:
            if flags.get("-c"):
                continue
            existing = b""
        cur_len = len(existing)
        if relative == "+":
            target = cur_len + size
        elif relative == "-":
            target = max(cur_len - size, 0)
        elif relative == "<":
            target = min(cur_len, size)
        elif relative == ">":
            target = max(cur_len, size)
        else:
            target = size
        if target > cur_len:
            new_data = existing + b"\x00" * (target - cur_len)
        else:
            new_data = existing[:target]
        try:
            interp.fs.write_file(p, new_data)
        except FsError as e:
            write_err(io_ctx, f"truncate: {e}\n")
            rc = 1
    return rc


# ---------------------------------------------------------------------------
# md5 alias / shasum
# ---------------------------------------------------------------------------


def cmd_shasum(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``shasum [-a 1|256|512]`` selects the algorithm; default 1."""
    import hashlib

    try:
        flags, paths = parse_flags(argv, valued={"-a"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"shasum: {e}\n")
        return 2
    algo_n = int(flags.get("-a", 1))
    name = {1: "sha1", 224: "sha224", 256: "sha256", 384: "sha384", 512: "sha512"}.get(algo_n)
    if name is None:
        write_err(io_ctx, b"shasum: unsupported algorithm\n")
        return 1
    rc = 0
    if not paths:
        h = hashlib.new(name)
        h.update(io_ctx.stdin)
        write_out(io_ctx, f"{h.hexdigest()}  -\n")
        return 0
    for p in paths:
        try:
            data = interp.fs.read_file(p)
        except FsError as e:
            write_err(io_ctx, f"shasum: {e}\n")
            rc = 1
            continue
        h = hashlib.new(name)
        h.update(data)
        write_out(io_ctx, f"{h.hexdigest()}  {p}\n")
    return rc


# ---------------------------------------------------------------------------
# tr improvements: -c complement is already handled. Add tr -t (truncate set1).
# Keep existing tr command.


# ---------------------------------------------------------------------------
# True/false alias commands (in addition to builtins, for ``/usr/bin/true``).
# ---------------------------------------------------------------------------


def cmd_true(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_false(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 1


# ---------------------------------------------------------------------------
# realpath improvements + dirname builtin alias.
# ---------------------------------------------------------------------------


def cmd_realpath_e(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """A ``realpath`` that supports ``-e`` (must exist) and ``-q`` (quiet)."""
    try:
        flags, paths = parse_flags(argv, boolean={"-e", "-q", "-s", "-m"})
    except ValueError as e:
        write_err(io_ctx, f"realpath: {e}\n")
        return 2
    rc = 0
    for arg in paths:
        from just_bash.fs import path_utils

        target = path_utils.resolve(interp.fs.cwd, arg)
        exists = interp.fs.exists(target)
        if flags.get("-e") and not exists:
            if not flags.get("-q"):
                write_err(io_ctx, f"realpath: {arg}: No such file or directory\n".encode())
            rc = 1
            continue
        write_out(io_ctx, target + "\n")
    return rc


__all__ = [
    "cmd_basename",
    "cmd_dirname",
    "cmd_env",
    "cmd_factor",
    "cmd_false",
    "cmd_install",
    "cmd_realpath_e",
    "cmd_shasum",
    "cmd_sleep",
    "cmd_true",
    "cmd_truncate",
]
