"""Tests for phase-4 commands and builtins."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# cmp
# ---------------------------------------------------------------------------


def test_cmp_equal(run, fs) -> None:
    fs.write_file("/a", "x\n")
    fs.write_file("/b", "x\n")
    r = run("cmp /a /b")
    assert r.exit_code == 0


def test_cmp_differ(run, fs) -> None:
    fs.write_file("/a", "abc\n")
    fs.write_file("/b", "abd\n")
    r = run("cmp /a /b")
    assert r.exit_code == 1
    assert "differ" in r.stdout


def test_cmp_silent(run, fs) -> None:
    fs.write_file("/a", "x\n")
    fs.write_file("/b", "y\n")
    r = run("cmp -s /a /b")
    assert r.exit_code == 1
    assert r.stdout == ""


# ---------------------------------------------------------------------------
# fold
# ---------------------------------------------------------------------------


def test_fold_default(run) -> None:
    text = "a" * 90
    r = run("fold", stdin=text.encode() + b"\n")
    assert r.stdout.startswith("a" * 80 + "\n" + "a" * 10)


def test_fold_with_width(run) -> None:
    r = run("fold -w 3", stdin=b"abcdefg\n")
    assert r.stdout == "abc\ndef\ng\n"


# ---------------------------------------------------------------------------
# expand / unexpand
# ---------------------------------------------------------------------------


def test_expand_default(run) -> None:
    r = run("expand", stdin=b"a\tb\n")
    assert r.stdout == "a       b\n"


def test_expand_t(run) -> None:
    r = run("expand -t 4", stdin=b"a\tb\n")
    assert r.stdout == "a   b\n"


def test_unexpand_leading(run) -> None:
    r = run("unexpand", stdin=b"        leading\n")
    assert r.stdout == "\tleading\n"


# ---------------------------------------------------------------------------
# mktemp
# ---------------------------------------------------------------------------


def test_mktemp_creates_file(run, fs) -> None:
    r = run("mktemp /tmp/test.XXXXXX")
    assert r.exit_code == 0
    path = r.stdout.strip()
    assert path.startswith("/tmp/test.")
    assert fs.exists(path)


def test_mktemp_directory(run, fs) -> None:
    r = run("mktemp -d /tmp/dir.XXXXXX")
    assert r.exit_code == 0
    assert fs.is_dir(r.stdout.strip())


# ---------------------------------------------------------------------------
# dd
# ---------------------------------------------------------------------------


def test_dd_copy(run, fs) -> None:
    fs.write_file("/in", "abcdefghij")
    r = run("dd if=/in of=/out bs=2 count=3")
    assert r.exit_code == 0
    assert fs.read_text("/out") == "abcdef"


def test_dd_stdin_to_stdout(run) -> None:
    r = run("dd bs=2 count=3", stdin=b"abcdefghij")
    assert r.stdout == "abcdef"


# ---------------------------------------------------------------------------
# cksum
# ---------------------------------------------------------------------------


def test_cksum_stdin(run) -> None:
    r = run("cksum", stdin=b"hello\n")
    parts = r.stdout.split()
    # CRC32 of "hello\n" via zlib.
    import zlib

    expected_crc = zlib.crc32(b"hello\n") & 0xFFFFFFFF
    assert int(parts[0]) == expected_crc
    assert int(parts[1]) == 6


# ---------------------------------------------------------------------------
# getopt
# ---------------------------------------------------------------------------


def test_getopt_short_flags(run) -> None:
    r = run("getopt 'ab:c' -a -b val rest")
    out = r.stdout.strip()
    assert "-a" in out
    assert "-b" in out and "'val'" in out
    assert "'rest'" in out


# ---------------------------------------------------------------------------
# alias / unalias
# ---------------------------------------------------------------------------


def test_alias_set_and_show(run) -> None:
    r = run("alias ll='ls -l'; alias")
    assert "ll='ls -l'" in r.stdout


def test_unalias_removes(run) -> None:
    r = run("alias x=foo; unalias x; alias x")
    assert r.exit_code != 0
    assert "not found" in r.stderr


# ---------------------------------------------------------------------------
# pushd / popd / dirs
# ---------------------------------------------------------------------------


def test_pushd_and_popd(run, fs) -> None:
    fs.mkdir("/a", parents=True, exist_ok=True)
    fs.mkdir("/b", parents=True, exist_ok=True)
    r = run("cd /a; pushd /b; pwd; popd; pwd")
    lines = r.stdout.splitlines()
    assert lines[1] == "/b"
    assert lines[3] == "/a"


# ---------------------------------------------------------------------------
# shopt
# ---------------------------------------------------------------------------


def test_shopt_set_and_list(run) -> None:
    r = run("shopt -s nocaseglob; shopt")
    assert "nocaseglob" in r.stdout


# ---------------------------------------------------------------------------
# umask / ulimit / time
# ---------------------------------------------------------------------------


def test_umask_default(run) -> None:
    r = run("umask")
    assert r.stdout.strip() == "0022"


def test_time_runs_command(run) -> None:
    r = run("time echo hi")
    assert r.stdout == "hi\n"
    assert "real" in r.stderr
