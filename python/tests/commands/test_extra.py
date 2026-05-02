"""Tests for the phase-2 commands."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# seq
# ---------------------------------------------------------------------------


def test_seq_one_arg(run) -> None:
    r = run("seq 5")
    assert r.stdout == "1\n2\n3\n4\n5\n"


def test_seq_two_args(run) -> None:
    r = run("seq 3 7")
    assert r.stdout == "3\n4\n5\n6\n7\n"


def test_seq_step(run) -> None:
    r = run("seq 1 2 9")
    assert r.stdout == "1\n3\n5\n7\n9\n"


def test_seq_descending(run) -> None:
    r = run("seq 5 -1 1")
    assert r.stdout == "5\n4\n3\n2\n1\n"


# ---------------------------------------------------------------------------
# expr
# ---------------------------------------------------------------------------


def test_expr_add(run) -> None:
    r = run("expr 3 + 4")
    assert r.stdout == "7\n"


def test_expr_mul(run) -> None:
    r = run("expr 3 \\* 4")
    assert r.stdout == "12\n"


def test_expr_length(run) -> None:
    r = run("expr length hello")
    assert r.stdout == "5\n"


def test_expr_substr(run) -> None:
    r = run("expr substr abcdef 2 3")
    assert r.stdout == "bcd\n"


# ---------------------------------------------------------------------------
# sleep
# ---------------------------------------------------------------------------


def test_sleep_no_op(run) -> None:
    r = run("sleep 1; echo done")
    assert r.stdout == "done\n"


# ---------------------------------------------------------------------------
# date
# ---------------------------------------------------------------------------


def test_date_format_year(run) -> None:
    r = run("date '+%Y'")
    assert r.exit_code == 0
    assert r.stdout.strip().isdigit()


# ---------------------------------------------------------------------------
# paste
# ---------------------------------------------------------------------------


def test_paste_two_files(run, fs) -> None:
    fs.write_file("/a", "1\n2\n3\n")
    fs.write_file("/b", "x\ny\nz\n")
    r = run("paste /a /b")
    assert r.stdout == "1\tx\n2\ty\n3\tz\n"


def test_paste_with_delim(run, fs) -> None:
    fs.write_file("/a", "1\n2\n")
    fs.write_file("/b", "x\ny\n")
    r = run("paste -d, /a /b")
    assert r.stdout == "1,x\n2,y\n"


# ---------------------------------------------------------------------------
# comm
# ---------------------------------------------------------------------------


def test_comm_basic(run, fs) -> None:
    fs.write_file("/a", "a\nb\nc\n")
    fs.write_file("/b", "b\nc\nd\n")
    r = run("comm /a /b")
    # Lines unique to a, unique to b, common.
    assert "a" in r.stdout and "d" in r.stdout and "b" in r.stdout


# ---------------------------------------------------------------------------
# diff
# ---------------------------------------------------------------------------


def test_diff_equal_files(run, fs) -> None:
    fs.write_file("/a", "x\ny\n")
    fs.write_file("/b", "x\ny\n")
    r = run("diff /a /b")
    assert r.exit_code == 0
    assert r.stdout == ""


def test_diff_different_files(run, fs) -> None:
    fs.write_file("/a", "x\ny\nz\n")
    fs.write_file("/b", "x\nY\nz\n")
    r = run("diff -q /a /b")
    assert r.exit_code == 1
    assert "differ" in r.stdout


# ---------------------------------------------------------------------------
# md5sum / sha1sum / sha256sum
# ---------------------------------------------------------------------------


def test_md5sum(run, fs) -> None:
    fs.write_file("/x", "hello\n")
    r = run("md5sum /x")
    # md5("hello\n") = b1946ac92492d2347c6235b4d2611184
    assert r.stdout.startswith("b1946ac92492d2347c6235b4d2611184")


def test_sha256sum_stdin(run) -> None:
    r = run("sha256sum", stdin=b"hello\n")
    # sha256 of "hello\n"
    assert r.stdout.split()[0] == (
        "5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
    )


# ---------------------------------------------------------------------------
# realpath
# ---------------------------------------------------------------------------


def test_realpath(run, fs) -> None:
    fs.mkdir("/a/b", parents=True)
    fs.write_file("/a/b/c", "")
    r = run("cd /a; realpath b/c")
    assert r.stdout == "/a/b/c\n"


# ---------------------------------------------------------------------------
# stat
# ---------------------------------------------------------------------------


def test_stat_file(run, fs) -> None:
    fs.write_file("/file", "abc")
    r = run("stat /file")
    assert "Size: 3" in r.stdout
    assert "regular file" in r.stdout


# ---------------------------------------------------------------------------
# xargs
# ---------------------------------------------------------------------------


def test_xargs_simple(run) -> None:
    r = run("echo a b c | xargs echo")
    assert r.stdout == "a b c\n"


def test_xargs_n(run) -> None:
    r = run("printf '%s\\n' a b c d | xargs -n 2 echo")
    assert r.stdout == "a b\nc d\n"


def test_xargs_replace(run) -> None:
    r = run('printf "a\\nb\\n" | xargs -I {} echo got {}')
    assert r.stdout == "got a\ngot b\n"
