"""Phase-6 comparison fixtures pinning indirect / mapfile / new commands."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# Indirect expansion
# ---------------------------------------------------------------------------


def test_indirect_simple() -> None:
    compare("indirect_simple", 'x=hello; ref=x; echo "${!ref}"')


def test_indirect_with_default() -> None:
    compare("indirect_default", 'ref=missing; echo "${!ref:-fallback}"')


def test_indirect_through_function() -> None:
    compare(
        "indirect_func",
        """
greet() {
  local var=$1
  echo "${!var}"
}
hello=world
greet hello
""".strip(),
    )


def test_name_prefix_at_iter_sorted() -> None:
    compare(
        "name_prefix_iter",
        'foo_a=1; foo_b=2; bar=3; for n in "${!foo_@}"; do echo "$n=${!n}"; done | sort',
    )


# ---------------------------------------------------------------------------
# mapfile
# ---------------------------------------------------------------------------


def test_mapfile_simple() -> None:
    compare(
        "mapfile_t",
        'printf "a\\nb\\nc\\n" | { mapfile -t arr; echo "${arr[@]}"; }',
    )


def test_mapfile_count() -> None:
    compare(
        "mapfile_n",
        'printf "1\\n2\\n3\\n4\\n" | { mapfile -t -n 2 arr; echo "${#arr[@]}"; }',
    )


# ---------------------------------------------------------------------------
# Common script idioms
# ---------------------------------------------------------------------------


def test_count_word_occurrences() -> None:
    compare(
        "word_count",
        """
text="alpha beta alpha gamma alpha beta"
echo "$text" | tr ' ' '\\n' | sort | uniq -c | sort -rn
""".strip(),
    )


def test_recursive_factorial_loop() -> None:
    compare(
        "fact_loop",
        """
fact() {
  if (( $1 <= 1 )); then
    echo 1
  else
    local sub=$(fact $(($1 - 1)))
    echo $(($1 * sub))
  fi
}
for i in {1..5}; do
  echo "$i! = $(fact $i)"
done
""".strip(),
    )


def test_assoc_iteration_sorted_phase6() -> None:
    compare(
        "assoc_iter_p6",
        """
declare -A m
m[apple]=1
m[banana]=2
m[cherry]=3
for k in "${!m[@]}"; do
  echo "$k=${m[$k]}"
done | sort
""".strip(),
    )


def test_param_chain_with_indirect() -> None:
    compare(
        "indirect_chain",
        'a=hello; b=a; c=b; echo "${!c}"; echo "${!b}"',
    )


def test_brace_expansion_with_step() -> None:
    compare("brace_step", "echo {1..10..2}")


def test_brace_expansion_alpha_step() -> None:
    compare("brace_alpha_step", "echo {a..h..2}")


def test_arithmetic_negative_modulo() -> None:
    compare("arith_neg_mod", "echo $((-7 % 3))")


def test_pipeline_chain_status() -> None:
    compare(
        "pipe_chain_status",
        "true | true | false; echo $?",
    )


def test_grep_E_alternation() -> None:
    compare(
        "grep_E_alt",
        'printf "%s\\n" foo bar baz | grep -E "foo|baz"',
    )


def test_sed_subst_with_groups() -> None:
    compare(
        "sed_groups",
        'echo abc123 | sed -E "s/([a-z]+)([0-9]+)/\\\\2-\\\\1/"',
    )


def test_awk_NR_NF() -> None:
    compare(
        "awk_nr_nf",
        "printf \"a b c\\nd e\\n\" | awk '{ print NR, NF, $1 }'",
    )


def test_awk_split_assoc() -> None:
    compare(
        "awk_split_assoc",
        """
awk 'BEGIN {
  n = split("a:b:c:a:b", parts, ":")
  for (i = 1; i <= n; i++) counts[parts[i]]++
  for (k in counts) print k, counts[k]
}' | sort
""".strip(),
    )


def test_for_in_with_glob() -> None:
    compare(
        "for_glob",
        """
mkdir -p /tmp/g
: > /tmp/g/a.txt
: > /tmp/g/b.txt
for f in /tmp/g/*.txt; do
  echo "$f"
done | sort
""".strip(),
    )


def test_redirect_append_then_cat() -> None:
    compare(
        "redirect_append",
        ": > /tmp/log; echo first >> /tmp/log; echo second >> /tmp/log; cat /tmp/log",
    )


def test_function_with_local_array() -> None:
    compare(
        "func_local_array",
        """
join_args() {
  local IFS=,
  echo "$*"
}
join_args alpha beta gamma
""".strip(),
    )


def test_set_e_with_or_does_not_abort() -> None:
    compare(
        "set_e_or",
        "set -e; false || true; echo survived",
    )


def test_trap_exit_after_function() -> None:
    compare(
        "trap_exit_func",
        """
cleanup() { echo "cleaned"; }
trap cleanup EXIT
echo "main"
""".strip(),
    )


def test_case_with_pipe_alts() -> None:
    compare(
        "case_pipe_alts",
        """
for x in apple ant beer butter cherry; do
  case $x in
    a*)  echo "A: $x" ;;
    b*)  echo "B: $x" ;;
    *)   echo "?: $x" ;;
  esac
done
""".strip(),
    )


def test_arithmetic_inside_arith_inside_arith() -> None:
    compare(
        "arith_nested",
        "echo $(( $(($((1 + 2)) * 3)) + 4 ))",
    )


def test_redirect_block_to_file() -> None:
    compare(
        "redirect_block",
        "{ echo a; echo b; echo c; } > /tmp/blk; cat /tmp/blk",
    )
