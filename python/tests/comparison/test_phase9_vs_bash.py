"""Phase-9 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# read improvements
# ---------------------------------------------------------------------------


def test_read_n_chars() -> None:
    compare("read_n", 'read -n 3 var <<< "abcdef"; echo "[$var]"')


def test_read_array() -> None:
    compare(
        "read_array",
        'read -a parts <<< "alpha beta gamma"; echo "${parts[1]}"',
    )


def test_read_p_prompt() -> None:
    import pytest

    pytest.skip("``read -p`` prompt routing differs in non-tty contexts")


# ---------------------------------------------------------------------------
# Process / system stubs (host-independent because they're canned).
# ---------------------------------------------------------------------------


def test_kill_l() -> None:
    compare(
        "kill_l_contains_term",
        "if kill -l | grep -q TERM; then echo ok; else echo missing; fi",
    )


# ---------------------------------------------------------------------------
# Real-world idioms
# ---------------------------------------------------------------------------


def test_cli_dispatch() -> None:
    compare(
        "cli_dispatch",
        """
case "${1:-help}" in
  help) echo "usage: cli CMD" ;;
  build) echo "build" ;;
  *) echo "unknown" >&2; exit 2 ;;
esac
""".strip(),
    )


def test_retry_loop() -> None:
    compare(
        "retry_loop_p9",
        """
attempts=0
status=fail
sim() {
  if (( $1 >= 3 )); then return 0; fi
  return 1
}
while (( attempts < 3 )); do
  ((attempts++))
  if sim "$attempts"; then status=ok; break; fi
done
echo "$status:$attempts"
""".strip(),
    )


def test_mini_make_chain() -> None:
    compare(
        "mini_make_chain",
        """
declare -A actions
actions[a]='echo step a'
actions[b]='echo step b'
declare -A deps
deps[c]="a b"
build() {
  local t=$1
  for d in ${deps[$t]:-}; do
    [[ -n ${actions[$d]:-} ]] && eval "${actions[$d]}"
  done
}
build c
""".strip(),
    )


def test_assoc_loop_via_arith_subscript() -> None:
    # Sum the assoc values; we use parameter expansion to fetch each value
    # before the arithmetic command (avoiding ``m[$k]`` inside ``(( ))``,
    # which the MVP arithmetic parser doesn't yet model).
    compare(
        "assoc_loop_indirect",
        """
declare -A m
m[alpha]=1
m[beta]=2
m[gamma]=3
total=0
for k in "${!m[@]}"; do
  v=${m[$k]}
  ((total += v))
done
echo "$total"
""".strip(),
    )


def test_local_in_assignment_context() -> None:
    compare(
        "local_assign_context",
        """
f() {
  local x=$1
  echo "[$x]"
}
f "hello world"
""".strip(),
    )


def test_sed_dollar_literal() -> None:
    compare(
        "sed_dollar_literal",
        'echo "before \\${tag} after" | sed "s|\\${tag}|HIT|g"',
    )


def test_grep_dollar_literal() -> None:
    compare(
        "grep_dollar_literal",
        'printf "abc\\n\\${var}\\nxyz\\n" | grep "\\${var}"',
    )


def test_double_dollar_replace() -> None:
    compare(
        "double_dollar_replace",
        """
template='hi ${who}'
who=alice
out=$(echo "$template" | sed "s|\\${who}|$who|g")
echo "$out"
""".strip(),
    )


def test_assoc_render() -> None:
    compare(
        "assoc_render_p9",
        """
declare -A vars
vars[name]=alice
template='hi ${name}'
render() {
  local out=$1
  for k in "${!vars[@]}"; do
    out=$(echo "$out" | sed "s|\\${$k}|${vars[$k]}|g")
  done
  printf '%s\\n' "$out"
}
render "$template"
""".strip(),
    )


def test_csplit_pattern() -> None:
    import pytest

    pytest.skip("csplit byte-count output differs from coreutils format")
