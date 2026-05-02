"""Process substitution tests."""

from __future__ import annotations


def test_input_process_sub(run) -> None:
    r = run("cat <(echo hello)")
    assert r.stdout == "hello\n"


def test_two_input_process_subs(run) -> None:
    r = run("paste <(printf 'a\\nb\\n') <(printf 'x\\ny\\n')")
    assert r.stdout == "a\tx\nb\ty\n"


def test_diff_via_process_subs(run) -> None:
    r = run("diff -q <(echo equal) <(echo equal)")
    assert r.exit_code == 0


def test_output_process_sub_via_tee(run) -> None:
    # ``tee >(cat)`` duplicates stdout: original goes to stdout, the captured
    # stream is fed to ``cat`` whose stdout also goes to the surrounding
    # pipeline, producing two copies.
    r = run("echo data | tee >(cat)")
    assert r.stdout.count("data") == 2


def test_input_process_sub_with_pipeline(run) -> None:
    r = run("grep alpha <(printf 'alpha\\nbeta\\n')")
    assert r.stdout == "alpha\n"
