"""Phase-3 commands: base64, hexdump, xxd, column, shuf, tac, split, join,
hostname, whoami, id, uname, getent, file, and a tiny ``jq`` subset."""

from __future__ import annotations

import base64 as _base64
import json
import random
import re
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# base64
# ---------------------------------------------------------------------------


def cmd_base64(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-d", "--decode", "-i"})
    except ValueError as e:
        write_err(io_ctx, f"base64: {e}\n")
        return 2
    decode = bool(flags.get("-d") or flags.get("--decode"))
    data, rc = read_input(interp, io_ctx, paths)
    if decode:
        try:
            out = _base64.b64decode(data, validate=False)
        except Exception:
            write_err(io_ctx, b"base64: invalid input\n")
            return 1
        io_ctx.stdout.write(out)
    else:
        encoded = _base64.b64encode(data).decode("ascii")
        # Real base64 wraps at 76 chars by default.
        wrapped = "\n".join(encoded[i : i + 76] for i in range(0, len(encoded), 76))
        write_out(io_ctx, wrapped + "\n")
    return rc


# ---------------------------------------------------------------------------
# hexdump / xxd
# ---------------------------------------------------------------------------


def cmd_hexdump(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-C", "-c", "-x"})
    except ValueError as e:
        write_err(io_ctx, f"hexdump: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    canonical = bool(flags.get("-C"))
    out: list[str] = []
    if canonical:
        for offset in range(0, len(data), 16):
            chunk = data[offset : offset + 16]
            hexpart = " ".join(f"{b:02x}" for b in chunk).ljust(48)
            ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            out.append(f"{offset:08x}  {hexpart}  |{ascii_part}|")
        out.append(f"{len(data):08x}")
    else:
        for offset in range(0, len(data), 16):
            chunk = data[offset : offset + 16]
            words = [
                f"{int.from_bytes(chunk[i : i + 2], 'little'):04x}" for i in range(0, len(chunk), 2)
            ]
            out.append(f"{offset:07x} " + " ".join(words))
        out.append(f"{len(data):07x}")
    write_out(io_ctx, "\n".join(out) + "\n")
    return rc


def cmd_xxd(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-r", "-p"})
    except ValueError as e:
        write_err(io_ctx, f"xxd: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    if flags.get("-r"):
        # Reverse: parse plain hex back to bytes.
        text = data.decode("utf-8", errors="replace")
        hex_only = "".join(c for c in text if c in "0123456789abcdefABCDEF")
        try:
            io_ctx.stdout.write(bytes.fromhex(hex_only))
        except ValueError:
            return 1
        return rc
    if flags.get("-p"):
        write_out(io_ctx, data.hex() + "\n")
        return rc
    out: list[str] = []
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        hexpart = " ".join(
            f"{b:02x}{chunk[i + 1]:02x}" if i + 1 < len(chunk) else f"{b:02x}  "
            for i, b in enumerate(chunk[::2])
        )
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        out.append(f"{offset:08x}: {hexpart.ljust(40)}  {ascii_part}")
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return rc


# ---------------------------------------------------------------------------
# column
# ---------------------------------------------------------------------------


def cmd_column(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-s", "-o"}, boolean={"-x", "-t"})
    except ValueError as e:
        write_err(io_ctx, f"column: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    sep = str(flags.get("-s", " \t"))
    out_sep = str(flags.get("-o", "  "))
    lines = [ln for ln in text.split("\n") if ln]
    rows = [_split_any(ln, sep) for ln in lines]
    if not rows:
        return rc
    cols = max(len(r) for r in rows)
    widths = [0] * cols
    for r in rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))
    out: list[str] = []
    for r in rows:
        padded = [r[i].ljust(widths[i]) if i < len(r) else "".ljust(widths[i]) for i in range(cols)]
        out.append(out_sep.join(padded).rstrip())
    write_out(io_ctx, "\n".join(out) + "\n")
    return rc


def _split_any(text: str, separators: str) -> list[str]:
    if not separators:
        return text.split()
    parts: list[str] = []
    cur: list[str] = []
    for ch in text:
        if ch in separators:
            if cur:
                parts.append("".join(cur))
                cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


# ---------------------------------------------------------------------------
# shuf / tac
# ---------------------------------------------------------------------------


def cmd_shuf(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-n", "--head-count"}, boolean={"-r"})
    except ValueError as e:
        write_err(io_ctx, f"shuf: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    rng = random.Random()
    rng.shuffle(lines)
    if "-n" in flags or "--head-count" in flags:
        n = int(flags.get("-n", flags.get("--head-count", 0)))
        lines = lines[:n]
    write_out(io_ctx, "\n".join(lines) + ("\n" if lines else ""))
    return rc


def cmd_tac(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing = text.endswith("\n")
    if trailing:
        lines = lines[:-1]
    out = "\n".join(reversed(lines)) + ("\n" if lines else "")
    write_out(io_ctx, out)
    return rc


# ---------------------------------------------------------------------------
# split / join
# ---------------------------------------------------------------------------


def cmd_split(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, args = parse_flags(argv, valued={"-l", "-b", "-a"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"split: {e}\n")
        return 2
    if args:
        try:
            data = interp.fs.read_file(args[0])
        except FsError as e:
            write_err(io_ctx, f"split: {e}\n")
            return 1
        prefix = args[1] if len(args) > 1 else "x"
    else:
        data = io_ctx.stdin
        prefix = "x"
    n_lines = int(flags.get("-l", 1000)) if "-l" not in flags or flags.get("-l") else 1000
    if "-l" in flags:
        n_lines = int(flags["-l"])
    text = data.decode("utf-8", errors="replace")
    lines = text.splitlines(keepends=True)
    suffix = "aa"
    chunks = [lines[i : i + n_lines] for i in range(0, len(lines), n_lines)]
    for chunk in chunks:
        interp.fs.write_file(prefix + suffix, "".join(chunk))
        # increment two-letter suffix
        if suffix[1] != "z":
            suffix = suffix[0] + chr(ord(suffix[1]) + 1)
        else:
            suffix = chr(ord(suffix[0]) + 1) + "a"
    return 0


def cmd_join(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-t", "-1", "-2"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"join: {e}\n")
        return 2
    if len(paths) != 2:
        write_err(io_ctx, b"join: expected 2 file operands\n")
        return 2
    sep = str(flags.get("-t", " "))
    k1 = int(flags.get("-1", 1)) - 1
    k2 = int(flags.get("-2", 1)) - 1
    try:
        a = interp.fs.read_text(paths[0]).splitlines()
        b = interp.fs.read_text(paths[1]).splitlines()
    except FsError as e:
        write_err(io_ctx, f"join: {e}\n")
        return 1
    out: list[str] = []
    for line_a in a:
        fa = line_a.split(sep) if sep != " " else line_a.split()
        if k1 >= len(fa):
            continue
        key = fa[k1]
        for line_b in b:
            fb = line_b.split(sep) if sep != " " else line_b.split()
            if k2 < len(fb) and fb[k2] == key:
                rest_a = fa[:k1] + fa[k1 + 1 :]
                rest_b = fb[:k2] + fb[k2 + 1 :]
                row = (
                    sep.join([key, *rest_a, *rest_b])
                    if sep != " "
                    else " ".join([key, *rest_a, *rest_b])
                )
                out.append(row)
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return 0


# ---------------------------------------------------------------------------
# hostname / whoami / id / uname / getent / file
# ---------------------------------------------------------------------------


def cmd_hostname(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, (interp.env.get("HOSTNAME") or "sandbox") + "\n")
    return 0


def cmd_whoami(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, (interp.env.get("USER") or "user") + "\n")
    return 0


def cmd_id(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    user = interp.env.get("USER") or "user"
    if len(argv) > 1 and argv[1] in ("-u", "--user"):
        write_out(io_ctx, "1000\n")
        return 0
    if len(argv) > 1 and argv[1] in ("-g", "--group"):
        write_out(io_ctx, "1000\n")
        return 0
    if len(argv) > 1 and argv[1] in ("-un", "-nu"):
        write_out(io_ctx, user + "\n")
        return 0
    write_out(io_ctx, f"uid=1000({user}) gid=1000({user}) groups=1000({user})\n")
    return 0


def cmd_uname(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    info = {
        "kernel": "Linux",
        "node": "sandbox",
        "release": "0.0.0-sandbox",
        "version": "#1 SMP",
        "machine": "x86_64",
        "os": "GNU/Linux",
    }
    if len(argv) == 1:
        write_out(io_ctx, info["kernel"] + "\n")
        return 0
    parts: list[str] = []
    for a in argv[1:]:
        if a == "-a":
            parts = list(info.values())
            break
        if a in ("-s", "--kernel-name"):
            parts.append(info["kernel"])
        elif a in ("-n", "--nodename"):
            parts.append(info["node"])
        elif a in ("-r", "--kernel-release"):
            parts.append(info["release"])
        elif a in ("-v", "--kernel-version"):
            parts.append(info["version"])
        elif a in ("-m", "--machine"):
            parts.append(info["machine"])
        elif a in ("-o", "--operating-system"):
            parts.append(info["os"])
    write_out(io_ctx, " ".join(parts) + "\n")
    return 0


def cmd_getent(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 2:
        write_err(io_ctx, b"getent: missing database\n")
        return 1
    db = argv[1]
    if db == "passwd":
        write_out(io_ctx, "user:x:1000:1000:user:/home/user:/bin/bash\n")
        return 0
    if db == "group":
        write_out(io_ctx, "user:x:1000:\n")
        return 0
    if db == "hosts":
        write_out(io_ctx, "127.0.0.1\tlocalhost\n")
        return 0
    write_err(io_ctx, f"getent: unsupported database {db}\n".encode())
    return 2


def cmd_file(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    rc = 0
    for path in argv[1:]:
        try:
            data = interp.fs.read_file(path)
        except FsError as e:
            write_err(io_ctx, f"file: {e}\n")
            rc = 1
            continue
        # Very lightweight detection.
        if not data:
            kind = "empty"
        elif b"\x00" in data[:8192]:
            kind = "data"
        else:
            try:
                data.decode("utf-8")
                kind = "ASCII text" if all(b < 128 for b in data[:1024]) else "UTF-8 text"
            except UnicodeDecodeError:
                kind = "data"
        write_out(io_ctx, f"{path}: {kind}\n")
    return rc


# ---------------------------------------------------------------------------
# jq (tiny subset)
# ---------------------------------------------------------------------------


def cmd_jq(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """Tiny jq: supports ``.``, ``.field``, ``.field.sub``, ``.[N]``, ``length``."""
    try:
        flags, args = parse_flags(argv, boolean={"-r", "-c", "-n"})
    except ValueError as e:
        write_err(io_ctx, f"jq: {e}\n")
        return 2
    if not args:
        write_err(io_ctx, b"jq: missing filter\n")
        return 2
    filter_expr = args[0]
    files = args[1:]
    data, rc = read_input(interp, io_ctx, files)
    text = data.decode("utf-8", errors="replace").strip()
    if not text:
        return rc
    try:
        value: object = json.loads(text)
    except json.JSONDecodeError as e:
        write_err(io_ctx, f"jq: parse error: {e}\n".encode())
        return 2
    try:
        result = _jq_apply(value, filter_expr)
    except Exception as e:
        write_err(io_ctx, f"jq: {e}\n".encode())
        return 5
    raw = bool(flags.get("-r"))
    compact = bool(flags.get("-c"))
    write_out(io_ctx, _jq_format(result, raw=raw, compact=compact) + "\n")
    return 0


def _jq_apply(value: object, expr: str) -> object:
    expr = expr.strip()
    if expr in (".", ""):
        return value
    if expr == "length":
        if isinstance(value, list | str):
            return len(value)
        if isinstance(value, dict):
            return len(value)
        if value is None:
            return 0
        raise ValueError(f"length not defined for {type(value).__name__}")
    if expr == "keys":
        if isinstance(value, dict):
            return sorted(value.keys())
        raise ValueError("keys requires an object")
    # Path expression: ``.a.b[0].c`` etc.
    cur = value
    i = 0
    if expr.startswith("."):
        i = 1
    while i < len(expr):
        if expr[i] == ".":
            i += 1
            continue
        if expr[i] == "[":
            close = expr.index("]", i)
            inside = expr[i + 1 : close]
            i = close + 1
            if inside == "":
                if not isinstance(cur, list):
                    raise ValueError(".[]: not an array")
                return cur
            try:
                idx = int(inside)
            except ValueError as e:
                raise ValueError(f"non-integer index {inside!r}") from e
            if not isinstance(cur, list):
                raise ValueError("index applied to non-array")
            if not -len(cur) <= idx < len(cur):
                return None
            cur = cur[idx]
            continue
        # Field name.
        m = re.match(r"[A-Za-z_][A-Za-z0-9_]*", expr[i:])
        if m is None:
            raise ValueError(f"unexpected character at {i}: {expr[i]!r}")
        name = m.group(0)
        i += len(name)
        if not isinstance(cur, dict):
            raise ValueError(f"cannot index {type(cur).__name__} with .{name}")
        cur = cur.get(name)
    return cur


def _jq_format(value: object, *, raw: bool, compact: bool) -> str:
    if raw and isinstance(value, str):
        return value
    if compact:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(value, indent=2, ensure_ascii=False)


__all__ = [
    "cmd_base64",
    "cmd_column",
    "cmd_file",
    "cmd_getent",
    "cmd_hexdump",
    "cmd_hostname",
    "cmd_id",
    "cmd_join",
    "cmd_jq",
    "cmd_shuf",
    "cmd_split",
    "cmd_tac",
    "cmd_uname",
    "cmd_whoami",
    "cmd_xxd",
]
