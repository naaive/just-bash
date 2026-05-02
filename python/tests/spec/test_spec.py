"""Run every ``*.test.sh`` script in ``tests/spec/scripts/`` and compare
just-bash-py's output against real bash."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.spec.runner import (
    assert_equivalent,
    discover,
    is_skipped,
    run_bash,
    run_just_bash,
)


@pytest.mark.parametrize("script", discover(), ids=lambda p: p.name)
def test_spec_script_matches_bash(script: Path) -> None:
    if is_skipped():
        pytest.skip("SKIP_SPEC set")
    ours = run_just_bash(script)
    theirs = run_bash(script)
    assert_equivalent(script.name, ours, theirs)
