"""More commands: xargs, seq, expr, sleep, date, paste, comm, diff, md5sum,
realpath, stat, true/false-style helpers."""

from __future__ import annotations

import datetime
import difflib
import hashlib
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, write_err, write_out
from just_bash.fs import path_utils
from just_bash.fs.vfs import Directory, File, FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# seq
# ---------------------------------------------------------------------------


def cmd_seq(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``seq LAST`` / ``seq FIRST LAST`` / ``seq FIRST INC LAST``."""
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"seq: missing operand\n")
        return 1
    try:
        nums = [int(a) for a in args]
    except ValueError:
        write_err(io_ctx, b"seq: non-integer arguments not supported in MVP\n")
        return 1
    if len(nums) == 1:
        first, inc, last = 1, 1, nums[0]
    elif len(nums) == 2:
        first, inc, last = nums[0], 1, nums[1]
    elif len(nums) == 3:
        first, inc, last = nums[0], nums[1], nums[2]
    else:
        write_err(io_ctx, b"seq: too many arguments\n")
        return 1
    if inc == 0:
        write_err(io_ctx, b"seq: increment must not be 0\n")
        return 1
    if (inc > 0 and first > last) or (inc < 0 and first < last):
        return 0
    out: list[str] = []
    n = first
    while (inc > 0 and n <= last) or (inc < 0 and n >= last):
        out.append(str(n))
        n += inc
    write_out(io_ctx, "\n".join(out) + "\n")
    return 0


# ---------------------------------------------------------------------------
# expr
# ---------------------------------------------------------------------------


def cmd_expr(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``expr EXPR`` - tiny expression evaluator. Supports +, -, *, /, %, =, !=, <, <=, >, >=, length, substr."""
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"expr: syntax error\n")
        return 2
    if args[0] == "length" and len(args) == 2:
        write_out(io_ctx, str(len(args[1])) + "\n")
        return 0
    if args[0] == "substr" and len(args) == 4:
        try:
            pos = int(args[2])
            length = int(args[3])
        except ValueError:
            return 2
        s = args[1]
        write_out(io_ctx, s[max(pos - 1, 0) : max(pos - 1, 0) + length] + "\n")
        return 0
    if len(args) != 3:
        write_err(io_ctx, b"expr: only `A OP B` supported in MVP\n")
        return 2
    a, op, b = args
    if op in ("+", "-", "*", "/", "%"):
        try:
            ai, bi = int(a), int(b)
        except ValueError:
            return 2
        if op == "+":
            v = ai + bi
        elif op == "-":
            v = ai - bi
        elif op == "*":
            v = ai * bi
        elif op == "/":
            if bi == 0:
                write_err(io_ctx, b"expr: division by zero\n")
                return 2
            v = ai // bi
        else:
            v = ai % bi
        write_out(io_ctx, str(v) + "\n")
        return 0 if v != 0 else 1
    if op in ("=", "!=", "<", "<=", ">", ">="):
        try:
            ai, bi = int(a), int(b)
            cmp = (
                ai == bi
                if op == "="
                else ai != bi
                if op == "!="
                else ai < bi
                if op == "<"
                else ai <= bi
                if op == "<="
                else ai > bi
                if op == ">"
                else ai >= bi
            )
        except ValueError:
            cmp = (
                a == b
                if op == "="
                else a != b
                if op == "!="
                else a < b
                if op == "<"
                else a <= b
                if op == "<="
                else a > b
                if op == ">"
                else a >= b
            )
        write_out(io_ctx, ("1" if cmp else "0") + "\n")
        return 0 if cmp else 1
    write_err(io_ctx, f"expr: unsupported operator {op!r}\n".encode())
    return 2


# ---------------------------------------------------------------------------
# sleep
# ---------------------------------------------------------------------------


def cmd_sleep(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """No-op sleep. The sandbox is deterministic so we don't actually wait."""
    if len(argv) < 2:
        write_err(io_ctx, b"sleep: missing operand\n")
        return 1
    try:
        float(argv[1].rstrip("smhd"))
    except ValueError:
        write_err(io_ctx, b"sleep: invalid time interval\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------


def cmd_date(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``date [+FORMAT]`` - print current date/time using POSIX format codes."""
    fmt = "%a %b %e %H:%M:%S %Z %Y"
    for a in argv[1:]:
        if a.startswith("+"):
            fmt = a[1:]
            break
    now = datetime.datetime.now()
    write_out(io_ctx, now.strftime(fmt) + "\n")
    return 0


# ---------------------------------------------------------------------------
# paste
# ---------------------------------------------------------------------------


def cmd_paste(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``paste FILE...`` - merge corresponding lines, separated by tab."""
    try:
        flags, paths = parse_flags(argv, valued={"-d"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"paste: {e}\n")
        return 2
    delim = str(flags.get("-d", "\t"))
    if not paths:
        data = io_ctx.stdin.decode("utf-8", errors="replace").split("\n")
        if data and data[-1] == "":
            data = data[:-1]
        write_out(io_ctx, "\n".join(data) + ("\n" if data else ""))
        return 0
    columns: list[list[str]] = []
    for p in paths:
        if p == "-":
            data = io_ctx.stdin.decode("utf-8", errors="replace").split("\n")
        else:
            try:
                data = interp.fs.read_text(p).split("\n")
            except FsError as e:
                write_err(io_ctx, f"paste: {e}\n")
                return 1
        if data and data[-1] == "":
            data = data[:-1]
        columns.append(data)
    n = max((len(c) for c in columns), default=0)
    out: list[str] = []
    for i in range(n):
        row = [c[i] if i < len(c) else "" for c in columns]
        out.append(delim.join(row))
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return 0


# ---------------------------------------------------------------------------
# comm
# ---------------------------------------------------------------------------


def cmd_comm(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``comm FILE1 FILE2`` - select / reject lines unique to or common in two sorted files."""
    try:
        flags, paths = parse_flags(argv, boolean={"-1", "-2", "-3"})
    except ValueError as e:
        write_err(io_ctx, f"comm: {e}\n")
        return 2
    if len(paths) != 2:
        write_err(io_ctx, b"comm: expected 2 file operands\n")
        return 1
    suppress_1 = bool(flags.get("-1"))
    suppress_2 = bool(flags.get("-2"))
    suppress_3 = bool(flags.get("-3"))
    contents: list[list[str]] = []
    for p in paths:
        try:
            text = (
                io_ctx.stdin.decode("utf-8", errors="replace")
                if p == "-"
                else interp.fs.read_text(p)
            )
        except FsError as e:
            write_err(io_ctx, f"comm: {e}\n")
            return 1
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]
        contents.append(lines)
    a_lines, b_lines = contents
    set_a = set(a_lines)
    set_b = set(b_lines)
    out: list[str] = []
    for line in sorted(set_a | set_b):
        in_a, in_b = line in set_a, line in set_b
        if in_a and in_b:
            if not suppress_3:
                out.append("\t\t" + line)
        elif in_a:
            if not suppress_1:
                out.append(line)
        elif in_b and not suppress_2:
            out.append("\t" + line)
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return 0


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def cmd_diff(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``diff FILE1 FILE2`` - simple unified-diff output."""
    try:
        flags, paths = parse_flags(argv, boolean={"-u", "-q"})
    except ValueError as e:
        write_err(io_ctx, f"diff: {e}\n")
        return 2
    if len(paths) != 2:
        write_err(io_ctx, b"diff: expected 2 file operands\n")
        return 2
    a, b = paths
    try:
        ta = interp.fs.read_text(a).splitlines(keepends=True)
        tb = interp.fs.read_text(b).splitlines(keepends=True)
    except FsError as e:
        write_err(io_ctx, f"diff: {e}\n")
        return 2
    if ta == tb:
        return 0
    if flags.get("-q"):
        write_out(io_ctx, f"Files {a} and {b} differ\n")
        return 1
    if flags.get("-u"):
        diff = difflib.unified_diff(ta, tb, fromfile=a, tofile=b, lineterm="")
    else:
        diff = difflib.context_diff(ta, tb, fromfile=a, tofile=b, lineterm="")
    write_out(io_ctx, "\n".join(diff) + "\n")
    return 1


# ---------------------------------------------------------------------------
# md5sum / sha1sum / sha256sum
# ---------------------------------------------------------------------------


def _hash_cmd(algo: str):
    def cmd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
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
                    write_err(io_ctx, f"{algo}sum: {e}\n")
                    rc = 1
        for label, data in targets:
            h = hashlib.new(algo)
            h.update(data)
            write_out(io_ctx, f"{h.hexdigest()}  {label}\n")
        return rc

    return cmd


cmd_md5sum = _hash_cmd("md5")
cmd_sha1sum = _hash_cmd("sha1")
cmd_sha256sum = _hash_cmd("sha256")


# ---------------------------------------------------------------------------
# realpath
# ---------------------------------------------------------------------------


def cmd_realpath(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for arg in argv[1:]:
        target = path_utils.resolve(interp.fs.cwd, arg)
        if not interp.fs.exists(target):
            write_err(io_ctx, f"realpath: {target}: No such file or directory\n")
            rc = 1
            continue
        write_out(io_ctx, target + "\n")
    return rc


# ---------------------------------------------------------------------------
# stat
# ---------------------------------------------------------------------------


def cmd_stat(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for path in argv[1:]:
        try:
            node = interp.fs.stat(path)
        except FsError as e:
            write_err(io_ctx, f"stat: {e}\n")
            rc = 1
            continue
        kind = "directory" if isinstance(node, Directory) else "regular file"
        size = node.size if isinstance(node, File) else 0
        write_out(
            io_ctx,
            f"  File: {path}\n"
            f"  Size: {size}\tBlocks: {(size + 511) // 512}\tIO Block: 4096\t{kind}\n"
            f"Access: ({node.mode:04o}/-)\n",
        )
    return rc


# ---------------------------------------------------------------------------
# xargs
# ---------------------------------------------------------------------------


def cmd_xargs(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``xargs CMD [ARG...]`` - run CMD with stdin items appended as args."""
    try:
        flags, rest = parse_flags(argv, boolean={"-r", "-0", "-t"}, valued={"-n", "-I"})
    except ValueError as e:
        write_err(io_ctx, f"xargs: {e}\n")
        return 2
    if not rest:
        write_err(io_ctx, b"xargs: missing utility\n")
        return 2
    cmd_argv = rest
    text = io_ctx.stdin.decode("utf-8", errors="replace")
    items = text.split("\0") if flags.get("-0") else text.split()
    items = [i for i in items if i]
    if flags.get("-r") and not items:
        return 0
    rc = 0
    if "-I" in flags:
        placeholder = str(flags["-I"])
        for item in items:
            sub_argv = [a.replace(placeholder, item) for a in cmd_argv]
            rc = max(rc, interp._dispatch(sub_argv, io_ctx))
        return rc
    if "-n" in flags:
        n = int(flags["-n"])
        for i in range(0, len(items), n):
            sub_argv = [*cmd_argv, *items[i : i + n]]
            rc = max(rc, interp._dispatch(sub_argv, io_ctx))
        return rc
    sub_argv = [*cmd_argv, *items]
    return interp._dispatch(sub_argv, io_ctx)


__all__ = [
    "cmd_comm",
    "cmd_date",
    "cmd_diff",
    "cmd_expr",
    "cmd_md5sum",
    "cmd_paste",
    "cmd_realpath",
    "cmd_seq",
    "cmd_sha1sum",
    "cmd_sha256sum",
    "cmd_sleep",
    "cmd_stat",
    "cmd_xargs",
]
