"""Phase-14 language tests: nameref, pipefail, printf %q / %b / %f."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Nameref (declare -n / local -n)
# ---------------------------------------------------------------------------


def test_nameref_read_follows_target(run) -> None:
    r = run("""
target=hello
declare -n ref=target
echo "$ref"
""")
    assert r.stdout == "hello\n"


def test_nameref_write_updates_target(run) -> None:
    r = run("""
target=initial
declare -n ref=target
ref=updated
echo "$target"
""")
    assert r.stdout == "updated\n"


def test_nameref_local_in_function(run) -> None:
    r = run("""
target=outer
mutate() {
  local -n r=$1
  r=changed
}
mutate target
echo "$target"
""")
    assert r.stdout == "changed\n"


# ---------------------------------------------------------------------------
# set -o pipefail
# ---------------------------------------------------------------------------


def test_pipefail_first_stage_fails(run) -> None:
    r = run("""
set -o pipefail
false | true
echo $?
""")
    assert r.stdout == "1\n"


def test_pipefail_all_succeed(run) -> None:
    r = run("""
set -o pipefail
true | true
echo $?
""")
    assert r.stdout == "0\n"


def test_pipefail_off_uses_last_status(run) -> None:
    r = run("""
false | true
echo $?
""")
    assert r.stdout == "0\n"


def test_set_minus_o_invalid(run) -> None:
    r = run("set -o nosuch")
    assert r.exit_code == 2


# ---------------------------------------------------------------------------
# printf %q / %b / %f
# ---------------------------------------------------------------------------


def test_printf_q_safe_word(run) -> None:
    r = run("printf %q hello")
    assert r.stdout == "hello"


def test_printf_q_with_space(run) -> None:
    r = run("printf '%q' 'hello world'")
    assert r.stdout == "hello\\ world"


def test_printf_q_with_quote(run) -> None:
    r = run("""printf '%q' "don't" """)
    assert r.stdout == "don\\'t"


def test_printf_b_interprets_escapes(run) -> None:
    r = run(r"""printf '%b\n' 'a\tb'""")
    assert r.stdout == "a\tb\n"


def test_printf_f_float(run) -> None:
    r = run("printf '%.2f\\n' 3.14159")
    assert r.stdout == "3.14\n"


# ---------------------------------------------------------------------------
# set / shopt edge cases
# ---------------------------------------------------------------------------


def test_set_o_pipefail_then_plus_o(run) -> None:
    r = run("""
set -o pipefail
false | true
echo $?
set +o pipefail
false | true
echo $?
""")
    assert r.stdout == "1\n0\n"
