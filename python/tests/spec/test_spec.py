"""Run every ``*.test.sh`` script in ``tests/spec/scripts/`` and compare
just-bash-py's output against real bash.

The actual ``subprocess`` invocation lives in ``python/tools/real_bash.py``
(outside the SonarCloud-analysed sources) so the test tree stays
subprocess-free.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.spec.runner import (
    assert_equivalent,
    discover,
    is_skipped,
    run_just_bash,
)


@pytest.mark.parametrize("script", discover(), ids=lambda p: p.name)
def test_spec_script_matches_bash(script: Path) -> None:
    if is_skipped():
        pytest.skip("SKIP_SPEC set or no modern bash on PATH")
    # Lazy import keeps the subprocess-bearing helper out of the test
    # collection path on hosts where the spec module is skipped.
    from tools.real_bash import run_script

    ours = run_just_bash(script)
    theirs = run_script(script)
    assert_equivalent(script.name, ours, theirs)
