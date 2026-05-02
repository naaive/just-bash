"""Indexed array tests."""

from __future__ import annotations


def test_simple_indexed(run) -> None:
    r = run("arr=(a b c); echo ${arr[0]} ${arr[1]} ${arr[2]}")
    assert r.stdout == "a b c\n"


def test_array_length(run) -> None:
    r = run("arr=(a b c d); echo ${#arr[@]}")
    assert r.stdout == "4\n"


def test_array_unquoted_at(run) -> None:
    r = run("arr=(a b c); for x in ${arr[@]}; do echo $x; done")
    assert r.stdout == "a\nb\nc\n"


def test_array_quoted_at_preserves_fields(run) -> None:
    r = run('arr=("hi there" world); for x in "${arr[@]}"; do echo "<$x>"; done')
    assert r.stdout == "<hi there>\n<world>\n"


def test_array_star_quoted_joins_with_ifs(run) -> None:
    r = run('arr=(a b c); IFS=,; echo "${arr[*]}"')
    assert r.stdout == "a,b,c\n"


def test_array_append(run) -> None:
    r = run("arr=(a b); arr+=(c d); echo ${arr[@]}")
    assert r.stdout == "a b c d\n"


def test_array_indexed_arith(run) -> None:
    r = run("arr=(x y z); i=1; echo ${arr[$((i+1))]}")
    assert r.stdout == "z\n"


def test_array_keys(run) -> None:
    r = run("arr=(x y z); echo ${!arr[@]}")
    assert r.stdout == "0 1 2\n"


def test_positional_at_quoted(run) -> None:
    r = run('set -- a "b c" d; for x in "$@"; do echo "<$x>"; done')
    assert r.stdout == "<a>\n<b c>\n<d>\n"


def test_positional_count(run) -> None:
    r = run("set -- one two three four; echo $#")
    assert r.stdout == "4\n"


def test_array_via_function_args(run) -> None:
    r = run("""
join_args() {
  for a in "$@"; do
    echo "[$a]"
  done
}
join_args alpha beta gamma
""")
    assert r.stdout == "[alpha]\n[beta]\n[gamma]\n"


def test_array_iteration_with_spaces(run) -> None:
    r = run("""
files=("a b" "c d")
for f in "${files[@]}"; do
  echo "got: $f"
done
""")
    assert r.stdout == "got: a b\ngot: c d\n"


def test_unset_array(run) -> None:
    r = run("arr=(a b c); unset arr; echo ${#arr[@]}")
    assert r.stdout == "0\n"


def test_array_assignment_then_scalar_access(run) -> None:
    # Bare ``$arr`` references element 0.
    r = run('arr=(first second third); echo "$arr"')
    assert r.stdout == "first\n"
