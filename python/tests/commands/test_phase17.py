"""Phase-17 tests: declare -A / declare -a compound initialization."""

from __future__ import annotations


def test_assoc_compound_init_inline(run) -> None:
    r = run("""
declare -A m=([alpha]=1 [beta]=2 [gamma]=3)
echo "${m[alpha]}"
echo "${m[beta]}"
echo "${m[gamma]}"
""")
    assert r.stdout == "1\n2\n3\n"


def test_assoc_compound_init_multiline(run) -> None:
    r = run("""
declare -A vars=(
  [name]=alice
  [project]=just-bash
)
echo "${vars[name]}"
echo "${vars[project]}"
""")
    assert r.stdout == "alice\njust-bash\n"


def test_assoc_compound_init_quoted_values(run) -> None:
    r = run("""
declare -A m=([greeting]="hello world" [farewell]="see you")
echo "${m[greeting]}"
echo "${m[farewell]}"
""")
    assert r.stdout == "hello world\nsee you\n"


def test_indexed_compound_init_via_declare(run) -> None:
    r = run("""
declare -a arr=(alpha beta gamma)
echo "${arr[0]}"
echo "${arr[1]}"
echo "${arr[2]}"
echo "len=${#arr[@]}"
""")
    assert r.stdout == "alpha\nbeta\ngamma\nlen=3\n"


def test_local_assoc_compound_init(run) -> None:
    r = run("""
f() {
  local -A m=([a]=1 [b]=2)
  echo "${m[a]}+${m[b]}"
}
f
""")
    assert r.stdout == "1+2\n"


def test_assoc_compound_iteration(run) -> None:
    r = run("""
declare -A m=([alpha]=1 [beta]=2 [gamma]=3)
for k in $(echo "${!m[@]}" | tr ' ' '\\n' | sort); do
  echo "$k=${m[$k]}"
done
""")
    assert r.stdout == "alpha=1\nbeta=2\ngamma=3\n"
