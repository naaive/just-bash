"""Helper module for the spec-test harness.

Discovers the ``*.test.sh`` files under ``tests/spec/scripts/`` and the
best available ``bash`` binary on the host. The actual subprocess
invocation lives next door in ``test_spec.py`` so the production code
in this package stays free of subprocess machinery.

Why a separate harness from ``tests/comparison/``: comparison tests are
pinned snapshots committed alongside the test (host-independent). Spec
tests run live against the host bash and surface any drift immediately.

Many scripts here use bash 4+ features (``declare -A``, ``mapfile``,
``${var@Q}``, ``${var,,}`` etc.). macOS still ships bash 3.2 as
``/bin/bash``; on those hosts we prefer a Homebrew-installed bash 5.x
when present, otherwise the whole module is skipped.
"""

from __future__ import annotations

import os
import shutil
import sys
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
def find_modern_bash() -> str | None:
    """Return a path to bash >= 4.0 or ``None`` if none is available.

    Detection is purely path-based:

    - Homebrew installs bash 5.x at the canonical paths in
      ``_BASH_CANDIDATES``; if either is present we use it.
    - On Linux every distribution we run on (Ubuntu, Debian, Fedora,
      Arch, Alpine) ships bash 5+ at ``/bin/bash`` / ``/usr/bin/bash``.
    - macOS's stock ``/bin/bash`` is 3.2 (Apple won't ship GPLv3+); a
      macOS host with no Homebrew bash is treated as "no modern bash"
      and the spec module is skipped.

    This avoids invoking the binary just to read its version, which
    keeps the helper subprocess-free.
    """
    for candidate in _BASH_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    if not found:
        return None
    if sys.platform == "darwin":
        # macOS without a Homebrew bash → only Apple's bash 3.2 is on PATH.
        return None
    return found


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


def assert_equivalent(name: str, ours: object, theirs: object) -> None:
    """Compare two capture objects field-by-field (cross-type tolerant)."""
    if (
        getattr(ours, "stdout", None) == getattr(theirs, "stdout", None)
        and getattr(ours, "stderr", None) == getattr(theirs, "stderr", None)
        and getattr(ours, "exit_code", None) == getattr(theirs, "exit_code", None)
    ):
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
    return find_modern_bash() is None
