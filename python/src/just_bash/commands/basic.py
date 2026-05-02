"""Basic core utilities: cat, ls, mkdir, rmdir, touch, head, tail, wc, tee, etc."""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs import path_utils
from just_bash.fs.vfs import Directory, File, FsError, FsNode

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# cat
# ---------------------------------------------------------------------------


def cmd_cat(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-n", "-b", "-E", "-s"})
    except ValueError as e:
        write_err(io_ctx, f"cat: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    if flags.get("-n") or flags.get("-b"):
        out_lines: list[str] = []
        n = 1
        for line in text.split("\n"):
            if not line and flags.get("-b"):
                out_lines.append(line)
                continue
            out_lines.append(f"{n:>6}\t{line}")
            n += 1
        text = "\n".join(out_lines)
    if flags.get("-E"):
        text = text.replace("\n", "$\n")
    write_out(io_ctx, text)
    return rc


# ---------------------------------------------------------------------------
# ls
# ---------------------------------------------------------------------------


def cmd_ls(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-a", "-A", "-l", "-1", "-d", "-r", "-R", "-F"})
    except ValueError as e:
        write_err(io_ctx, f"ls: {e}\n")
        return 2
    if not paths:
        paths = [interp.fs.cwd]
    show_hidden = bool(flags.get("-a") or flags.get("-A"))
    long_form = bool(flags.get("-l"))
    one_per_line = bool(flags.get("-1") or long_form)
    classify = bool(flags.get("-F"))
    rc = 0

    def fmt(name: str, node: FsNode) -> str:
        if classify and isinstance(node, Directory):
            return name + "/"
        return name

    def show_dir_listing(target: str) -> None:
        try:
            entries = interp.fs.listdir(target)
        except FsError as e:
            write_err(io_ctx, f"ls: {e}\n")
            nonlocal_rc(1)
            return
        if not show_hidden:
            entries = [e for e in entries if not e.startswith(".")]
        if flags.get("-r"):
            entries.reverse()
        if long_form:
            for name in entries:
                node = interp.fs.stat(path_utils.join(target, name))
                kind = "d" if isinstance(node, Directory) else "-"
                size = node.size if isinstance(node, File) else 0
                mode = f"{node.mode:o}".rjust(3, "0")
                write_out(io_ctx, f"{kind}{mode} {size:>8} {fmt(name, node)}\n")
        elif one_per_line:
            for name in entries:
                node = interp.fs.stat(path_utils.join(target, name))
                write_out(io_ctx, fmt(name, node) + "\n")
        else:
            decorated = [fmt(n, interp.fs.stat(path_utils.join(target, n))) for n in entries]
            write_out(io_ctx, "  ".join(decorated) + ("\n" if decorated else ""))

    def nonlocal_rc(code: int) -> None:
        nonlocal rc
        rc = max(rc, code)

    for p in paths:
        try:
            node = interp.fs.stat(p)
        except FsError as e:
            write_err(io_ctx, f"ls: {e}\n")
            nonlocal_rc(2)
            continue
        if isinstance(node, Directory) and not flags.get("-d"):
            if len(paths) > 1:
                write_out(io_ctx, f"{p}:\n")
            show_dir_listing(p)
        else:
            if long_form:
                kind = "d" if isinstance(node, Directory) else "-"
                size = node.size if isinstance(node, File) else 0
                write_out(io_ctx, f"{kind}{node.mode:03o} {size:>8} {fmt(p, node)}\n")
            else:
                write_out(io_ctx, fmt(p, node) + "\n")
    return rc


# ---------------------------------------------------------------------------
# mkdir / rmdir / touch
# ---------------------------------------------------------------------------


def cmd_mkdir(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-p"})
    except ValueError as e:
        write_err(io_ctx, f"mkdir: {e}\n")
        return 2
    if not paths:
        write_err(io_ctx, b"mkdir: missing operand\n")
        return 1
    rc = 0
    for p in paths:
        try:
            interp.fs.mkdir(p, parents=bool(flags.get("-p")), exist_ok=bool(flags.get("-p")))
        except FsError as e:
            write_err(io_ctx, f"mkdir: {e}\n")
            rc = 1
    return rc


def cmd_rmdir(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    paths = argv[1:]
    if not paths:
        write_err(io_ctx, b"rmdir: missing operand\n")
        return 1
    rc = 0
    for p in paths:
        try:
            interp.fs.rmdir(p)
        except FsError as e:
            write_err(io_ctx, f"rmdir: {e}\n")
            rc = 1
    return rc


def cmd_touch(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    paths = argv[1:]
    if not paths:
        write_err(io_ctx, b"touch: missing file operand\n")
        return 1
    rc = 0
    for p in paths:
        try:
            interp.fs.touch(p)
        except FsError as e:
            write_err(io_ctx, f"touch: {e}\n")
            rc = 1
    return rc


# ---------------------------------------------------------------------------
# head / tail / wc / tee
# ---------------------------------------------------------------------------


def _split_legacy_n_flag(argv: list[str]) -> list[str]:
    """Translate the legacy ``-N`` shorthand (e.g. ``head -3``) into ``-n N``."""
    out: list[str] = []
    for arg in argv:
        if arg.startswith("-") and len(arg) > 1 and arg[1:].isdigit() and not arg.startswith("--"):
            out.append("-n")
            out.append(arg[1:])
            continue
        out.append(arg)
    return out


def cmd_head(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(_split_legacy_n_flag(argv), boolean=set(), valued={"-n", "-c"})
    except ValueError as e:
        write_err(io_ctx, f"head: {e}\n")
        return 2
    n = int(flags.get("-n", 10))
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    if "-c" in flags:
        c = int(flags["-c"])
        write_out(io_ctx, text[:c])
        return rc
    lines = text.splitlines(keepends=True)
    write_out(io_ctx, "".join(lines[:n]))
    return rc


def cmd_tail(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(_split_legacy_n_flag(argv), boolean=set(), valued={"-n", "-c"})
    except ValueError as e:
        write_err(io_ctx, f"tail: {e}\n")
        return 2
    raw_n = str(flags.get("-n", "10"))
    from_start = raw_n.startswith("+")
    n = int(raw_n.lstrip("+-")) if raw_n else 10
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    if "-c" in flags:
        c = int(flags["-c"])
        write_out(io_ctx, text[-c:])
        return rc
    lines = text.splitlines(keepends=True)
    out = lines[n - 1 :] if from_start else lines[-n:]
    write_out(io_ctx, "".join(out))
    return rc


def cmd_wc(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-l", "-w", "-c", "-m"})
    except ValueError as e:
        write_err(io_ctx, f"wc: {e}\n")
        return 2
    show_lines = bool(flags.get("-l"))
    show_words = bool(flags.get("-w"))
    show_bytes = bool(flags.get("-c"))
    show_chars = bool(flags.get("-m"))
    if not (show_lines or show_words or show_bytes or show_chars):
        show_lines = show_words = show_bytes = True
    rc = 0
    targets = paths or ["-"]
    totals = [0, 0, 0]
    for path in targets:
        if path == "-":
            data = io_ctx.stdin
            label = ""
        else:
            try:
                data = interp.fs.read_file(path)
                label = " " + path
            except FsError as e:
                write_err(io_ctx, f"wc: {e}\n")
                rc = 1
                continue
        text = data.decode("utf-8", errors="replace")
        n_lines = text.count("\n")
        n_words = len(text.split())
        n_bytes = len(data)
        # Bash's wc widths: a single column reading from stdin is unpadded,
        # otherwise pad to 7. (Real bash also bumps the width for very large
        # counts; we match the common case which covers all everyday usage.)
        active = sum(1 for f in (show_lines, show_words, show_bytes or show_chars) if f)
        named = bool(label)
        if active == 1 and not named:
            width = len(str(max(n_lines, n_words, n_bytes)))
        else:
            width = max(7, len(str(max(n_lines, n_words, n_bytes))))
        cols: list[str] = []
        if show_lines:
            cols.append(f"{n_lines:>{width}}")
        if show_words:
            cols.append(f"{n_words:>{width}}")
        if show_bytes or show_chars:
            cols.append(f"{n_bytes:>{width}}")
        write_out(io_ctx, " ".join(cols) + label + "\n")
        totals[0] += n_lines
        totals[1] += n_words
        totals[2] += n_bytes
    if len(targets) > 1:
        width = max(7, len(str(max(totals))))
        cols = []
        if show_lines:
            cols.append(f"{totals[0]:>{width}}")
        if show_words:
            cols.append(f"{totals[1]:>{width}}")
        if show_bytes or show_chars:
            cols.append(f"{totals[2]:>{width}}")
        write_out(io_ctx, " ".join(cols) + " total\n")
    return rc


def cmd_tee(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-a"})
    except ValueError as e:
        write_err(io_ctx, f"tee: {e}\n")
        return 2
    data = io_ctx.stdin
    write_out(io_ctx, data)
    for p in paths:
        try:
            if flags.get("-a"):
                interp.fs.append_file(p, data)
            else:
                interp.fs.write_file(p, data)
        except FsError as e:
            write_err(io_ctx, f"tee: {e}\n")
            return 1
    return 0


# ---------------------------------------------------------------------------
# basename / dirname / env / which / yes
# ---------------------------------------------------------------------------


def cmd_basename(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        write_err(io_ctx, b"basename: missing operand\n")
        return 1
    name = path_utils.basename(argv[1])
    if len(argv) >= 3:
        suffix = argv[2]
        if name.endswith(suffix) and name != suffix:
            name = name[: -len(suffix)]
    write_out(io_ctx, name + "\n")
    return 0


def cmd_dirname(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        write_err(io_ctx, b"dirname: missing operand\n")
        return 1
    write_out(io_ctx, path_utils.dirname(argv[1]) + "\n")
    return 0


def cmd_env(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    rest_argv: list[str] = []
    extra_env: dict[str, str] = {}
    i = 0
    while i < len(args):
        a = args[i]
        if "=" in a and not a.startswith("-"):
            k, _, v = a.partition("=")
            extra_env[k] = v
            i += 1
            continue
        rest_argv = args[i:]
        break
    for k, v in extra_env.items():
        interp.env.set_var(k, v, exported=True)
    if not rest_argv:
        for k, v in sorted(interp.env.env_dict().items()):
            write_out(io_ctx, f"{k}={v}\n")
        return 0
    return interp._dispatch(rest_argv, io_ctx)


def cmd_which(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for name in argv[1:]:
        if name in interp.builtins:
            write_out(io_ctx, f"{name}: shell builtin\n")
            continue
        if name in interp.commands:
            write_out(io_ctx, f"/usr/bin/{name}\n")
            continue
        rc = 1
    return rc


def cmd_yes(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    text = " ".join(argv[1:]) or "y"
    # In MVP we deliberately produce a single line to avoid infinite output.
    write_out(io_ctx, text + "\n")
    return 0


__all__ = [
    "cmd_basename",
    "cmd_cat",
    "cmd_dirname",
    "cmd_env",
    "cmd_head",
    "cmd_ls",
    "cmd_mkdir",
    "cmd_rmdir",
    "cmd_tail",
    "cmd_tee",
    "cmd_touch",
    "cmd_wc",
    "cmd_which",
    "cmd_yes",
]
