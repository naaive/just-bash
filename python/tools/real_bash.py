"""Tiny wrapper around the host bash binary.

This module is intentionally outside ``python/tests/`` so the test suite
can stay subprocess-free in CI; ``tests/comparison`` only invokes this
helper when ``RECORD_FIXTURES=1`` is set, and ``tests/spec`` skips when
the helper isn't usable.

Importable for local-dev fixture recording only. Not included in the
SonarCloud "sources" path.
"""
# argv is a fixed-shape allowlist; never shell=True

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(slots=True)
class Capture:
    stdout: str
    stderr: str
    exit_code: int


_BASH_CANDIDATES = (
    "/opt/homebrew/bin/bash",
    "/usr/local/bin/bash",
)


@lru_cache(maxsize=1)
def find_modern_bash() -> str | None:
    """Locate a bash >= 4 binary by path heuristic only."""
    for candidate in _BASH_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    found = shutil.which("bash")
    if not found:
        return None
    if sys.platform == "darwin":
        # macOS without Homebrew → only Apple's bash 3.2 is on PATH.
        return None
    return found


def run_script(script_path: Path) -> Capture:
    """Run a ``.test.sh`` script through the host bash."""
    bash = find_modern_bash()
    if bash is None:
        raise RuntimeError("bash >= 4 not found")
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(  # NOSONAR - vetted bash + fixed argv
            [bash, str(script_path)],
            cwd=tmp,
            capture_output=True,
            timeout=10,
            env={
                "LC_ALL": "C",
                "LANG": "C",
                "PATH": "/usr/bin:/bin",
                "HOME": tmp,
                "PWD": tmp,
            },
            check=False,
        )
    return Capture(
        stdout=result.stdout.decode("utf-8", errors="replace"),
        stderr=result.stderr.decode("utf-8", errors="replace"),
        exit_code=result.returncode,
    )


def run_inline(script: str, *, files: dict[str, str] | None = None, stdin: bytes = b"") -> Capture:
    """Run an inline script through the host bash via ``-c``."""
    bash = shutil.which("bash")
    if bash is None:
        raise RuntimeError("real bash not on PATH")
    with tempfile.TemporaryDirectory() as tmpdir:
        if files:
            for relpath, content in files.items():
                target = Path(tmpdir) / relpath
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content)
        result = subprocess.run(  # NOSONAR - vetted bash + fixed argv
            [bash, "-c", script],
            cwd=tmpdir,
            input=stdin,
            capture_output=True,
            timeout=10,
            env={
                "LC_ALL": "C",
                "LANG": "C",
                "PATH": "/usr/bin:/bin",
                "HOME": tmpdir,
                "PWD": tmpdir,
            },
            check=False,
        )
    return Capture(
        stdout=result.stdout.decode("utf-8", errors="replace"),
        stderr=result.stderr.decode("utf-8", errors="replace"),
        exit_code=result.returncode,
    )
