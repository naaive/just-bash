"""Tests for ``mapfile`` / ``readarray`` and the small completion helpers."""

from __future__ import annotations


def test_mapfile_default(run) -> None:
    r = run('printf "a\\nb\\nc\\n" | mapfile arr; echo "${#arr[@]}"; echo "${arr[1]}"')
    out = r.stdout.splitlines()
    assert out[0] == "3"
    # Without -t, lines retain their terminator. ``arr[1]`` is ``b\n``.
    assert out[1] == "b"


def test_mapfile_strip_terminator(run) -> None:
    r = run('printf "a\\nb\\nc\\n" | mapfile -t arr; for x in "${arr[@]}"; do echo "<$x>"; done')
    assert r.stdout == "<a>\n<b>\n<c>\n"


def test_mapfile_count(run) -> None:
    r = run('printf "1\\n2\\n3\\n4\\n5\\n" | mapfile -t -n 3 arr; echo "${#arr[@]}"')
    assert r.stdout.strip() == "3"


def test_readarray_alias(run) -> None:
    r = run('printf "x\\ny\\n" | readarray -t arr; echo "${arr[0]}-${arr[1]}"')
    assert r.stdout == "x-y\n"


def test_compgen_word_list(run) -> None:
    r = run('compgen -W "apple banana cherry" b')
    assert r.stdout == "banana\n"


def test_jobs_returns_success(run) -> None:
    r = run("jobs; echo $?")
    assert r.stdout.strip() == "0"


def test_wait_no_op(run) -> None:
    r = run("wait; echo done")
    assert r.stdout == "done\n"
