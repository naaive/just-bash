"""Run every ``*.test.sh`` script in ``tests/spec/scripts/`` and compare
just-bash-py's output against real bash.

The bash subprocess invocation lives here (in a clearly-test-named
file) rather than in ``runner.py`` so SonarCloud applies test-file
heuristics to it.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pytest

from tests.spec.runner import (
    Capture,
    assert_equivalent,
    discover,
    find_modern_bash,
    is_skipped,
    run_just_bash,
)


def _run_real_bash(script_path: Path) -> Capture:
    """Invoke the host bash on a single spec script.

    ``script_path`` comes from the committed ``tests/spec/scripts/`` glob;
    the ``bash`` binary is one of the vetted entries in
    ``runner._BASH_CANDIDATES``. ``shell=True`` is never used.
    """
    bash = find_modern_bash()
    if bash is None:
        raise RuntimeError("bash >= 4 not found")
    with tempfile.TemporaryDirectory() as tmp:
        result = subprocess.run(  # NOSONAR - argv is a fixed-shape allowlist
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


@pytest.mark.parametrize("script", discover(), ids=lambda p: p.name)
def test_spec_script_matches_bash(script: Path) -> None:
    if is_skipped():
        pytest.skip("SKIP_SPEC set or no modern bash on PATH")
    ours = run_just_bash(script)
    theirs = _run_real_bash(script)
    assert_equivalent(script.name, ours, theirs)
