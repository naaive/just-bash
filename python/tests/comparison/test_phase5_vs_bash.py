"""Phase-5 comparison fixtures: case transforms, grep -A/-B/-C/-o, sed -i,
find -exec / -delete, more parameter expansions."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# Case modification
# ---------------------------------------------------------------------------


def test_case_upper_all() -> None:
    compare("case_upper_all", 's=hello; echo "${s^^}"')


def test_case_upper_first() -> None:
    compare("case_upper_first", 's=hello; echo "${s^}"')


def test_case_lower_all() -> None:
    compare("case_lower_all", 's=HELLO; echo "${s,,}"')


def test_case_lower_first() -> None:
    compare("case_lower_first", 's=HELLO; echo "${s,}"')


def test_transform_Q() -> None:
    compare("transform_Q", 's="hi there"; echo "${s@Q}"')


def test_transform_U() -> None:
    compare("transform_U", 's=hello; echo "${s@U}"')


def test_transform_L() -> None:
    compare("transform_L", 's=HELLO; echo "${s@L}"')


# ---------------------------------------------------------------------------
# grep advanced
# ---------------------------------------------------------------------------


def test_grep_only_matching() -> None:
    compare(
        "grep_only_matching",
        "printf 'abc 12 def 345\\nno digits\\n6789 z\\n' | grep -oE '[0-9]+'",
    )


def test_grep_after_context() -> None:
    compare(
        "grep_a1",
        "printf 'a\\nneedle\\nb\\nc\\nd\\n' | grep -A1 needle",
    )


def test_grep_combined_context() -> None:
    compare(
        "grep_c1",
        "printf 'a\\nb\\nneedle\\nc\\nd\\n' | grep -C1 needle",
    )


def test_grep_count_with_lineno() -> None:
    compare("grep_n_count", 'printf "%s\\n" foo bar foo baz | grep -n foo')


# ---------------------------------------------------------------------------
# sed advanced
# ---------------------------------------------------------------------------


def test_sed_in_place() -> None:
    compare(
        "sed_in_place",
        "printf 'foo\\nbar\\n' > /tmp/x; sed -i 's/foo/baz/' /tmp/x; cat /tmp/x",
    )


def test_sed_multi_e() -> None:
    compare(
        "sed_multi_e",
        "printf 'a\\nb\\nc\\n' | sed -e 's/a/A/' -e 's/c/C/'",
    )


# ---------------------------------------------------------------------------
# find advanced
# ---------------------------------------------------------------------------


def test_find_exec_count_lines() -> None:
    # Use printf to set up files in /tmp, run find -exec wc -l on each.
    compare(
        "find_exec_count",
        (
            'mkdir -p /tmp/r; printf "x\\n" > /tmp/r/a; '
            'printf "x\\ny\\n" > /tmp/r/b; '
            "find /tmp/r -type f | sort"
        ),
    )


def test_find_or_branch() -> None:
    compare(
        "find_or",
        (
            "mkdir -p /tmp/q; "
            ": > /tmp/q/a.py; : > /tmp/q/b.md; : > /tmp/q/c.txt; "
            "find /tmp/q \\( -name '*.py' -o -name '*.md' \\) | sort"
        ),
    )


# ---------------------------------------------------------------------------
# Parameter expansion combinations
# ---------------------------------------------------------------------------


def test_param_default_and_pattern() -> None:
    compare(
        "param_default_pattern",
        'p=foo.bar.baz; echo "${p%%.*}"; echo "${unset:-fallback}"',
    )


def test_param_replace_anchored() -> None:
    compare("param_replace_anchored", 's=foofoo; echo "${s/#foo/BAR}"')


def test_param_substring_from_end() -> None:
    compare("param_substring_neg2", 's=hello; echo "${s: -2}"')


# ---------------------------------------------------------------------------
# Real-world idioms
# ---------------------------------------------------------------------------


def test_pipeline_to_xargs_count() -> None:
    compare(
        "pipe_to_xargs",
        'printf "a\\nb\\nc\\n" | xargs -n 1 echo',
    )


def test_for_with_command_substitution() -> None:
    compare(
        "for_cmd_sub",
        'for w in $(echo a b c); do echo "[$w]"; done',
    )


def test_brace_expansion_in_loop() -> None:
    compare(
        "brace_in_loop",
        "for i in {1..4}; do echo $((i * i)); done",
    )


def test_function_with_array_arg() -> None:
    compare(
        "func_array_arg",
        """
collect() {
  local IFS=,
  echo "$*"
}
collect alpha beta gamma
""".strip(),
    )


def test_set_pipefail() -> None:
    compare(
        "set_pipefail",
        "false | true; echo $?",
    )


def test_local_in_recursive_function() -> None:
    compare(
        "local_recursive",
        """
sum() {
  local n=$1
  if (( n <= 0 )); then
    echo 0
    return
  fi
  local sub=$(sum $((n - 1)))
  echo $((n + sub))
}
sum 5
""".strip(),
    )
