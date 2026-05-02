"""Phase-3 comparison tests: more behaviour pinned to real bash output."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# parameter expansion
# ---------------------------------------------------------------------------


def test_param_default() -> None:
    compare("param_default", 'unset x; echo "${x:-fallback}"')


def test_param_assign_default() -> None:
    compare("param_assign_default", 'unset x; echo "${x:=set}"; echo "$x"')


def test_param_alternate() -> None:
    compare("param_alt", 'x=hello; echo "${x:+yes}"; unset x; echo "${x:+yes}"')


def test_param_length() -> None:
    compare("param_length", 'x=hello; echo "${#x}"')


def test_param_substring() -> None:
    compare("param_substring", 'x=helloworld; echo "${x:5}"; echo "${x:0:5}"')


def test_param_pattern_remove_prefix() -> None:
    compare("param_remove_prefix", 'x=foo.bar.baz; echo "${x#*.}"; echo "${x##*.}"')


def test_param_pattern_remove_suffix() -> None:
    compare("param_remove_suffix", 'x=foo.bar.baz; echo "${x%.*}"; echo "${x%%.*}"')


def test_param_pattern_replace_all() -> None:
    compare("param_replace_all", 's=hello; echo "${s//l/L}"')


def test_param_pattern_replace_first() -> None:
    compare("param_replace_first", 's=hello; echo "${s/l/L}"')


# ---------------------------------------------------------------------------
# arithmetic
# ---------------------------------------------------------------------------


def test_arith_complex() -> None:
    compare("arith_complex", "echo $(( (1 + 2) * 3 - 4 / 2 ))")


def test_arith_modulo() -> None:
    compare("arith_modulo", "echo $((17 % 5))")


def test_arith_bitops() -> None:
    compare("arith_bitops", "echo $((0xff & 0x0f)); echo $((1 << 4)); echo $((255 >> 4))")


def test_arith_postinc() -> None:
    compare("arith_postinc", "i=5; echo $((i++)); echo $i")


def test_arith_ternary() -> None:
    compare("arith_ternary", "x=10; echo $(( x > 5 ? 100 : 200 ))")


# ---------------------------------------------------------------------------
# control flow
# ---------------------------------------------------------------------------


def test_nested_for() -> None:
    compare(
        "nested_for",
        """
for i in 1 2; do
  for j in a b; do
    echo "$i$j"
  done
done
""".strip(),
    )


def test_while_with_counter() -> None:
    compare(
        "while_counter",
        """
i=0
while (( i < 3 )); do
  echo "i=$i"
  ((i++))
done
""".strip(),
    )


def test_case_with_glob_and_default() -> None:
    compare(
        "case_glob_default",
        """
for x in apple banana cherry; do
  case $x in
    a*) echo "A: $x" ;;
    b*|c*) echo "BC: $x" ;;
    *) echo "other" ;;
  esac
done
""".strip(),
    )


def test_function_with_local_var() -> None:
    compare(
        "function_local",
        """
greet() {
  local name=$1
  echo "Hello, $name!"
}
name=outside
greet alice
echo "still: $name"
""".strip(),
    )


def test_function_recursion() -> None:
    compare(
        "function_recursion",
        """
fact() {
  if (( $1 <= 1 )); then
    echo 1
  else
    local sub=$(fact $(( $1 - 1 )))
    echo $(( $1 * sub ))
  fi
}
fact 5
""".strip(),
    )


# ---------------------------------------------------------------------------
# arrays
# ---------------------------------------------------------------------------


def test_array_iteration_at_quoted() -> None:
    compare(
        "array_iter",
        """
arr=("hi there" world)
for x in "${arr[@]}"; do
  echo "<$x>"
done
""".strip(),
    )


def test_array_length_indexed() -> None:
    compare("array_length", "arr=(a b c d e); echo ${#arr[@]}")


def test_array_append() -> None:
    compare("array_append", 'arr=(a b); arr+=(c d); echo "${arr[@]}"')


# ---------------------------------------------------------------------------
# heredoc
# ---------------------------------------------------------------------------


def test_heredoc_with_arith() -> None:
    compare(
        "heredoc_arith",
        """
n=5
cat <<EOF
result is $((n * 2))
EOF
""".strip(),
    )


def test_heredoc_strip_tabs_real() -> None:
    compare(
        "heredoc_strip",
        "cat <<-END\n\tfirst\n\tsecond\n\tEND\n",
    )


# ---------------------------------------------------------------------------
# pipelines + redirects
# ---------------------------------------------------------------------------


def test_pipeline_with_grep_count() -> None:
    compare(
        "pipe_grep_count",
        'printf "%s\\n" alpha beta alphabet gamma alpaca | grep -c alpha',
    )


def test_pipeline_with_awk_count() -> None:
    compare(
        "pipe_awk_count",
        "printf \"%s\\n\" 10 20 30 | awk '{ s += $1 } END { print s, NR }'",
    )


def test_redirect_2_to_1() -> None:
    compare("redirect_2_to_1", "(echo out; echo err >&2) 2>&1 | wc -l")


def test_pipefail_unset_default() -> None:
    compare("pipe_default_status", "false | true; echo $?")


# ---------------------------------------------------------------------------
# command sub
# ---------------------------------------------------------------------------


def test_cmd_sub_in_loop() -> None:
    compare(
        "cmd_sub_loop",
        """
for w in $(echo alpha beta gamma); do
  echo "[$w]"
done
""".strip(),
    )


def test_cmd_sub_strips_trailing_newline() -> None:
    compare("cmd_sub_strip", 'x=$(printf "abc\\n\\n\\n"); echo "[$x]"')


# ---------------------------------------------------------------------------
# text utilities
# ---------------------------------------------------------------------------


def test_sort_numeric() -> None:
    compare("sort_n", 'printf "%s\\n" 3 11 2 22 1 | sort -n')


def test_uniq_count() -> None:
    compare("uniq_count", 'printf "a\\na\\nb\\nc\\nc\\nc\\n" | uniq -c')


def test_cut_fields() -> None:
    compare(
        "cut_fields",
        'printf "a:b:c\\n1:2:3\\n" | cut -d: -f2,3',
    )


def test_tr_squeeze() -> None:
    compare("tr_squeeze", 'echo "hello   world  done" | tr -s " "')


def test_wc_l_w_c() -> None:
    compare("wc_lwc", 'printf "%s\\n" "a b c" "d e" | wc -l -w -c')
