"""Trap-handler tests."""

from __future__ import annotations


def test_exit_trap_runs_at_script_end(run) -> None:
    r = run("trap 'echo bye' EXIT; echo hello")
    assert r.stdout == "hello\nbye\n"


def test_exit_trap_runs_on_explicit_exit(run) -> None:
    r = run("trap 'echo cleanup' EXIT; exit 3")
    assert r.stdout == "cleanup\n"
    assert r.exit_code == 3


def test_err_trap_fires_on_failure(run) -> None:
    r = run("trap 'echo failed' ERR; false; echo done")
    assert r.stdout == "failed\ndone\n"


def test_err_trap_does_not_fire_on_success(run) -> None:
    r = run("trap 'echo failed' ERR; true; echo done")
    assert r.stdout == "done\n"


def test_set_e_aborts(run) -> None:
    r = run("set -e; echo a; false; echo never")
    assert r.stdout == "a\n"
    assert r.exit_code == 1


def test_set_e_with_or_does_not_abort(run) -> None:
    r = run("set -e; echo a; false || true; echo b")
    assert r.stdout == "a\nb\n"


def test_trap_clear_with_dash(run) -> None:
    r = run("trap 'echo bye' EXIT; trap - EXIT; echo hi")
    assert r.stdout == "hi\n"


def test_trap_with_multiple_signals(run) -> None:
    r = run("trap 'echo done' EXIT TERM; echo ok")
    assert r.stdout == "ok\ndone\n"


def test_trap_list(run) -> None:
    r = run("trap 'echo bye' EXIT; trap")
    assert "EXIT" in r.stdout
