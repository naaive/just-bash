"""End-to-end CLI invocation tests via ``just_bash.cli.main``."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from just_bash.cli import main as cli_main


def _run_cli(argv: list[str]) -> tuple[str, str, int]:
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc = cli_main(argv)
    return out.getvalue(), err.getvalue(), rc


def test_cli_inline_command() -> None:
    stdout, _, rc = _run_cli(["-c", "echo hello"])
    assert stdout == "hello\n"
    assert rc == 0


def test_cli_pipeline() -> None:
    stdout, _, rc = _run_cli(["-c", "echo abc | tr a-z A-Z"])
    assert stdout == "ABC\n"
    assert rc == 0


def test_cli_json_output() -> None:
    stdout, _, rc = _run_cli(["--json", "-c", "echo hi; false"])
    payload = json.loads(stdout.strip())
    assert payload["stdout"] == "hi\n"
    assert payload["exitCode"] == 1
    assert rc == 1


def test_cli_overlay_root_reads_real_files(tmp_path: Path) -> None:
    (tmp_path / "alpha.txt").write_text("alpha-content\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "beta.txt").write_text("beta-content\n")
    stdout, _, rc = _run_cli(["--root", str(tmp_path), "-c", "cat /alpha.txt /src/beta.txt"])
    assert stdout == "alpha-content\nbeta-content\n"
    assert rc == 0


def test_cli_overlay_writes_stay_in_memory(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("orig\n")
    stdout, _, _ = _run_cli(
        ["--root", str(tmp_path), "-c", "echo new > /input.txt; cat /input.txt"]
    )
    assert stdout == "new\n"
    # Real file unchanged.
    assert (tmp_path / "input.txt").read_text() == "orig\n"


def test_cli_overlay_symlink_blocked(tmp_path: Path) -> None:
    (tmp_path / "link").symlink_to("/etc/passwd")
    _, stderr, rc = _run_cli(["--root", str(tmp_path), "-c", "cat /link"])
    assert rc != 0
    assert "no such file or directory" in stderr.lower() or "ENOENT" in stderr


def test_cli_print_ast() -> None:
    stdout, _, rc = _run_cli(["--print-ast", "-c", "echo hi"])
    assert rc == 0
    payload = json.loads(stdout)
    # The dumped Script dataclass has a ``statements`` list.
    assert "statements" in payload
    assert payload["statements"]


def test_cli_errexit_aborts() -> None:
    stdout, _, rc = _run_cli(["-e", "-c", "false; echo never"])
    assert rc == 1
    assert stdout == ""


def test_cli_legacy_head_flag() -> None:
    stdout, _, rc = _run_cli(["-c", "printf '1\\n2\\n3\\n4\\n5\\n' | head -3"])
    assert stdout == "1\n2\n3\n"
    assert rc == 0
