"""End-to-end: run scripts against an OverlayFs over a real directory."""

from __future__ import annotations

from pathlib import Path

from just_bash.fs.overlay_fs import OverlayFs
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.interpreter import Interpreter
from just_bash.parser.parser import parse


def _run(fs: OverlayFs, script: str) -> tuple[str, str, int]:
    fs.chdir("/")
    env = Environment(initial_env={"PATH": "/usr/bin:/bin", "HOME": "/", "IFS": " \t\n"})
    interp = Interpreter(fs=fs, env=env)  # type: ignore[arg-type]
    r = interp.run_script_capture(parse(script))
    return r.stdout, r.stderr, r.exit_code


def test_grep_real_files_through_overlay(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello\nworld\nhello again\n")
    (tmp_path / "b.txt").write_text("nothing here\n")
    fs = OverlayFs(tmp_path)
    out, _, rc = _run(fs, "grep hello /a.txt /b.txt")
    assert rc == 0
    assert "/a.txt:hello" in out
    assert "/a.txt:hello again" in out
    assert "/b.txt" not in out


def test_overlay_write_visible_to_subsequent_command(tmp_path: Path) -> None:
    fs = OverlayFs(tmp_path)
    (tmp_path / "data.txt").write_text("x\n")
    out, _, rc = _run(
        fs,
        "echo first > /data.txt; echo second >> /data.txt; cat /data.txt",
    )
    assert rc == 0
    assert out == "first\nsecond\n"
    # Real file is still untouched.
    assert (tmp_path / "data.txt").read_text() == "x\n"


def test_find_walks_real_tree(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("")
    (tmp_path / "src" / "b.txt").write_text("")
    (tmp_path / "src" / "sub").mkdir()
    (tmp_path / "src" / "sub" / "c.py").write_text("")
    fs = OverlayFs(tmp_path)
    out, _, rc = _run(fs, "find /src -name '*.py'")
    assert rc == 0
    assert "/src/a.py" in out
    assert "/src/sub/c.py" in out
    assert "/src/b.txt" not in out
