"""Phase-6 commands.

Mostly stubs / lightweight implementations that match the surface bash
scripts expect. Network commands return canned data; archive commands work
against the in-memory VFS.
"""

from __future__ import annotations

import io
import tarfile
import zipfile
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs.vfs import Directory, FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# tar (subset)
# ---------------------------------------------------------------------------


def cmd_tar(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``tar -cf out.tar paths...`` / ``tar -xf in.tar`` / ``tar -tf in.tar``.

    Operates on the VFS. Single-letter flags may be glued (``-cvf``).
    """
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"tar: missing operand\n")
        return 2
    flags = ""
    rest: list[str] = []
    i = 0
    if args[0].startswith("-"):
        flags = args[0].lstrip("-")
        i = 1
    elif args[0] and not args[0].startswith("/") and args[0][0] in "cxtvfz":
        flags = args[0]
        i = 1
    rest = args[i:]
    create = "c" in flags
    extract = "x" in flags
    listing = "t" in flags
    use_file = "f" in flags
    archive: str | None = None
    paths: list[str] = []
    if use_file:
        if not rest:
            write_err(io_ctx, b"tar: no archive named\n")
            return 1
        archive = rest[0]
        paths = rest[1:]
    if create:
        if archive is None:
            write_err(io_ctx, b"tar: -c requires -f FILE\n")
            return 1
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for p in paths:
                _tar_add(interp, tf, p, p)
        try:
            interp.fs.write_file(archive, buf.getvalue())
        except FsError as e:
            write_err(io_ctx, f"tar: {e}\n")
            return 1
        return 0
    if listing or extract:
        if archive is None:
            write_err(io_ctx, b"tar: -t/-x requires -f FILE\n")
            return 1
        try:
            data = interp.fs.read_file(archive)
        except FsError as e:
            write_err(io_ctx, f"tar: {e}\n")
            return 1
        try:
            with tarfile.open(fileobj=io.BytesIO(data), mode="r") as tf:
                for member in tf.getmembers():
                    if listing:
                        write_out(io_ctx, member.name + "\n")
                        continue
                    if member.isdir():
                        interp.fs.mkdir("/" + member.name, parents=True, exist_ok=True)
                    else:
                        f = tf.extractfile(member)
                        content = f.read() if f else b""
                        target = "/" + member.name
                        parent = target.rsplit("/", 1)[0]
                        if parent:
                            interp.fs.mkdir(parent, parents=True, exist_ok=True)
                        interp.fs.write_file(target, content)
        except tarfile.TarError as e:
            write_err(io_ctx, f"tar: {e}\n".encode())
            return 1
        return 0
    write_err(io_ctx, b"tar: must specify one of -c / -t / -x\n")
    return 1


def _tar_add(interp: Interpreter, tf: tarfile.TarFile, path: str, arcname: str) -> None:
    try:
        node = interp.fs.stat(path)
    except FsError:
        return
    if isinstance(node, Directory):
        info = tarfile.TarInfo(name=arcname)
        info.type = tarfile.DIRTYPE
        info.mode = node.mode
        tf.addfile(info)
        try:
            for child in interp.fs.listdir(path):
                _tar_add(
                    interp, tf, path.rstrip("/") + "/" + child, arcname.rstrip("/") + "/" + child
                )
        except FsError:
            pass
        return
    data = interp.fs.read_file(path)
    info = tarfile.TarInfo(name=arcname)
    info.size = len(data)
    info.mode = node.mode
    tf.addfile(info, io.BytesIO(data))


# ---------------------------------------------------------------------------
# zip / unzip (read-only listing + extract; create is minimal)
# ---------------------------------------------------------------------------


def cmd_zip(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) < 3:
        write_err(io_ctx, b"zip: usage: zip OUT.zip PATHS...\n")
        return 2
    out_path = argv[1]
    paths = argv[2:]
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            try:
                node = interp.fs.stat(p)
            except FsError as e:
                write_err(io_ctx, f"zip: {e}\n")
                return 1
            if isinstance(node, Directory):
                for entry in interp.fs.walk(p):
                    dirpath, _dirs, files = entry
                    for f in files:
                        full = dirpath.rstrip("/") + "/" + f if dirpath != "/" else "/" + f
                        zf.writestr(full.lstrip("/"), interp.fs.read_file(full))
            else:
                zf.writestr(p.lstrip("/"), interp.fs.read_file(p))
    interp.fs.write_file(out_path, buf.getvalue())
    return 0


def cmd_unzip(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-l", "-q"})
    except ValueError as e:
        write_err(io_ctx, f"unzip: {e}\n")
        return 2
    if not paths:
        write_err(io_ctx, b"unzip: missing zip file\n")
        return 1
    listing = bool(flags.get("-l"))
    try:
        data = interp.fs.read_file(paths[0])
    except FsError as e:
        write_err(io_ctx, f"unzip: {e}\n")
        return 1
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        write_err(io_ctx, b"unzip: not a zip archive\n")
        return 1
    for info in zf.infolist():
        if listing:
            write_out(io_ctx, info.filename + "\n")
            continue
        target = "/" + info.filename
        if info.filename.endswith("/"):
            interp.fs.mkdir(target, parents=True, exist_ok=True)
            continue
        parent = target.rsplit("/", 1)[0]
        if parent:
            interp.fs.mkdir(parent, parents=True, exist_ok=True)
        interp.fs.write_file(target, zf.read(info))
    return 0


# ---------------------------------------------------------------------------
# Network stubs (sandbox-friendly)
# ---------------------------------------------------------------------------


def cmd_curl(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """Sandboxed ``curl``: emits a placeholder body, never opens a socket."""
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"curl: missing URL\n")
        return 2
    url = args[-1]
    write_err(io_ctx, f"curl: sandbox stub - no network access (would fetch {url})\n".encode())
    return 6  # CURLE_COULDNT_RESOLVE_HOST


def cmd_wget(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    url = args[-1] if args else "-"
    write_err(io_ctx, f"wget: sandbox stub - no network access (would fetch {url})\n".encode())
    return 4  # WGET_NETWORK_ERROR


def cmd_ping(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[-1] if len(argv) > 1 else "localhost"
    write_out(io_ctx, f"PING {target} (sandbox): 0% packet loss\n".encode())
    return 0


def cmd_host(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[-1] if len(argv) > 1 else "localhost"
    write_out(io_ctx, f"{target} has address 127.0.0.1\n".encode())
    return 0


def cmd_dig(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[-1] if len(argv) > 1 else "localhost"
    write_out(io_ctx, f";; ANSWER SECTION:\n{target}.\t0\tIN\tA\t127.0.0.1\n".encode())
    return 0


def cmd_nslookup(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[-1] if len(argv) > 1 else "localhost"
    write_out(
        io_ctx,
        f"Server:\t127.0.0.53\nAddress:\t127.0.0.53#53\n\n"
        f"Name:\t{target}\nAddress: 127.0.0.1\n".encode(),
    )
    return 0


def cmd_ip(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] in ("a", "addr", "address"):
        write_out(
            io_ctx,
            b"1: lo: <LOOPBACK,UP> inet 127.0.0.1/8 scope host lo\n",
        )
        return 0
    if args and args[0] in ("link", "l"):
        write_out(io_ctx, b"1: lo: <LOOPBACK,UP>\n")
        return 0
    return 0


def cmd_ifconfig(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"lo: flags=73<UP,LOOPBACK,RUNNING>\n        inet 127.0.0.1\n")
    return 0


# ---------------------------------------------------------------------------
# Other small commands
# ---------------------------------------------------------------------------


def cmd_lsof(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"COMMAND  PID USER FD TYPE  DEVICE SIZE NODE NAME\n")
    return 0


def cmd_ps(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"  PID TTY          TIME CMD\n    1 ?        00:00:00 just-bash\n")
    return 0


def cmd_top(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"top - sandbox stub: no live process listing\n")
    return 0


def cmd_watch(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``watch CMD`` runs CMD once in the sandbox (no live refresh)."""
    args = argv[1:]
    while args and args[0].startswith("-"):
        # Skip flags like ``-n SECS`` / ``-d``.
        if args[0] in ("-n", "-d") and len(args) > 1:
            args = args[2:]
            continue
        args = args[1:]
    if not args:
        write_err(io_ctx, b"watch: missing command\n")
        return 1
    return interp._dispatch(args, io_ctx)


def cmd_du(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``du`` - report disk usage in 1024-byte blocks."""
    try:
        flags, paths = parse_flags(argv, boolean={"-h", "-a", "-s", "-c"})
    except ValueError as e:
        write_err(io_ctx, f"du: {e}\n")
        return 2
    if not paths:
        paths = [interp.fs.cwd]
    for p in paths:
        total = _du_size(interp, p)
        if flags.get("-h"):
            write_out(io_ctx, f"{_human(total)}\t{p}\n")
        else:
            write_out(io_ctx, f"{(total + 1023) // 1024}\t{p}\n")
    return 0


def _du_size(interp: Interpreter, path: str) -> int:
    try:
        node = interp.fs.stat(path)
    except FsError:
        return 0
    if isinstance(node, Directory):
        total = 0
        try:
            for child in interp.fs.listdir(path):
                total += _du_size(
                    interp, path.rstrip("/") + "/" + child if path != "/" else "/" + child
                )
        except FsError:
            pass
        return total
    return getattr(node, "size", 0)


def _human(n: int) -> str:
    units = ["B", "K", "M", "G", "T"]
    f = float(n)
    for u in units:
        if f < 1024:
            return f"{f:.1f}{u}".rstrip("0").rstrip(".")
        f /= 1024
    return f"{f:.1f}P"


def cmd_df(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    del argv
    write_out(
        io_ctx,
        b"Filesystem     1K-blocks    Used Available Use% Mounted on\n"
        b"sandbox          1048576       0   1048576   0% /\n",
    )
    return 0


def cmd_free(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"              total        used        free\n"
        b"Mem:        1048576      131072      917504\n",
    )
    return 0


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def cmd_pr(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    write_out(io_ctx, data.decode("utf-8", errors="replace"))
    return rc


def cmd_fmt(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, valued={"-w"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"fmt: {e}\n")
        return 2
    width = int(flags.get("-w", 75))
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    out: list[str] = []
    for paragraph in text.split("\n\n"):
        words = paragraph.split()
        line = ""
        for w in words:
            if not line:
                line = w
            elif len(line) + 1 + len(w) > width:
                out.append(line)
                line = w
            else:
                line += " " + w
        if line:
            out.append(line)
        out.append("")
    write_out(io_ctx, "\n".join(out).rstrip("\n") + "\n")
    return rc


def cmd_look(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``look PREFIX [FILE]`` - emit lines starting with PREFIX (sorted)."""
    if len(argv) < 2:
        write_err(io_ctx, b"look: missing prefix\n")
        return 2
    prefix = argv[1]
    paths = argv[2:]
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    lines = sorted(line for line in text.splitlines() if line.startswith(prefix))
    write_out(io_ctx, "\n".join(lines) + ("\n" if lines else ""))
    return rc


def cmd_tsort(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``tsort`` - topological sort of whitespace-separated edges."""
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    tokens = text.split()
    edges: list[tuple[str, str]] = []
    nodes: list[str] = []
    seen_node: set[str] = set()
    for i in range(0, len(tokens) - 1, 2):
        a, b = tokens[i], tokens[i + 1]
        edges.append((a, b))
        for n in (a, b):
            if n not in seen_node:
                seen_node.add(n)
                nodes.append(n)
    # Kahn's algorithm.
    indeg = {n: 0 for n in nodes}
    succ: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        succ[a].append(b)
        indeg[b] += 1
    ready = [n for n in nodes if indeg[n] == 0]
    out: list[str] = []
    while ready:
        cur = ready.pop(0)
        out.append(cur)
        for s in succ[cur]:
            indeg[s] -= 1
            if indeg[s] == 0:
                ready.append(s)
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return rc


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


def cmd_yes_inf(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``yes`` that bounds output to keep tests sane."""
    text = " ".join(argv[1:]) or "y"
    out = ((text + "\n") * 1024)[:1024]
    write_out(io_ctx, out)
    return 0


def cmd_clear(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"\x1b[H\x1b[2J")
    return 0


def cmd_reset(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"\x1b\x63")
    return 0


def cmd_tput(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``tput`` recognises a tiny subset of capabilities (cols / lines)."""
    if len(argv) >= 2 and argv[1] == "cols":
        write_out(io_ctx, b"80\n")
        return 0
    if len(argv) >= 2 and argv[1] == "lines":
        write_out(io_ctx, b"24\n")
        return 0
    return 0


def cmd_stty(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"speed 38400 baud; line = 0;\n")
    return 0


def cmd_pwd_alias(interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, (interp.fs.cwd + "\n").encode())
    return 0


__all__ = [
    "cmd_clear",
    "cmd_curl",
    "cmd_df",
    "cmd_dig",
    "cmd_du",
    "cmd_fmt",
    "cmd_free",
    "cmd_host",
    "cmd_ifconfig",
    "cmd_ip",
    "cmd_look",
    "cmd_lsof",
    "cmd_nslookup",
    "cmd_ping",
    "cmd_pr",
    "cmd_ps",
    "cmd_pwd_alias",
    "cmd_reset",
    "cmd_stty",
    "cmd_tar",
    "cmd_top",
    "cmd_tput",
    "cmd_tsort",
    "cmd_unzip",
    "cmd_watch",
    "cmd_wget",
    "cmd_yes_inf",
    "cmd_zip",
]
