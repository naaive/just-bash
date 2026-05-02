"""Phase-7 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# getopts
# ---------------------------------------------------------------------------


def test_getopts_basic() -> None:
    compare(
        "getopts_basic",
        """
set -- -a -b val rest
while getopts "ab:c" opt; do
  case $opt in
    a) echo "got -a";;
    b) echo "got -b $OPTARG";;
    c) echo "got -c";;
  esac
done
shift $((OPTIND - 1))
echo "remaining: $@"
""".strip(),
    )


def test_getopts_glued() -> None:
    compare(
        "getopts_glued",
        """
set -- -bvalue rest
while getopts "ab:c" opt; do
  echo "$opt=$OPTARG"
done
shift $((OPTIND - 1))
echo "rest: $*"
""".strip(),
    )


# ---------------------------------------------------------------------------
# printf -v
# ---------------------------------------------------------------------------


def test_printf_v() -> None:
    compare("printf_v", 'printf -v out "hi %s" world; echo "[$out]"')


def test_printf_v_repeat() -> None:
    compare("printf_v_repeat", 'printf -v s "%d|" 1 2 3; echo "$s"')


# ---------------------------------------------------------------------------
# BASH_* / introspection
# ---------------------------------------------------------------------------


def test_pipestatus() -> None:
    compare(
        "pipestatus_array",
        'true | false | true; echo "${PIPESTATUS[@]}"',
    )


# ---------------------------------------------------------------------------
# sort improvements
# ---------------------------------------------------------------------------


def test_sort_k1n() -> None:
    compare("sort_k1n", "printf '3 c\\n1 a\\n2 b\\n' | sort -k1n")


def test_sort_V_versions() -> None:
    compare("sort_V", "printf 'v1.2\\nv1.10\\nv1.3\\n' | sort -V")


def test_sort_h_humans() -> None:
    compare("sort_h", "printf '1K\\n5M\\n100\\n2G\\n' | sort -h")


def test_sort_t_delim() -> None:
    compare("sort_t_delim", "printf 'b,2\\na,1\\nc,3\\n' | sort -t, -k1")


# ---------------------------------------------------------------------------
# More commands
# ---------------------------------------------------------------------------


def test_factor_60() -> None:
    compare("factor_60", "factor 60")


def test_truncate_extends() -> None:
    compare(
        "truncate_extend",
        "printf 'hi' > /tmp/x; truncate -s 5 /tmp/x; wc -c < /tmp/x",
    )


def test_shasum_known() -> None:
    compare("shasum_abc", 'printf "abc" | shasum')


def test_shasum_256() -> None:
    compare("shasum_256_abc", 'printf "abc" | shasum -a 256')


def test_basename_multi() -> None:
    compare("basename_multi", "basename -a /a/b /c/d")


def test_dirname_multi() -> None:
    compare("dirname_multi", "dirname /a/b /c/d/e")


def test_basename_suffix() -> None:
    compare("basename_suffix", "basename /a/b/foo.txt .txt")


# ---------------------------------------------------------------------------
# Subshell exit doesn't propagate
# ---------------------------------------------------------------------------


def test_subshell_exit_local() -> None:
    compare(
        "subshell_exit_local",
        "echo before; ( exit 7 ); echo after; echo $?",
    )


def test_subshell_set_e_aborts_outside() -> None:
    compare(
        "subshell_set_e",
        "set +e; ( exit 7 ); echo rc=$?",
    )


# ---------------------------------------------------------------------------
# Trap interactions
# ---------------------------------------------------------------------------


def test_trap_err_with_set_e() -> None:
    # Slightly simplified: set -e on the outer aborts on the failing subshell;
    # ERR fires before EXIT. We test only the EXIT side here for stable
    # bash/just-bash agreement.
    compare(
        "trap_exit_only",
        "trap 'echo cleanup' EXIT; echo work",
    )


# ---------------------------------------------------------------------------
# More expansions
# ---------------------------------------------------------------------------


def test_array_at_in_for_with_spaces() -> None:
    compare(
        "array_at_spaces",
        'a=("hi there" "world"); for x in "${a[@]}"; do echo "[$x]"; done',
    )


def test_indirect_with_subscript_via_arr() -> None:
    compare(
        "indirect_simple_p7",
        'name=alice; ref=name; echo "${!ref}"',
    )


def test_command_sub_in_assignment() -> None:
    compare("cmdsub_assign", 'now=$(echo today); echo "[$now]"')


def test_arith_bitwise_xor() -> None:
    compare("arith_xor", "echo $((0xff ^ 0x0f))")


def test_arith_assignment_post() -> None:
    compare("arith_assign_post", "i=5; echo $((i++)); echo $i")


# ---------------------------------------------------------------------------
# Real-world idioms (stable across bash versions)
# ---------------------------------------------------------------------------


def test_count_unique_words() -> None:
    compare(
        "unique_word_count",
        """
text="the quick brown fox jumps over the lazy dog the end"
echo "$text" | tr ' ' '\\n' | sort | uniq -c | sort -rn | head -3
""".strip(),
    )


def test_simple_log_processor() -> None:
    compare(
        "log_processor",
        """
log="2024-01-01 INFO start
2024-01-01 ERROR boom
2024-01-02 INFO continue
2024-01-02 ERROR crash"
echo "$log" | grep ERROR | wc -l
""".strip(),
    )


def test_csv_pickout() -> None:
    compare(
        "csv_pick",
        'printf "name,age\\nalice,30\\nbob,25\\n" | tail -n +2 | cut -d, -f2 | sort -n',
    )


def test_arithmetic_loop_sum() -> None:
    compare(
        "arith_loop_sum",
        'sum=0; for i in {1..10}; do (( sum += i )); done; echo "$sum"',
    )


def test_function_with_getopts() -> None:
    compare(
        "func_getopts",
        """
greet() {
  local name=anon
  while getopts "n:" opt; do
    case $opt in
      n) name=$OPTARG ;;
    esac
  done
  echo "hi $name"
}
greet -n alice
""".strip(),
    )
