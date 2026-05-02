"""Tests for find, cp, mv, rm."""

from __future__ import annotations


def _setup_tree(fs) -> None:
    fs.mkdir("/r/sub", parents=True)
    fs.write_file("/r/a.txt", "")
    fs.write_file("/r/b.md", "")
    fs.write_file("/r/sub/c.txt", "")
    fs.write_file("/r/sub/d.md", "")


# ---------------------------------------------------------------------------
# find
# ---------------------------------------------------------------------------


def test_find_all(run, fs) -> None:
    _setup_tree(fs)
    r = run("find /r")
    lines = sorted(r.stdout.split())
    assert "/r" in lines
    assert "/r/a.txt" in lines
    assert "/r/sub/c.txt" in lines


def test_find_name_glob(run, fs) -> None:
    _setup_tree(fs)
    r = run("find /r -name '*.txt'")
    out = sorted(r.stdout.split())
    assert out == ["/r/a.txt", "/r/sub/c.txt"]


def test_find_type_d(run, fs) -> None:
    _setup_tree(fs)
    r = run("find /r -type d")
    out = sorted(r.stdout.split())
    assert "/r" in out and "/r/sub" in out
    assert "/r/a.txt" not in out


def test_find_maxdepth(run, fs) -> None:
    _setup_tree(fs)
    r = run("find /r -maxdepth 1")
    out = sorted(r.stdout.split())
    assert "/r/sub" in out
    assert "/r/sub/c.txt" not in out


# ---------------------------------------------------------------------------
# cp
# ---------------------------------------------------------------------------


def test_cp_file(run, fs) -> None:
    fs.write_file("/a", "hello\n")
    r = run("cp /a /b")
    assert r.exit_code == 0
    assert fs.read_text("/b") == "hello\n"


def test_cp_recursive(run, fs) -> None:
    fs.mkdir("/src/inner", parents=True)
    fs.write_file("/src/inner/file", "x")
    r = run("cp -r /src /dst")
    assert r.exit_code == 0
    assert fs.read_text("/dst/inner/file") == "x"


# ---------------------------------------------------------------------------
# mv
# ---------------------------------------------------------------------------


def test_mv_renames(run, fs) -> None:
    fs.write_file("/a", "x")
    r = run("mv /a /b")
    assert r.exit_code == 0
    assert fs.read_text("/b") == "x"
    assert not fs.exists("/a")


def test_mv_into_dir(run, fs) -> None:
    fs.mkdir("/d")
    fs.write_file("/file", "x")
    r = run("mv /file /d")
    assert r.exit_code == 0
    assert fs.read_text("/d/file") == "x"


# ---------------------------------------------------------------------------
# rm
# ---------------------------------------------------------------------------


def test_rm_file(run, fs) -> None:
    fs.write_file("/x", b"")
    r = run("rm /x")
    assert r.exit_code == 0
    assert not fs.exists("/x")


def test_rm_dir_requires_r(run, fs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/x", b"")
    r = run("rm /d")
    assert r.exit_code == 1
    r2 = run("rm -r /d")
    assert r2.exit_code == 0
    assert not fs.exists("/d")


def test_rm_force_missing(run) -> None:
    r = run("rm -f /nope")
    assert r.exit_code == 0
