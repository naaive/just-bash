"""Comparison tests: just-bash-py output vs real bash, replayed from fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare


def test_simple_echo() -> None:
    compare("simple_echo", "echo hello")


def test_pipe_tr() -> None:
    compare("pipe_tr", "echo hello | tr a-z A-Z")


def test_for_loop() -> None:
    compare("for_loop", "for i in 1 2 3; do echo $i; done")


def test_if_else() -> None:
    compare("if_else", 'if [ -z "" ]; then echo empty; else echo no; fi')


def test_arithmetic_expansion() -> None:
    compare("arith_expansion", "echo $((2 + 3 * 4))")


def test_brace_range() -> None:
    compare("brace_range", "echo {1..5}")


def test_function_call() -> None:
    compare("function_call", 'greet() { echo "hi $1"; }; greet world')


def test_arrays() -> None:
    compare("arrays_at_quoted", 'arr=("a b" c); for x in "${arr[@]}"; do echo "<$x>"; done')


def test_heredoc() -> None:
    compare("heredoc", "cat <<EOF\nhello $USER\nEOF\n")


def test_redirect_then_cat() -> None:
    compare("redirect_then_cat", "echo first > out.txt; echo second >> out.txt; cat out.txt")


def test_grep_basic() -> None:
    compare("grep_basic", 'printf "%s\\n" alpha beta alphabet | grep alpha')


def test_sed_substitute() -> None:
    compare("sed_substitute", 'echo "foo bar foo" | sed "s/foo/baz/g"')


def test_awk_sum() -> None:
    compare("awk_sum", "printf \"%s\\n\" 1 2 3 4 | awk '{ s += $1 } END { print s }'")


def test_sort_uniq() -> None:
    compare("sort_uniq", 'printf "b\\na\\nb\\nc\\na\\n" | sort | uniq')


def test_nested_command_substitution() -> None:
    compare("nested_cmd_sub", 'echo "today is $(echo $(echo monday))"')
