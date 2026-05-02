"""Indirect expansion ``${!ref}`` and var-name prefix ``${!prefix*}``."""

from __future__ import annotations


def test_indirect_simple(run) -> None:
    r = run('x=hello; ref=x; echo "${!ref}"')
    assert r.stdout == "hello\n"


def test_indirect_with_default(run) -> None:
    r = run('ref=missing; echo "${!ref:-fallback}"')
    assert r.stdout == "fallback\n"


def test_indirect_to_array_element(run) -> None:
    # The TS port doesn't support indirect-to-array in MVP, but the simple
    # case (``ref`` points at a scalar) is the common usage.
    r = run('a=alpha; ref=a; echo "${!ref}"')
    assert r.stdout == "alpha\n"


def test_name_prefix_star(run) -> None:
    r = run("foo_a=1; foo_b=2; bar=3; echo ${!foo_*}")
    assert "foo_a" in r.stdout and "foo_b" in r.stdout
    assert "bar" not in r.stdout


def test_name_prefix_at_quoted_iter(run) -> None:
    r = run('foo_a=1; foo_b=2; for n in "${!foo_@}"; do echo "$n=${!n}"; done')
    assert r.stdout == "foo_a=1\nfoo_b=2\n"


def test_indirect_unset(run) -> None:
    r = run('ref=unset_name; echo "[${!ref}]"')
    # ``unset_name`` is undefined → empty.
    assert r.stdout == "[]\n"
