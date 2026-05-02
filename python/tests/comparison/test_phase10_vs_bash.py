"""Phase-10 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# extglob in case patterns
# ---------------------------------------------------------------------------


def test_case_extglob_at() -> None:
    compare(
        "case_extglob_at",
        "shopt -s extglob; eval 'case alpha in @(alpha|beta)) echo match;; *) echo no;; esac'",
    )


def test_case_extglob_negate() -> None:
    compare(
        "case_extglob_negate",
        "shopt -s extglob; eval 'case foo.md in !(*.txt)) echo not-txt;; *) echo txt;; esac'",
    )


def test_case_extglob_star() -> None:
    compare(
        "case_extglob_star",
        "shopt -s extglob; eval 'case ababa in *(a|b)) echo all-ab;; *) echo no;; esac'",
    )


def test_case_extglob_plus() -> None:
    compare(
        "case_extglob_plus",
        "shopt -s extglob; eval 'case ddd in +(d)) echo dees;; *) echo no;; esac'",
    )


def test_case_extglob_question() -> None:
    compare(
        "case_extglob_question",
        "shopt -s extglob; "
        """eval 'case "" in ?(x)) echo zero;; *) echo no;; esac' """,
    )


# ---------------------------------------------------------------------------
# Arithmetic with array subscripts
# ---------------------------------------------------------------------------


def test_arith_assoc_subscript() -> None:
    compare(
        "arith_assoc_subscript",
        """
declare -A m
m[a]=10
m[b]=20
total=0
for k in a b; do
  ((total += m[$k]))
done
echo "$total"
""".strip(),
    )


def test_arith_indexed_subscript() -> None:
    compare(
        "arith_indexed_subscript",
        'arr=(10 20 30); ((sum = arr[0] + arr[1] + arr[2])); echo "$sum"',
    )


# ---------------------------------------------------------------------------
# more / less / pager pass-through
# ---------------------------------------------------------------------------


def test_more_passthrough() -> None:
    compare(
        "more_passthrough",
        'printf "line1\\nline2\\n" | more',
    )


def test_less_passthrough() -> None:
    compare(
        "less_passthrough",
        'printf "abc\\n" | less',
    )


# ---------------------------------------------------------------------------
# md5 (BSD-style) and units are not standard on Linux bash CI runners.
# ---------------------------------------------------------------------------


def test_md5_string() -> None:
    import pytest

    pytest.skip("BSD `md5` is unavailable on Linux runners; just-bash provides it directly")


def test_units_kib_to_kb() -> None:
    import pytest

    pytest.skip("real `units` is unavailable in CI; just-bash has a stub table")


# ---------------------------------------------------------------------------
# while-read-from-file-redirection (the bug fixed in this phase).
# ---------------------------------------------------------------------------


def test_while_read_file_loop() -> None:
    compare(
        "while_read_file_loop",
        """
printf 'a\\nb\\nc\\n' > /tmp/lines
while IFS= read -r line; do
  echo "got: $line"
done < /tmp/lines
""".strip(),
    )


def test_while_read_count() -> None:
    compare(
        "while_read_count",
        """
printf 'x\\ny\\nz\\nw\\n' > /tmp/n
n=0
while read -r _; do
  n=$((n + 1))
done < /tmp/n
echo "$n"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Real-world idioms
# ---------------------------------------------------------------------------


def test_calculator_rpn() -> None:
    compare(
        "calculator_rpn",
        """
stack=()
top=-1
RET=0
push() {
  top=$((top + 1))
  stack[$top]=$1
}
pop() {
  RET=${stack[$top]}
  unset 'stack[top]'
  top=$((top - 1))
}
apply() {
  local op=$1
  pop
  local b=$RET
  pop
  local a=$RET
  case "$op" in
    +) push $((a + b)) ;;
    -) push $((a - b)) ;;
  esac
}
push 10
push 5
apply +
push 3
apply -
echo "${stack[$top]}"
""".strip(),
    )


def test_csv_filter_pipeline() -> None:
    compare(
        "csv_filter_pipeline",
        """
printf 'name,score\\nalice,75\\nbob,40\\ncarol,90\\n' \\
  | tail -n +2 \\
  | awk -F, '$2 > 50 {print $1}' \\
  | sort
""".strip(),
    )


def test_assoc_template_render() -> None:
    compare(
        "assoc_template_render",
        """
declare -A v
v[name]=alice
v[age]=30
template='hi ${name} (${age})'
out=$template
for k in "${!v[@]}"; do
  out=${out//\\$\\{$k\\}/${v[$k]}}
done
echo "$out"
""".strip(),
    )


def test_log_threshold_filter() -> None:
    compare(
        "log_threshold_filter",
        """
declare -A rank
rank[DEBUG]=10
rank[INFO]=20
rank[WARN]=30
rank[ERROR]=40
threshold=${rank[INFO]}
for line in "DEBUG x" "INFO y" "WARN z" "ERROR q"; do
  level=${line%% *}
  lvl=${rank[$level]:-0}
  if (( lvl >= threshold )); then
    echo "$line"
  fi
done
""".strip(),
    )


def test_string_table_printf() -> None:
    compare(
        "string_table_printf",
        """
names=(alpha beta gamma)
counts=(7 23 199)
printf '%-8s %5s\\n' name count
for i in "${!names[@]}"; do
  printf '%-8s %5d\\n' "${names[$i]}" "${counts[$i]}"
done
""".strip(),
    )


def test_word_count_topn() -> None:
    compare(
        "word_count_topn",
        """
echo "the fox the dog the cat" \\
  | tr ' ' '\\n' \\
  | sort \\
  | uniq -c \\
  | sort -nr \\
  | head -2 \\
  | sed 's/^ *//'
""".strip(),
    )


def test_ini_parser_basic() -> None:
    compare(
        "ini_parser_basic",
        """
printf '[s]\\nhost=h\\nport=8\\n' > /tmp/c.ini
declare -A s
section=""
while IFS= read -r line; do
  case "$line" in
    \\[*\\])
      section=${line#[}
      section=${section%]}
      ;;
    *=*)
      k=${line%%=*}
      v=${line#*=}
      [[ "$section" == "s" ]] && s[$k]=$v
      ;;
  esac
done < /tmp/c.ini
echo "${s[host]}:${s[port]}"
""".strip(),
    )


def test_required_env_check() -> None:
    compare(
        "required_env_check",
        """
required=(NAME PORT LOG)
NAME=app
PORT=80
missing=()
for v in "${required[@]}"; do
  if [[ -z ${!v:-} ]]; then
    missing+=("$v")
  fi
done
if (( ${#missing[@]} == 0 )); then
  echo ok
else
  echo "missing: ${missing[*]}" >&2
  exit 1
fi
""".strip(),
    )


def test_sysinfo_arith() -> None:
    compare(
        "sysinfo_arith",
        """
mem_mb=8192
secs=12345
mem=$(( mem_mb / 1024 ))
h=$(( secs / 3600 ))
m=$(( (secs % 3600) / 60 ))
printf 'mem=%dGiB up=%dh%dm\\n' "$mem" "$h" "$m"
""".strip(),
    )


def test_array_dedup_sort() -> None:
    compare(
        "array_dedup_sort",
        """
arr=(c a b c a d)
printf '%s\\n' "${arr[@]}" | sort -u
""".strip(),
    )


def test_pipeline_grep_count() -> None:
    compare(
        "pipeline_grep_count",
        """
printf 'INFO a\\nERROR b\\nINFO c\\nWARN d\\nERROR e\\n' \\
  | grep -c '^ERROR'
""".strip(),
    )


def test_nested_brace_expansion_arith() -> None:
    compare(
        "nested_brace_expansion_arith",
        """
total=0
for n in {1..5}; do
  total=$((total + n))
done
echo "$total"
""".strip(),
    )


def test_param_expansion_chain() -> None:
    compare(
        "param_expansion_chain",
        """
path=/a/b/c/file.tar.gz
echo "${path##*/}"
echo "${path%.*}"
echo "${path%%.*}"
echo "${path#*/}"
""".strip(),
    )


def test_subshell_isolation_p10() -> None:
    compare(
        "subshell_isolation_p10",
        """
x=outer
( x=inner; echo "in: $x" )
echo "out: $x"
""".strip(),
    )


def test_function_local_scope() -> None:
    compare(
        "function_local_scope",
        """
v=top
f() {
  local v=local
  echo "f: $v"
}
f
echo "after: $v"
""".strip(),
    )
