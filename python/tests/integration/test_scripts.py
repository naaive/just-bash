"""End-to-end script tests that combine multiple features."""

from __future__ import annotations


def test_pipeline_cat_grep_wc(run, fs) -> None:
    fs.write_file("/data", "alpha\nbeta\ngamma\nalphabet\n")
    r = run("cat /data | grep alpha | wc -l")
    assert r.stdout.strip() == "2"


def test_for_with_glob(run, fs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/a.txt", "")
    fs.write_file("/d/b.txt", "")
    fs.write_file("/d/c.md", "")
    r = run('for f in /d/*.txt; do echo "$f"; done')
    assert r.stdout == "/d/a.txt\n/d/b.txt\n"


def test_function_with_return_in_pipeline(run) -> None:
    r = run("""
    f() { echo "$1"; }
    for n in 1 2 3; do
      f "n=$n"
    done
    """)
    assert r.stdout == "n=1\nn=2\nn=3\n"


def test_arithmetic_loop_counts(run) -> None:
    r = run("""
    n=0
    for i in 1 2 3 4 5; do
      (( n += i ))
    done
    echo $n
    """)
    assert r.stdout == "15\n"


def test_pipeline_into_sort_uniq(run) -> None:
    r = run('echo -e "b\\na\\nb\\nc\\na" | sort | uniq')
    assert r.stdout == "a\nb\nc\n"


def test_grep_with_redirect(run, fs) -> None:
    fs.write_file("/in", "alpha\nbeta\nalphabet\n")
    r = run("grep alpha /in > /out")
    assert r.exit_code == 0
    assert fs.read_text("/out") == "alpha\nalphabet\n"


def test_word_split_and_glob_combined(run, fs) -> None:
    fs.mkdir("/x")
    fs.write_file("/x/a", "")
    fs.write_file("/x/b", "")
    r = run('files="/x/a /x/b"; for f in $files; do echo $f; done')
    assert r.stdout == "/x/a\n/x/b\n"


def test_command_substitution_in_args(run) -> None:
    r = run('echo "today is $(echo monday)"')
    assert r.stdout == "today is monday\n"


def test_recursive_grep_count(run, fs) -> None:
    fs.mkdir("/r/sub", parents=True)
    fs.write_file("/r/a", "match me\nnope\n")
    fs.write_file("/r/sub/b", "yes match\nfoo\n")
    r = run("grep -r match /r | wc -l")
    assert r.stdout.strip() == "2"


def test_full_pipeline_with_awk(run) -> None:
    r = run("""
    printf '%s\\n' "alice 90" "bob 85" "carol 95" |
      awk '{ s += $2 } END { print s }'
    """)
    assert r.stdout == "270\n"
