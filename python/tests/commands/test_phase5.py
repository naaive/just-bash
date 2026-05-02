"""Phase-5 tests: find -exec / -delete, sed -i, grep -P / -A / -B / -C / -o."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# find actions
# ---------------------------------------------------------------------------


def test_find_exec_simple(run, fs) -> None:
    fs.mkdir("/r", parents=True)
    fs.write_file("/r/a", "")
    fs.write_file("/r/b", "")
    r = run("find /r -type f -exec echo {} \\;")
    out = sorted(r.stdout.split())
    assert out == ["/r/a", "/r/b"]


def test_find_exec_multi_arg(run, fs) -> None:
    fs.mkdir("/r", parents=True)
    fs.write_file("/r/a", "")
    fs.write_file("/r/b", "")
    fs.write_file("/r/c", "")
    r = run("find /r -type f -exec echo {} +")
    # ``+`` form passes all matches in a single invocation.
    assert "/r/a" in r.stdout and "/r/b" in r.stdout and "/r/c" in r.stdout
    # Single line means a single ``echo`` invocation.
    assert r.stdout.count("\n") == 1


def test_find_delete(run, fs) -> None:
    fs.mkdir("/r/sub", parents=True)
    fs.write_file("/r/keep.txt", "")
    fs.write_file("/r/sub/drop.tmp", "")
    fs.write_file("/r/drop.tmp", "")
    r = run("find /r -name '*.tmp' -delete")
    assert r.exit_code == 0
    assert fs.exists("/r/keep.txt")
    assert not fs.exists("/r/drop.tmp")
    assert not fs.exists("/r/sub/drop.tmp")


def test_find_or(run, fs) -> None:
    fs.mkdir("/r", parents=True)
    fs.write_file("/r/a.txt", "")
    fs.write_file("/r/b.md", "")
    fs.write_file("/r/c.py", "")
    r = run("find /r -name '*.txt' -o -name '*.md'")
    out = sorted(r.stdout.split())
    assert out == ["/r/a.txt", "/r/b.md"]


def test_find_size(run, fs) -> None:
    fs.mkdir("/r", parents=True)
    fs.write_file("/r/small", b"abc")
    fs.write_file("/r/big", b"x" * 5000)
    r = run("find /r -type f -size +1k")
    out = r.stdout.split()
    assert "/r/big" in out and "/r/small" not in out


# ---------------------------------------------------------------------------
# sed -i
# ---------------------------------------------------------------------------


def test_sed_in_place(run, fs) -> None:
    fs.write_file("/file.txt", "foo\nbar\nfoo\n")
    r = run("sed -i 's/foo/baz/g' /file.txt")
    assert r.exit_code == 0
    assert fs.read_text("/file.txt") == "baz\nbar\nbaz\n"


def test_sed_in_place_keeps_original_when_no_match(run, fs) -> None:
    fs.write_file("/x", "abc\n")
    r = run("sed -i 's/zzz/yyy/' /x")
    assert r.exit_code == 0
    assert fs.read_text("/x") == "abc\n"


# ---------------------------------------------------------------------------
# grep -P / -A / -B / -C / -o
# ---------------------------------------------------------------------------


def test_grep_only_matching(run) -> None:
    r = run("grep -o '[0-9]\\+'", stdin=b"abc 12 def 345\nno digits\n6789 z\n")
    assert r.stdout == "12\n345\n6789\n"


def test_grep_after_context(run) -> None:
    r = run("grep -A 1 needle", stdin=b"a\nneedle\nb\nc\nd\n")
    # Match plus 1 line of trailing context.
    assert r.stdout == "needle\nb\n"


def test_grep_before_context(run) -> None:
    r = run("grep -B 1 needle", stdin=b"a\nb\nneedle\nc\n")
    assert r.stdout == "b\nneedle\n"


def test_grep_combined_context(run) -> None:
    r = run("grep -C 1 needle", stdin=b"a\nb\nneedle\nc\nd\n")
    assert r.stdout == "b\nneedle\nc\n"


def test_grep_perl_regex(run) -> None:
    # Python re already supports the Perl features; -P just enables it.
    r = run("grep -P '\\d{3}'", stdin=b"a 12 b\nc 345 d\n")
    assert r.stdout == "c 345 d\n"
