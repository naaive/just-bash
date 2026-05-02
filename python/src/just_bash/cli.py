"""``just-bash`` CLI entry point.

Operates either against a fresh in-memory ``VirtualFs`` (the default) or
against an ``OverlayFs`` rooted at ``--root DIR`` so the sandbox can read
real project files while keeping all writes in memory.

Reads its script from ``-c "..."``, a file argument, or stdin.
"""

from __future__ import annotations

import argparse
import json
import sys

from just_bash.fs.overlay_fs import OverlayFs
from just_bash.fs.vfs import VirtualFs
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.errors import ExitException
from just_bash.interpreter.interpreter import Interpreter
from just_bash.parser.parser import parse


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="just-bash",
        description="Sandboxed bash interpreter (Python port of just-bash)",
    )
    p.add_argument("-c", dest="command", help="execute COMMAND and exit")
    p.add_argument("--json", action="store_true", help="emit stdout/stderr/exitCode as JSON")
    p.add_argument("--print-ast", action="store_true", help="print parsed AST and exit")
    p.add_argument("-e", "--errexit", action="store_true", help="exit on first error")
    p.add_argument(
        "--root",
        default=None,
        help="OverlayFs root: real-FS files become readable; writes stay in memory",
    )
    p.add_argument(
        "--allow-write",
        action="store_true",
        help="permit writes inside the OverlayFs (writes are in-memory regardless)",
    )
    p.add_argument(
        "--allow-symlinks",
        action="store_true",
        help="allow symlink traversal in the OverlayFs (default: deny for safety)",
    )
    p.add_argument(
        "--cwd", default="/home/user/project", help="initial working directory inside the sandbox"
    )
    p.add_argument("script", nargs="?", help="path to a script file (read from stdin if absent)")
    p.add_argument(
        "args", nargs=argparse.REMAINDER, help="positional arguments passed to the script"
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_argparser()
    ns = parser.parse_args(argv)

    if ns.command is not None:
        source = ns.command
    elif ns.script is not None:
        with open(ns.script, encoding="utf-8") as f:
            source = f.read()
    else:
        source = sys.stdin.read()

    if ns.print_ast:
        from dataclasses import asdict, is_dataclass

        def to_dict(obj: object) -> object:
            if is_dataclass(obj) and not isinstance(obj, type):
                return {k: to_dict(v) for k, v in asdict(obj).items()}
            if isinstance(obj, list):
                return [to_dict(v) for v in obj]
            if isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            return obj

        ast = parse(source)
        print(json.dumps(to_dict(ast), indent=2, default=str))
        return 0

    fs: VirtualFs | OverlayFs
    if ns.root is not None:
        fs = OverlayFs(
            ns.root,
            allow_symlinks=ns.allow_symlinks,
            allow_writes=ns.allow_write or True,  # writes are in-memory only
        )
        # Fall back to "/" if the requested cwd doesn't exist under the root.
        try:
            fs.chdir(ns.cwd)
        except OSError:
            fs.chdir("/")
    else:
        vfs = VirtualFs()
        vfs.mkdir(ns.cwd, parents=True, exist_ok=True)
        vfs.chdir(ns.cwd)
        fs = vfs
    env = Environment(
        initial_env={"PATH": "/usr/bin:/bin", "HOME": "/root", "IFS": " \t\n", "PWD": fs.cwd}
    )
    if ns.errexit:
        env.shell_options.add("e")
    interp = Interpreter(fs=fs, env=env)
    if ns.args:
        interp.env.positional = ns.args

    script = parse(source)
    try:
        result = interp.run_script_capture(script)
    except ExitException as e:
        result_code = e.code
        result_stdout = ""
        result_stderr = ""
    else:
        result_code = result.exit_code
        result_stdout = result.stdout
        result_stderr = result.stderr

    if ns.json:
        print(
            json.dumps({"stdout": result_stdout, "stderr": result_stderr, "exitCode": result_code})
        )
    else:
        sys.stdout.write(result_stdout)
        sys.stderr.write(result_stderr)
    return result_code


if __name__ == "__main__":
    sys.exit(main())
