"""Comparison-test harness.

The harness runs a script through ``just-bash-py`` and compares the captured
stdout/stderr/exit-code against a JSON fixture committed alongside the test.
Fixtures are recorded by re-running the suite with ``RECORD_FIXTURES=1``
in the environment, which invokes real ``bash`` and writes the fixture file.

Why fixtures and not always-live ``bash``: portability. Real bash output
varies with locale, glibc version, and tooling versions on the host. Recorded
fixtures are deterministic across CI machines.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from just_bash.fs.vfs import VirtualFs
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.interpreter import Interpreter
from just_bash.parser.parser import parse

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(slots=True)
class Capture:
    stdout: str
    stderr: str
    exit_code: int

    def to_dict(self) -> dict[str, str | int]:
        return {"stdout": self.stdout, "stderr": self.stderr, "exitCode": self.exit_code}


def _record() -> bool:
    return os.environ.get("RECORD_FIXTURES", "") not in ("", "0", "false")


def _run_real_bash(
    script: str, *, files: dict[str, str] | None = None, stdin: bytes = b""
) -> Capture:
    """Stub — use ``scripts/record-fixtures.sh`` to (re-)record fixtures.

    The original Python recorder used ``subprocess.run`` which SonarCloud
    flagged as a hotspot we couldn't auto-clear; that recorder lived in
    ``python/tools/real_bash.py`` and has been removed in favour of a
    shell wrapper in ``python/scripts/record-fixtures.sh``.
    """
    del files, stdin  # unused
    raise RuntimeError(
        "RECORD_FIXTURES is no longer supported from pytest. "
        "Run scripts/record-fixtures.sh against the desired fixture(s) "
        "and commit the resulting JSON. Script body was: "
        f"{script[:80]!r}..."
    )


def _run_just_bash(
    script: str, *, files: dict[str, str] | None = None, stdin: bytes = b""
) -> Capture:
    fs = VirtualFs()
    fs.mkdir("/work", parents=True, exist_ok=True)
    if files:
        for relpath, content in files.items():
            full = "/work/" + relpath if not relpath.startswith("/") else relpath
            parent = full.rsplit("/", 1)[0]
            if parent:
                fs.mkdir(parent, parents=True, exist_ok=True)
            fs.write_file(full, content)
    fs.chdir("/work")
    env = Environment(
        initial_env={"PATH": "/usr/bin:/bin", "HOME": "/work", "PWD": "/work", "IFS": " \t\n"}
    )
    interp = Interpreter(fs=fs, env=env)
    result = interp.run_script_capture(parse(script), stdin=stdin)
    return Capture(stdout=result.stdout, stderr=result.stderr, exit_code=result.exit_code)


def compare(
    name: str, script: str, *, files: dict[str, str] | None = None, stdin: bytes = b""
) -> None:
    """Assert ``just-bash-py`` matches the recorded ``bash`` fixture for ``name``.

    With ``RECORD_FIXTURES=1`` set, runs real bash to capture and overwrite
    the fixture. Otherwise loads the fixture and asserts equality.
    """
    fixture_path = FIXTURE_DIR / f"{name}.json"
    if _record():
        cap = _run_real_bash(script, files=files, stdin=stdin)
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(
            json.dumps(
                {"script": script, "files": files or {}, **cap.to_dict()}, indent=2, sort_keys=True
            )
            + "\n"
        )
        return
    if not fixture_path.exists():
        raise AssertionError(
            f"missing fixture: {fixture_path}. "
            "Re-run with RECORD_FIXTURES=1 to capture from real bash."
        )
    fixture = json.loads(fixture_path.read_text())
    actual = _run_just_bash(script, files=files, stdin=stdin)
    expected = Capture(
        stdout=fixture["stdout"], stderr=fixture["stderr"], exit_code=fixture["exitCode"]
    )
    if actual != expected:
        raise AssertionError(
            f"comparison mismatch for {name!r}\n"
            f"--- expected ({fixture_path.name}, recorded from real bash) ---\n"
            f"stdout={expected.stdout!r}\nstderr={expected.stderr!r}\nexit={expected.exit_code}\n"
            f"--- actual (just-bash-py) ---\n"
            f"stdout={actual.stdout!r}\nstderr={actual.stderr!r}\nexit={actual.exit_code}\n"
        )
