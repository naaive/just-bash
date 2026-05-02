"""Phase-13 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# Here-string + pipeline
# ---------------------------------------------------------------------------


def test_here_string_to_tr() -> None:
    compare(
        "here_string_to_tr",
        """
s="HELLO WORLD"
result=$(tr 'A-Z' 'a-z' <<< "$s")
echo "[$result]"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Aggregate counts via assoc array
# ---------------------------------------------------------------------------


def test_assoc_aggregate_counts() -> None:
    compare(
        "assoc_aggregate_counts",
        """
declare -A counts
items=(red blue red green blue red green green green)
for item in "${items[@]}"; do
  counts[$item]=$(( ${counts[$item]:-0} + 1 ))
done
for k in green red blue; do
  echo "$k: ${counts[$k]}"
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# && / || short-circuit
# ---------------------------------------------------------------------------


def test_short_circuit_and() -> None:
    compare(
        "short_circuit_and",
        """
true && echo ok
false && echo fail
""".strip(),
    )


def test_short_circuit_or() -> None:
    compare(
        "short_circuit_or",
        """
true || echo nope
false || echo fallback
""".strip(),
    )


def test_chain_and_or() -> None:
    compare(
        "chain_and_or",
        """
t() { return "$1"; }
t 0 && echo a || echo b
t 1 && echo c || echo d
""".strip(),
    )


# ---------------------------------------------------------------------------
# Regex match with [[ =~ ]]
# ---------------------------------------------------------------------------


def test_regex_ipv4_basic() -> None:
    compare(
        "regex_ipv4_basic",
        """
for ip in 192.168.1.1 999.0.0.1 not-an-ip; do
  if [[ "$ip" =~ ^[0-9.]+$ ]]; then
    echo "$ip: numeric"
  else
    echo "$ip: no"
  fi
done
""".strip(),
    )


def test_regex_kv_match() -> None:
    compare(
        "regex_kv_match",
        """
s="key=value123"
if [[ "$s" =~ ^[a-z]+=[a-z0-9]+$ ]]; then
  echo "matched"
fi
""".strip(),
    )


# ---------------------------------------------------------------------------
# Heredocs in functions
# ---------------------------------------------------------------------------


def test_heredoc_in_function() -> None:
    compare(
        "heredoc_in_function",
        """
emit() {
  cat <<EOF
[$1]
key=value
nested=${2:-default}
EOF
}
emit alpha
emit beta override
""".strip(),
    )


# ---------------------------------------------------------------------------
# trap EXIT
# ---------------------------------------------------------------------------


def test_trap_exit_runs_handler() -> None:
    compare(
        "trap_exit_runs_handler",
        """
cleanup() { echo "cleanup invoked"; }
trap cleanup EXIT
echo "main work"
exit 0
""".strip(),
    )


# ---------------------------------------------------------------------------
# uniq -c with sort
# ---------------------------------------------------------------------------


def test_uniq_c_sort_n() -> None:
    compare(
        "uniq_c_sort_n",
        """
text=$'apple\\nbanana\\napple\\ncherry\\nbanana\\napple\\ndate'
echo "$text" | sort | uniq -c | sort -nr
""".strip(),
    )


# ---------------------------------------------------------------------------
# Process substitution (default-format diff was changed in this phase).
# ---------------------------------------------------------------------------


def test_diff_normal_default_format() -> None:
    compare(
        "diff_normal_default_format",
        """
printf 'a\\nb\\nc\\n' > /tmp/d1
printf 'a\\nx\\nc\\n' > /tmp/d2
diff /tmp/d1 /tmp/d2
""".strip(),
    )


def test_process_subst_diff() -> None:
    compare(
        "process_subst_diff",
        """
diff <(printf 'a\\nb\\nc\\n') <(printf 'a\\nx\\nc\\n')
""".strip(),
    )


# ---------------------------------------------------------------------------
# Bash 5+ vars
# ---------------------------------------------------------------------------


def test_epochseconds_is_integer() -> None:
    compare(
        "epochseconds_is_integer",
        """
n=$EPOCHSECONDS
[[ "$n" =~ ^[0-9]+$ ]] && echo "ok" || echo "bad"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Real-world scripts
# ---------------------------------------------------------------------------


def test_walk_directory_text() -> None:
    compare(
        "walk_directory_text",
        """
mkdir -p /tmp/walk/sub
echo a > /tmp/walk/x
echo b > /tmp/walk/sub/y
find /tmp/walk -type f | sort
""".strip(),
    )


def test_count_files_per_ext() -> None:
    compare(
        "count_files_per_ext",
        """
mkdir -p /tmp/ext
touch /tmp/ext/a.txt /tmp/ext/b.txt /tmp/ext/c.md /tmp/ext/d.md /tmp/ext/e.md /tmp/ext/f.json
ls /tmp/ext | awk -F. '{print $2}' | sort | uniq -c | sort -nr | sed 's/^ *//'
""".strip(),
    )


def test_basename_with_suffix() -> None:
    compare(
        "basename_with_suffix",
        """
basename /a/b/c.txt
basename /a/b/c.txt .txt
basename /tmp/hello.tar.gz .tar.gz
""".strip(),
    )


def test_dirname_chain() -> None:
    compare(
        "dirname_chain",
        """
p=/usr/local/bin/script.sh
dirname "$p"
dirname "$(dirname "$p")"
""".strip(),
    )


def test_xargs_basic() -> None:
    compare(
        "xargs_basic",
        """
printf 'a\\nb\\nc\\n' | xargs echo
""".strip(),
    )


def test_xargs_n1() -> None:
    compare(
        "xargs_n1",
        """
printf 'a\\nb\\nc\\n' | xargs -n 1 echo
""".strip(),
    )


def test_seq_arithmetic_mix() -> None:
    compare(
        "seq_arithmetic_mix",
        """
sum=0
for n in $(seq 1 10); do
  sum=$((sum + n))
done
echo "$sum"
""".strip(),
    )


def test_redirect_stderr_to_stdout() -> None:
    compare(
        "redirect_stderr_to_stdout_p13",
        """
{ echo out; echo err >&2; } 2>&1 | sort
""".strip(),
    )


def test_function_outer_local_visible() -> None:
    compare(
        "function_outer_local_visible",
        """
outer() {
  local val=outer-val
  inner
}
inner() {
  echo "inner sees: $val"
}
outer
""".strip(),
    )


def test_pipe_into_while() -> None:
    compare(
        "pipe_into_while",
        """
{ echo a; echo b; echo c; } | while read line; do echo "got: $line"; done
""".strip(),
    )


def test_arith_modulo_chain() -> None:
    compare(
        "arith_modulo_chain",
        """
for n in 7 12 19 33 100; do
  printf '%d %% 3 = %d\\n' "$n" $((n % 3))
done
""".strip(),
    )


def test_param_default_in_assignment() -> None:
    compare(
        "param_default_in_assignment",
        """
unset x
y=${x:-fallback}
echo "$y"
x=set
y=${x:-fallback}
echo "$y"
""".strip(),
    )


def test_echo_with_dash_e() -> None:
    compare(
        "echo_with_dash_e",
        r"""echo -e 'tab\there\nline2'""",
    )


def test_string_compare_numeric() -> None:
    compare(
        "string_compare_numeric",
        """
a=10; b=2
[[ "$a" -gt "$b" ]] && echo "a > b numeric"
[[ "$a" > "$b" ]] || echo "a not > b lex"
""".strip(),
    )
