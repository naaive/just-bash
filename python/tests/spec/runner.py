"""Script-driven spec-test runner.

Each ``*.test.sh`` file in ``tests/spec/scripts/`` is executed both with
real ``bash`` and with ``just-bash-py`` (against a fresh ``VirtualFs``).
The runner asserts both produce identical stdout / stderr / exit-code.

Why a separate harness from ``tests/comparison/``: comparison tests are
pinned snapshots committed alongside the test (host-independent). Spec
tests run live against the host bash and surface any drift immediately —
they're meant to be run by humans during development, not in CI on
arbitrary machines.

Run with::

    pytest tests/spec
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from just_bash.fs.vfs import VirtualFs
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.interpreter import Interpreter
from just_bash.parser.parser import parse

SCRIPTS_DIR = Path(__file__).parent / "scripts"


@dataclass(slots=True)
class Capture:
    stdout: str
    stderr: str
    exit_code: int


def discover() -> list[Path]:
    return sorted(SCRIPTS_DIR.glob("*.test.sh"))


def run_bash(script_path: Path) -> Capture:
    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("bash not on PATH")
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(
            [bash, str(script_path)],
            cwd=tmp,
            capture_output=True,
            timeout=10,
            env={"LC_ALL": "C", "LANG": "C", "PATH": "/usr/bin:/bin", "HOME": tmp, "PWD": tmp},
            check=False,
        )
    return Capture(
        stdout=result.stdout.decode("utf-8", errors="replace"),
        stderr=result.stderr.decode("utf-8", errors="replace"),
        exit_code=result.returncode,
    )


def run_just_bash(script_path: Path) -> Capture:
    fs = VirtualFs()
    fs.mkdir("/work", parents=True, exist_ok=True)
    fs.chdir("/work")
    env = Environment(
        initial_env={"PATH": "/usr/bin:/bin", "HOME": "/work", "PWD": "/work", "IFS": " \t\n"}
    )
    interp = Interpreter(fs=fs, env=env)
    source = script_path.read_text()
    result = interp.run_script_capture(parse(source))
    return Capture(stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code)


def assert_equivalent(name: str, ours: Capture, theirs: Capture) -> None:
    if ours == theirs:
        return
    raise AssertionError(
        f"spec mismatch for {name}\n"
        f"--- bash ---\n"
        f"stdout={theirs.stdout!r}\nstderr={theirs.stderr!r}\nexit={theirs.exit_code}\n"
        f"--- just-bash-py ---\n"
        f"stdout={ours.stdout!r}\nstderr={ours.stderr!r}\nexit={ours.exit_code}\n"
    )


def is_skipped() -> bool:
    return os.environ.get("SKIP_SPEC", "") not in ("", "0", "false")
