"""Tests for grep, sed, awk."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# grep
# ---------------------------------------------------------------------------


def test_grep_simple(run) -> None:
    r = run("grep ell", stdin=b"hello\nworld\nshell\n")
    assert r.stdout == "hello\nshell\n"


def test_grep_invert(run) -> None:
    r = run("grep -v ell", stdin=b"hello\nworld\nshell\n")
    assert r.stdout == "world\n"


def test_grep_count(run) -> None:
    r = run("grep -c ell", stdin=b"hello\nworld\nshell\n")
    assert r.stdout == "2\n"


def test_grep_lineno(run) -> None:
    r = run("grep -n ell", stdin=b"hello\nworld\nshell\n")
    assert r.stdout == "1:hello\n3:shell\n"


def test_grep_case_insensitive(run) -> None:
    r = run("grep -i hello", stdin=b"HELLO\nhello\nHi\n")
    assert r.stdout == "HELLO\nhello\n"


def test_grep_fixed_string(run) -> None:
    r = run("grep -F '.' ", stdin=b"a.b\naxb\n")
    assert r.stdout == "a.b\n"


def test_grep_word(run) -> None:
    r = run("grep -w cat", stdin=b"cat\ncategory\nwildcat\n")
    assert r.stdout == "cat\n"


def test_grep_recursive(run, fs) -> None:
    fs.mkdir("/r/sub", parents=True)
    fs.write_file("/r/a.txt", "hello\n")
    fs.write_file("/r/sub/b.txt", "world\nhello\n")
    r = run("grep -r hello /r")
    assert "/r/a.txt" in r.stdout
    assert "/r/sub/b.txt" in r.stdout


def test_grep_no_match_returns_1(run) -> None:
    r = run("grep zzz", stdin=b"a\nb\n")
    assert r.exit_code == 1


# ---------------------------------------------------------------------------
# sed
# ---------------------------------------------------------------------------


def test_sed_substitute(run) -> None:
    r = run("sed 's/foo/bar/'", stdin=b"foo baz foo\n")
    assert r.stdout == "bar baz foo\n"


def test_sed_global(run) -> None:
    r = run("sed 's/foo/bar/g'", stdin=b"foo baz foo\n")
    assert r.stdout == "bar baz bar\n"


def test_sed_address(run) -> None:
    r = run("sed '2 s/x/Y/'", stdin=b"x\nx\nx\n")
    assert r.stdout == "x\nY\nx\n"


def test_sed_delete(run) -> None:
    r = run("sed '2d'", stdin=b"a\nb\nc\n")
    assert r.stdout == "a\nc\n"


def test_sed_quiet_print(run) -> None:
    r = run("sed -n '2p'", stdin=b"a\nb\nc\n")
    assert r.stdout == "b\n"


def test_sed_backref(run) -> None:
    r = run(r"sed 's/\([a-z]*\) \([a-z]*\)/\2 \1/'", stdin=b"hello world\n")
    assert r.stdout == "world hello\n"


def test_sed_case_insensitive(run) -> None:
    r = run("sed 's/foo/bar/gi'", stdin=b"FOO Foo foo\n")
    assert r.stdout == "bar bar bar\n"


# ---------------------------------------------------------------------------
# awk
# ---------------------------------------------------------------------------


def test_awk_print_first_field(run) -> None:
    r = run("awk '{ print $1 }'", stdin=b"alpha beta\ngamma delta\n")
    assert r.stdout == "alpha\ngamma\n"


def test_awk_arithmetic(run) -> None:
    r = run("awk '{ s += $1 } END { print s }'", stdin=b"1\n2\n3\n4\n")
    assert r.stdout == "10\n"


def test_awk_field_separator(run) -> None:
    r = run("awk -F, '{ print $2 }'", stdin=b"a,b,c\n1,2,3\n")
    assert r.stdout == "b\n2\n"


def test_awk_pattern_match(run) -> None:
    r = run("awk '/foo/ { print }'", stdin=b"foo\nbar\nfoobar\n")
    assert r.stdout == "foo\nfoobar\n"


def test_awk_begin_end(run) -> None:
    r = run('awk \'BEGIN { print "start" } END { print "end" }\'', stdin=b"")
    assert r.stdout == "start\nend\n"


def test_awk_nf(run) -> None:
    r = run("awk '{ print NF }'", stdin=b"a b c\nx y\n")
    assert r.stdout == "3\n2\n"


def test_awk_nr(run) -> None:
    r = run("awk '{ print NR, $0 }'", stdin=b"a\nb\nc\n")
    assert r.stdout == "1 a\n2 b\n3 c\n"
