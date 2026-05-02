"""Phase-14 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# Nameref
# ---------------------------------------------------------------------------


def test_nameref_basic() -> None:
    compare(
        "nameref_basic",
        """
target=hello
declare -n ref=target
echo "$ref"
ref=updated
echo "$target"
""".strip(),
    )


def test_nameref_swap() -> None:
    compare(
        "nameref_swap",
        """
a=alpha
b=beta
swap() {
  local -n x=$1
  local -n y=$2
  local tmp=$x
  x=$y
  y=$tmp
}
swap a b
echo "a=$a"
echo "b=$b"
""".strip(),
    )


def test_nameref_assoc_via_function() -> None:
    compare(
        "nameref_assoc_via_function",
        """
declare -A counts
bump() {
  local -n m=$1
  local key=$2
  m[$key]=$(( ${m[$key]:-0} + 1 ))
}
for c in red red blue green red blue; do
  bump counts "$c"
done
for k in red green blue; do
  echo "$k: ${counts[$k]}"
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# pipefail
# ---------------------------------------------------------------------------


def test_pipefail_first_stage_fails_p14() -> None:
    compare(
        "pipefail_first_stage_fails_p14",
        """
set -o pipefail
false | true
echo "rc=$?"
""".strip(),
    )


def test_pipefail_off_swallows_failure() -> None:
    compare(
        "pipefail_off_swallows_failure",
        """
false | true
echo "rc=$?"
""".strip(),
    )


def test_pipefail_toggle() -> None:
    compare(
        "pipefail_toggle",
        """
set -o pipefail
false | true
echo "on=$?"
set +o pipefail
false | true
echo "off=$?"
""".strip(),
    )


# ---------------------------------------------------------------------------
# printf %q
# ---------------------------------------------------------------------------


def test_printf_q_safe() -> None:
    compare(
        "printf_q_safe",
        "printf '%q\\n' hello",
    )


def test_printf_q_with_space() -> None:
    compare(
        "printf_q_with_space",
        """printf '%q\\n' 'hello world'""",
    )


def test_printf_q_round_trip() -> None:
    compare(
        "printf_q_round_trip",
        """
original="hello world's"
quoted=$(printf '%q' "$original")
eval "echoed=$quoted"
[[ "$echoed" == "$original" ]] && echo ok || echo bad
""".strip(),
    )


# ---------------------------------------------------------------------------
# printf %b / %f
# ---------------------------------------------------------------------------


def test_printf_b_escapes() -> None:
    compare(
        "printf_b_escapes",
        r"""printf '%b\n' 'a\tb\nc'""",
    )


def test_printf_f_floats() -> None:
    compare(
        "printf_f_floats",
        "printf '%.3f %.0f\\n' 3.14159 99.5",
    )


# ---------------------------------------------------------------------------
# Combined: pipefail + set -e + ||
# ---------------------------------------------------------------------------


def test_pipefail_e_with_or() -> None:
    compare(
        "pipefail_e_with_or",
        """
set -e
set -o pipefail
echo before
( exit 7 ) | cat || echo "caught: $?"
echo after
""".strip(),
    )


# ---------------------------------------------------------------------------
# Misc real-world patterns
# ---------------------------------------------------------------------------


def test_default_value_chain_p14() -> None:
    compare(
        "default_value_chain_p14",
        """
unset a
unset b
echo "${a:-${b:-fallback}}"
b=BB
echo "${a:-${b:-fallback}}"
a=AA
echo "${a:-${b:-fallback}}"
""".strip(),
    )


def test_array_append_compound() -> None:
    compare(
        "array_append_compound",
        """
arr=(a b)
arr+=(c d)
arr+=(e)
echo "${arr[@]}"
echo "len=${#arr[@]}"
""".strip(),
    )


def test_associative_iter_then_total() -> None:
    compare(
        "associative_iter_then_total",
        """
declare -A m
m[a]=1
m[b]=2
m[c]=3
total=0
for k in $(echo "${!m[@]}" | tr ' ' '\\n' | sort); do
  total=$((total + m[$k]))
done
echo "$total"
""".strip(),
    )


def test_dollar_at_in_function() -> None:
    compare(
        "dollar_at_in_function",
        """
show() {
  echo "count=$#"
  for arg in "$@"; do
    echo "[$arg]"
  done
}
show alpha "two words" beta
""".strip(),
    )


def test_arith_logical_and_or() -> None:
    compare(
        "arith_logical_and_or",
        """
a=1; b=0
echo $(( a && b ))
echo $(( a || b ))
echo $(( !a ))
echo $(( !b ))
""".strip(),
    )


def test_arith_ternary_in_assignment() -> None:
    compare(
        "arith_ternary_in_assignment",
        """
n=5
sign=$(( n > 0 ? 1 : (n < 0 ? -1 : 0) ))
echo "$sign"
n=-3
sign=$(( n > 0 ? 1 : (n < 0 ? -1 : 0) ))
echo "$sign"
n=0
sign=$(( n > 0 ? 1 : (n < 0 ? -1 : 0) ))
echo "$sign"
""".strip(),
    )


def test_nested_command_substitution() -> None:
    compare(
        "nested_command_substitution",
        """
n=$(echo $(echo $(echo 5)))
echo "$n"
""".strip(),
    )


def test_brace_expansion_with_prefix() -> None:
    compare(
        "brace_expansion_with_prefix",
        "echo file{1..3}.txt",
    )


def test_command_v_succeeds_for_builtin() -> None:
    compare(
        "command_v_succeeds_for_builtin",
        """
command -v echo > /dev/null && echo found
command -v this_command_does_not_exist > /dev/null || echo missing
""".strip(),
    )


def test_indirect_param_expansion() -> None:
    compare(
        "indirect_param_expansion",
        """
target=value
ref=target
echo "${!ref}"
""".strip(),
    )


def test_string_uppercase_lowercase() -> None:
    compare(
        "string_uppercase_lowercase",
        """
s="Hello World"
echo "${s^^}"
echo "${s,,}"
echo "${s^}"
echo "${s,}"
""".strip(),
    )
