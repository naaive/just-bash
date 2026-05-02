"""End-to-end interpreter behavior on simple scripts."""

from __future__ import annotations

import pytest


def test_echo(run) -> None:
    r = run("echo hello world")
    assert r.stdout == "hello world\n"
    assert r.exit_code == 0


def test_echo_n(run) -> None:
    r = run("echo -n hello")
    assert r.stdout == "hello"


def test_echo_e(run) -> None:
    r = run('echo -e "a\\tb"')
    assert r.stdout == "a\tb\n"


def test_pipe(run) -> None:
    r = run("echo hello | tr a-z A-Z")
    assert r.stdout == "HELLO\n"


def test_variable_assignment_and_expansion(run) -> None:
    r = run('x=hello; echo "value $x"')
    assert r.stdout == "value hello\n"


def test_braced_param_default(run) -> None:
    r = run('echo "${UNSET:-fallback}"')
    assert r.stdout == "fallback\n"


def test_braced_param_length(run) -> None:
    r = run("x=hello; echo ${#x}")
    assert r.stdout == "5\n"


def test_pattern_removal_prefix(run) -> None:
    r = run("p=foo.bar; echo ${p#*.}")
    assert r.stdout == "bar\n"


def test_pattern_removal_suffix(run) -> None:
    r = run("p=foo.bar; echo ${p%.*}")
    assert r.stdout == "foo\n"


def test_pattern_replacement_all(run) -> None:
    r = run('s=hello; echo "${s//l/L}"')
    assert r.stdout == "heLLo\n"


def test_substring(run) -> None:
    r = run('s=hello; echo "${s:1:3}"')
    assert r.stdout == "ell\n"


def test_command_substitution(run) -> None:
    r = run('x=$(echo hi); echo "got $x"')
    assert r.stdout == "got hi\n"


def test_arithmetic_expansion(run) -> None:
    r = run("echo $((2 + 3 * 4))")
    assert r.stdout == "14\n"


def test_arithmetic_assignment(run) -> None:
    r = run("(( x = 5 + 3 )); echo $x")
    assert r.stdout == "8\n"


def test_arithmetic_command_truthy(run) -> None:
    r = run("if (( 1 + 1 == 2 )); then echo yes; fi")
    assert r.stdout == "yes\n"


def test_if_else(run) -> None:
    r = run("if false; then echo a; else echo b; fi")
    assert r.stdout == "b\n"


def test_for_loop(run) -> None:
    r = run("for i in 1 2 3; do echo $i; done")
    assert r.stdout == "1\n2\n3\n"


def test_while_loop_with_arithmetic(run) -> None:
    r = run("i=0; while (( i < 3 )); do echo $i; (( i++ )); done")
    assert r.stdout == "0\n1\n2\n"


def test_until_loop(run) -> None:
    r = run("i=0; until (( i >= 3 )); do echo $i; (( i++ )); done")
    assert r.stdout == "0\n1\n2\n"


def test_case_match(run) -> None:
    r = run("case foo in bar) echo nope ;; foo) echo yep ;; *) echo other ;; esac")
    assert r.stdout == "yep\n"


def test_case_glob_pattern(run) -> None:
    r = run("case foobar in foo*) echo prefix ;; *) echo no ;; esac")
    assert r.stdout == "prefix\n"


def test_function_call(run) -> None:
    r = run('greet() { echo "hi $1"; }; greet world')
    assert r.stdout == "hi world\n"


def test_function_local_var(run) -> None:
    r = run('outer() { local x=inside; echo "$x"; }; x=outside; outer; echo "$x"')
    assert r.stdout == "inside\noutside\n"


def test_function_return(run) -> None:
    r = run("f() { return 7; }; f; echo $?")
    assert r.stdout == "7\n"


def test_brace_expansion(run) -> None:
    r = run("echo {a,b,c}")
    assert r.stdout == "a b c\n"


def test_brace_range_numeric(run) -> None:
    r = run("echo {1..5}")
    assert r.stdout == "1 2 3 4 5\n"


def test_brace_range_alpha(run) -> None:
    r = run("echo {a..d}")
    assert r.stdout == "a b c d\n"


def test_and_short_circuit(run) -> None:
    r = run("false && echo nope; echo done")
    assert r.stdout == "done\n"


def test_or_short_circuit(run) -> None:
    r = run("true || echo nope; echo done")
    assert r.stdout == "done\n"


def test_negation_pipeline(run) -> None:
    r = run("! false")
    assert r.exit_code == 0
    r = run("! true")
    assert r.exit_code == 1


def test_subshell_isolates_cd(run, fs) -> None:
    fs.mkdir("/sub", parents=True, exist_ok=True)
    r = run("( cd /sub; pwd ); pwd")
    assert r.stdout == "/sub\n/home/user/project\n"


def test_redirect_stdout(run, fs) -> None:
    fs.mkdir("/tmp", parents=True, exist_ok=True)
    r = run("echo hello > /tmp/out")
    assert r.exit_code == 0
    assert fs.read_text("/tmp/out") == "hello\n"


def test_redirect_append(run, fs) -> None:
    fs.mkdir("/tmp", parents=True, exist_ok=True)
    fs.write_file("/tmp/out", "first\n")
    r = run("echo second >> /tmp/out")
    assert r.exit_code == 0
    assert fs.read_text("/tmp/out") == "first\nsecond\n"


def test_redirect_input(run, fs) -> None:
    fs.mkdir("/tmp", parents=True, exist_ok=True)
    fs.write_file("/tmp/in", "hi there\n")
    r = run("cat < /tmp/in")
    assert r.stdout == "hi there\n"


def test_test_brackets(run) -> None:
    r = run('[ -n "x" ] && echo nonempty')
    assert r.stdout == "nonempty\n"
    r = run('[ -z "" ] && echo empty')
    assert r.stdout == "empty\n"


def test_double_bracket_string_match(run) -> None:
    r = run("[[ hello == h*o ]] && echo match")
    assert r.stdout == "match\n"


def test_double_bracket_regex(run) -> None:
    r = run('[[ "hello123" =~ ^[a-z]+[0-9]+$ ]] && echo regex')
    assert r.stdout == "regex\n"


def test_exit_propagates(run) -> None:
    r = run("exit 42")
    assert r.exit_code == 42


def test_break_in_for(run) -> None:
    r = run("for i in 1 2 3 4 5; do if (( i > 2 )); then break; fi; echo $i; done")
    assert r.stdout == "1\n2\n"


def test_continue_in_for(run) -> None:
    r = run("for i in 1 2 3; do (( i == 2 )) && continue; echo $i; done")
    assert r.stdout == "1\n3\n"


def test_pipe_status(run) -> None:
    r = run("false | true; echo $?")
    assert r.stdout == "0\n"


def test_command_not_found(run) -> None:
    r = run("nosuchcommand")
    assert r.exit_code == 127


@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("echo $((1 << 4))", "16\n"),
        ("echo $((10 % 3))", "1\n"),
        ("echo $((2 ** 8))", "256\n"),
        ("x=5; echo $((x * 2))", "10\n"),
        ("echo $(( 1 ? 100 : 200 ))", "100\n"),
    ],
)
def test_arithmetic_examples(run, script: str, expected: str) -> None:
    r = run(script)
    assert r.stdout == expected


def test_quoted_empty_field_preserved(run) -> None:
    r = run('echo "$undefined" | wc -c')
    # Empty word followed by newline = 1 byte
    assert r.stdout.strip() == "1"
