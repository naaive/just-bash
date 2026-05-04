"""Script-driven spec-test runner.

Each ``*.test.sh`` file in ``tests/spec/scripts/`` is executed both with
real ``bash`` and with ``just-bash-py`` (against a fresh ``VirtualFs``).
The runner asserts both produce identical stdout / stderr / exit-code.

Why a separate harness from ``tests/comparison/``: comparison tests are
pinned snapshots committed alongside the test (host-independent). Spec
tests run live against the host bash and surface any drift immediately.

Many scripts here use bash 4+ features (``declare -A``, ``mapfile``,
``${var@Q}``, ``${var,,}`` etc.). macOS still ships bash 3.2 as
``/bin/bash``; on those hosts we prefer a Homebrew-installed bash 5.x
when present, otherwise the whole module is skipped.

Run with::

    pytest tests/spec
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
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


# Candidate bash paths in order of preference. Homebrew installs bash 5+
# at these locations on macOS; macOS's system ``/bin/bash`` is 3.2 and
# can't run scripts that use ``declare -A`` / ``mapfile`` / ``${var@Q}``.
_BASH_CANDIDATES = (
    "/opt/homebrew/bin/bash",  # macOS arm64 brew
    "/usr/local/bin/bash",  # macOS x86_64 brew, common Linux installs
)


@lru_cache(maxsize=1)
def _find_modern_bash() -> str | None:
    """Return a path to bash >= 4.0 or ``None`` if none is available."""
    paths: list[str] = []
    for candidate in _BASH_CANDIDATES:
        if Path(candidate).is_file():
            paths.append(candidate)
    found = shutil.which("bash")
    if found and found not in paths:
        paths.append(found)
    for path in paths:
        if _bash_major_version(path) >= 4:
            return path
    return None


def _bash_major_version(path: str) -> int:
    try:
        out = subprocess.run(
            [path, "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        ).stdout.decode("utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError):
        return 0
    m = re.search(r"version (\d+)", out)
    return int(m.group(1)) if m else 0


def run_bash(script_path: Path) -> Capture:
    bash = _find_modern_bash()
    if bash is None:
        raise RuntimeError("bash >= 4 not found")
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
    if os.environ.get("SKIP_SPEC", "") not in ("", "0", "false"):
        return True
    # No bash 4+ on this host — the live-comparison harness can't run.
    return _find_modern_bash() is None
