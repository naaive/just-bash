"""Parameter case-modification and ``@`` transforms."""

from __future__ import annotations


def test_uppercase_all(run) -> None:
    r = run('s=hello; echo "${s^^}"')
    assert r.stdout == "HELLO\n"


def test_uppercase_first(run) -> None:
    r = run('s=hello; echo "${s^}"')
    assert r.stdout == "Hello\n"


def test_lowercase_all(run) -> None:
    r = run('s=HELLO; echo "${s,,}"')
    assert r.stdout == "hello\n"


def test_lowercase_first(run) -> None:
    r = run('s=HELLO; echo "${s,}"')
    assert r.stdout == "hELLO\n"


def test_uppercase_pattern(run) -> None:
    # Only characters matching the (single-char) pattern get folded.
    r = run('s=hello; echo "${s^^[hl]}"')
    assert r.stdout == "HeLLo\n"


def test_transform_Q(run) -> None:
    r = run('s="hi there"; echo "${s@Q}"')
    assert r.stdout.strip() == "'hi there'"


def test_transform_U(run) -> None:
    r = run('s=hello; echo "${s@U}"')
    assert r.stdout == "HELLO\n"


def test_transform_L(run) -> None:
    r = run('s=HELLO; echo "${s@L}"')
    assert r.stdout == "hello\n"


def test_transform_u(run) -> None:
    r = run('s=hello; echo "${s@u}"')
    assert r.stdout == "Hello\n"


def test_transform_E_processes_escapes(run) -> None:
    r = run("""s='hi\\nthere'; echo "${s@E}" """)
    # The ``$'...'`` interpretation kicks in: ``\n`` becomes a real newline.
    assert "hi\nthere" in r.stdout


def test_uppercase_unset(run) -> None:
    # An unset var folds to the empty string.
    r = run('echo "${unset^^}"')
    assert r.stdout == "\n"
