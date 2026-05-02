"""Tests for cat, ls, mkdir, head, tail, wc, etc."""

from __future__ import annotations


def test_cat_files(run, fs) -> None:
    fs.write_file("/a", "alpha\n")
    fs.write_file("/b", "beta\n")
    r = run("cat /a /b")
    assert r.stdout == "alpha\nbeta\n"


def test_cat_stdin(run) -> None:
    r = run("cat", stdin=b"piped\n")
    assert r.stdout == "piped\n"


def test_cat_n(run, fs) -> None:
    fs.write_file("/a", "x\ny\nz\n")
    r = run("cat -n /a")
    assert "     1\tx" in r.stdout
    assert "     2\ty" in r.stdout


def test_ls_directory(run, fs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/file1", "")
    fs.write_file("/d/file2", "")
    r = run("ls /d")
    assert "file1" in r.stdout and "file2" in r.stdout


def test_ls_hidden(run, fs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/.hidden", "")
    fs.write_file("/d/visible", "")
    r = run("ls /d")
    assert ".hidden" not in r.stdout
    r = run("ls -a /d")
    assert ".hidden" in r.stdout


def test_mkdir_and_p(run, fs) -> None:
    r = run("mkdir -p /a/b/c")
    assert r.exit_code == 0
    assert fs.is_dir("/a/b/c")


def test_touch_creates(run, fs) -> None:
    r = run("touch /file && [ -f /file ] && echo ok")
    assert r.stdout == "ok\n"


def test_head(run) -> None:
    r = run("head -n 2", stdin=b"a\nb\nc\nd\n")
    assert r.stdout == "a\nb\n"


def test_tail(run) -> None:
    r = run("tail -n 2", stdin=b"a\nb\nc\nd\n")
    assert r.stdout == "c\nd\n"


def test_wc_counts(run) -> None:
    r = run("wc -l", stdin=b"a\nb\nc\n")
    assert r.stdout.strip().split()[0] == "3"


def test_basename(run) -> None:
    r = run("basename /a/b/c.txt")
    assert r.stdout == "c.txt\n"


def test_dirname(run) -> None:
    r = run("dirname /a/b/c.txt")
    assert r.stdout == "/a/b\n"


def test_tee(run, fs) -> None:
    r = run("echo hello | tee /tmp.txt")
    assert r.stdout == "hello\n"
    assert fs.read_text("/tmp.txt") == "hello\n"


def test_pwd(run, fs) -> None:
    fs.mkdir("/work", parents=True, exist_ok=True)
    r = run("cd /work; pwd")
    assert r.stdout == "/work\n"
