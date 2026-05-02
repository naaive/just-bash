"""Tests for sort, uniq, tr, cut, rev, nl."""

from __future__ import annotations


def test_sort(run) -> None:
    r = run("sort", stdin=b"banana\napple\ncherry\n")
    assert r.stdout == "apple\nbanana\ncherry\n"


def test_sort_reverse(run) -> None:
    r = run("sort -r", stdin=b"a\nb\nc\n")
    assert r.stdout == "c\nb\na\n"


def test_sort_numeric(run) -> None:
    r = run("sort -n", stdin=b"10\n2\n1\n")
    assert r.stdout == "1\n2\n10\n"


def test_sort_unique(run) -> None:
    r = run("sort -u", stdin=b"b\na\nb\nc\na\n")
    assert r.stdout == "a\nb\nc\n"


def test_uniq(run) -> None:
    r = run("uniq", stdin=b"a\na\nb\nb\nb\nc\n")
    assert r.stdout == "a\nb\nc\n"


def test_uniq_count(run) -> None:
    r = run("uniq -c", stdin=b"a\na\nb\nc\nc\nc\n")
    assert "      2 a" in r.stdout
    assert "      1 b" in r.stdout
    assert "      3 c" in r.stdout


def test_tr_translate(run) -> None:
    r = run("tr a-z A-Z", stdin=b"hello\n")
    assert r.stdout == "HELLO\n"


def test_tr_delete(run) -> None:
    r = run("tr -d aeiou", stdin=b"hello world\n")
    assert r.stdout == "hll wrld\n"


def test_cut_fields(run) -> None:
    r = run("cut -d, -f2", stdin=b"a,b,c\n1,2,3\n")
    assert r.stdout == "b\n2\n"


def test_cut_chars(run) -> None:
    r = run("cut -c1-3", stdin=b"hello\nworld\n")
    assert r.stdout == "hel\nwor\n"


def test_rev(run) -> None:
    r = run("rev", stdin=b"abc\nxyz\n")
    assert r.stdout == "cba\nzyx\n"


def test_nl(run) -> None:
    r = run("nl", stdin=b"a\nb\nc\n")
    assert "     1\ta" in r.stdout
    assert "     2\tb" in r.stdout
