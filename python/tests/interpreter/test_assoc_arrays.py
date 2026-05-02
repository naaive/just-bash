"""Associative array tests."""

from __future__ import annotations


def test_declare_A_and_set(run) -> None:
    r = run('declare -A m; m[name]=alice; m[city]=NYC; echo "${m[name]} ${m[city]}"')
    assert r.stdout == "alice NYC\n"


def test_assoc_keys(run) -> None:
    r = run("""
declare -A m
m[a]=1
m[b]=2
for k in "${!m[@]}"; do
  echo "$k=${m[$k]}"
done
""")
    # Order is dict-insertion order in Python 3.7+; matches typical bash 5.
    assert r.stdout == "a=1\nb=2\n"


def test_assoc_length(run) -> None:
    r = run("declare -A m; m[a]=1; m[b]=2; m[c]=3; echo ${#m[@]}")
    assert r.stdout == "3\n"


def test_assoc_missing_key(run) -> None:
    r = run('declare -A m; m[x]=1; echo "[${m[missing]}]"')
    assert r.stdout == "[]\n"


def test_assoc_overwrite(run) -> None:
    r = run("declare -A m; m[a]=1; m[a]=99; echo ${m[a]}")
    assert r.stdout == "99\n"


def test_assoc_values_iteration(run) -> None:
    r = run("""
declare -A m
m[k1]=alpha
m[k2]=beta
for v in "${m[@]}"; do
  echo "$v"
done
""")
    assert r.stdout == "alpha\nbeta\n"


def test_indexed_array_subscript_assignment(run) -> None:
    r = run('arr[3]=hello; echo "${arr[3]}"; echo "${#arr[@]}"')
    assert r.stdout == "hello\n4\n"


def test_assoc_with_spaces_in_value(run) -> None:
    r = run('declare -A m; m[greet]="hi there"; echo "${m[greet]}"')
    assert r.stdout == "hi there\n"
