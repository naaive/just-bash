"""Phase-11 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# read combined short flags (the bug fixed in this phase).
# ---------------------------------------------------------------------------


def test_read_ra_combined_flag() -> None:
    compare(
        "read_ra_combined_flag",
        """
inner='a,b,c,d'
IFS=',' read -ra arr <<< "$inner"
echo "${#arr[@]}"
echo "${arr[1]}"
""".strip(),
    )


def test_read_rn_combined_flag() -> None:
    compare(
        "read_rn_combined_flag",
        """
read -rn 3 var <<< "abcdef"
echo "[$var]"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Recursive function
# ---------------------------------------------------------------------------


def test_factorial_recursive() -> None:
    compare(
        "factorial_recursive",
        """
fact() {
  if (( $1 <= 1 )); then
    echo 1
    return
  fi
  local prev
  prev=$(fact $(( $1 - 1 )))
  echo $(( $1 * prev ))
}
fact 6
""".strip(),
    )


# ---------------------------------------------------------------------------
# C-style arithmetic for-loop
# ---------------------------------------------------------------------------


def test_arith_for_sum_squares() -> None:
    compare(
        "arith_for_sum_squares",
        """
sum=0
for ((i = 1; i <= 5; i++)); do
  sum=$((sum + i * i))
done
echo "$sum"
""".strip(),
    )


def test_arith_for_nested_table() -> None:
    compare(
        "arith_for_nested_table",
        """
for ((r = 1; r <= 3; r++)); do
  for ((c = 1; c <= 3; c++)); do
    printf '%3d ' "$((r * c))"
  done
  printf '\\n'
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# break / continue
# ---------------------------------------------------------------------------


def test_break_continue_filter() -> None:
    compare(
        "break_continue_filter",
        """
result=()
for i in 1 2 3 4 5 6 7 8 9 10; do
  if (( i % 2 == 0 )); then
    continue
  fi
  if (( i > 7 )); then
    break
  fi
  result+=("$i")
done
echo "${result[*]}"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Heredocs
# ---------------------------------------------------------------------------


def test_heredoc_with_subst() -> None:
    compare(
        "heredoc_with_subst",
        """
name=alice
cat <<EOF
hello $name
EOF
""".strip(),
    )


def test_heredoc_no_subst() -> None:
    compare(
        "heredoc_no_subst",
        """
name=alice
cat <<'EOF'
hello $name
EOF
""".strip(),
    )


def test_heredoc_strip_tabs() -> None:
    compare(
        "heredoc_strip_tabs",
        """
n=3
cat <<-EOF
\t\t(stripped)
\t\tcount is $n
\tEOF
""".strip(),
    )


# ---------------------------------------------------------------------------
# Nested case
# ---------------------------------------------------------------------------


def test_nested_case_classify() -> None:
    compare(
        "nested_case_classify",
        """
classify() {
  local x=$1
  case "$x" in
    [0-9])
      case "$x" in
        0) echo zero ;;
        [1-9]) echo digit ;;
      esac
      ;;
    [a-z]) echo lower ;;
    [A-Z]) echo upper ;;
    *) echo other ;;
  esac
}
for v in 0 5 a Z !; do
  classify "$v"
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# printf
# ---------------------------------------------------------------------------


def test_printf_format_reuse() -> None:
    compare(
        "printf_format_reuse",
        "printf '%-6s %3d\\n' alpha 1 beta 22 gamma 333",
    )


def test_printf_hex_oct() -> None:
    compare(
        "printf_hex_oct",
        "printf 'hex=%x oct=%o\\n' 255 8",
    )


def test_printf_brackets() -> None:
    compare(
        "printf_brackets",
        "printf '[%s]\\n' a b c",
    )


# ---------------------------------------------------------------------------
# JSON-like text munging via parameter expansion
# ---------------------------------------------------------------------------


def test_json_like_extract() -> None:
    compare(
        "json_like_extract",
        """
blob='{"name":"alice","age":30}'
inner=${blob#\\{}
inner=${inner%\\}}
IFS=',' read -ra pairs <<< "$inner"
for p in "${pairs[@]}"; do
  k=${p%%:*}
  v=${p#*:}
  k=${k//\\"/}
  v=${v//\\"/}
  printf '%s -> %s\\n' "$k" "$v"
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# Pipeline → mapfile → array
# ---------------------------------------------------------------------------


def test_pipeline_to_array() -> None:
    compare(
        "pipeline_to_array",
        """
text=$'banana\\napple\\nbanana\\ncherry\\napple'
mapfile -t fruits < <(echo "$text" | sort -u)
echo "count=${#fruits[@]}"
for f in "${fruits[@]}"; do
  printf 'item: %s\\n' "$f"
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# Real-world mini-tools
# ---------------------------------------------------------------------------


def test_uniq_count_top() -> None:
    compare(
        "uniq_count_top",
        """
echo "the fox the dog the cat" \\
  | tr ' ' '\\n' \\
  | sort \\
  | uniq -c \\
  | sort -nr \\
  | head -1 \\
  | sed 's/^ *//'
""".strip(),
    )


def test_arith_string_padding() -> None:
    compare(
        "arith_string_padding",
        """
for n in 7 42 1234; do
  printf '%05d\\n' "$n"
done
""".strip(),
    )


def test_string_slice_offset() -> None:
    compare(
        "string_slice_offset",
        """
s="Hello, World!"
echo "${s:7}"
echo "${s:7:5}"
echo "${s:0:5}"
""".strip(),
    )


def test_associative_keys_sorted() -> None:
    compare(
        "associative_keys_sorted",
        """
declare -A m
m[bravo]=2
m[alpha]=1
m[charlie]=3
for k in $(echo "${!m[@]}" | tr ' ' '\\n' | sort); do
  echo "$k=${m[$k]}"
done
""".strip(),
    )


def test_arith_until_loop() -> None:
    compare(
        "arith_until_loop",
        """
n=0
until (( n >= 4 )); do
  echo "n=$n"
  n=$((n + 1))
done
""".strip(),
    )


def test_string_reverse_via_rev() -> None:
    compare(
        "string_reverse_via_rev",
        'echo "abcdef" | rev',
    )


def test_concat_with_dollar_at() -> None:
    compare(
        "concat_with_dollar_at",
        """
join_args() {
  local IFS=,
  echo "$*"
}
join_args alpha beta gamma
""".strip(),
    )


def test_default_param_expansion() -> None:
    compare(
        "default_param_expansion",
        """
unset undef
echo "${undef:-fallback}"
echo "${undef:=assigned}"
echo "$undef"
echo "${set:-shouldnt-show}"
""".strip(),
    )


def test_brace_range_step() -> None:
    compare(
        "brace_range_step",
        "echo {1..10..2}",
    )


def test_brace_alpha_range() -> None:
    compare(
        "brace_alpha_range",
        "echo {a..g}",
    )


def test_command_substitution_arith() -> None:
    compare(
        "command_substitution_arith",
        """
n=$(echo 5)
echo $((n * 7))
""".strip(),
    )
