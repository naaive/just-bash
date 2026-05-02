"""Lexer behavior."""

from __future__ import annotations

import pytest

from just_bash.parser.lexer import Lexer, TokenKind, tokenize


def kinds(text: str) -> list[tuple[str, str]]:
    return [(t.kind.name, t.text) for t in tokenize(text) if t.kind is not TokenKind.EOF]


def test_simple_command() -> None:
    assert kinds("echo hello") == [("WORD", "echo"), ("WORD", "hello")]


def test_pipeline_operator() -> None:
    assert kinds("a | b") == [("WORD", "a"), ("OPERATOR", "|"), ("WORD", "b")]


def test_and_or() -> None:
    assert kinds("a && b || c") == [
        ("WORD", "a"),
        ("OPERATOR", "&&"),
        ("WORD", "b"),
        ("OPERATOR", "||"),
        ("WORD", "c"),
    ]


def test_redirections() -> None:
    assert kinds("echo hi >file") == [
        ("WORD", "echo"),
        ("WORD", "hi"),
        ("OPERATOR", ">"),
        ("WORD", "file"),
    ]
    assert kinds("cat <input >>output") == [
        ("WORD", "cat"),
        ("OPERATOR", "<"),
        ("WORD", "input"),
        ("OPERATOR", ">>"),
        ("WORD", "output"),
    ]


def test_io_number() -> None:
    out = kinds("echo hi 2>err")
    assert ("IO_NUMBER", "2") in out
    assert ("OPERATOR", ">") in out
    assert ("WORD", "err") in out


def test_quotes_preserve_text() -> None:
    out = kinds("echo 'hello world' \"x $y\"")
    assert out == [
        ("WORD", "echo"),
        ("WORD", "'hello world'"),
        ("WORD", '"x $y"'),
    ]


def test_command_substitution_in_word() -> None:
    out = kinds("echo $(echo nested)")
    assert out == [("WORD", "echo"), ("WORD", "$(echo nested)")]


def test_arithmetic_in_word() -> None:
    out = kinds("echo $((1+2))")
    assert out == [("WORD", "echo"), ("WORD", "$((1+2))")]


def test_braced_param() -> None:
    out = kinds("echo ${VAR:-default}")
    assert out == [("WORD", "echo"), ("WORD", "${VAR:-default}")]


def test_newline_terminator() -> None:
    out = [(t.kind.name, t.text) for t in tokenize("a\nb")]
    assert out == [
        ("WORD", "a"),
        ("NEWLINE", "\n"),
        ("WORD", "b"),
        ("EOF", ""),
    ]


def test_comment_stripped() -> None:
    out = kinds("echo hi # comment")
    assert out == [("WORD", "echo"), ("WORD", "hi")]


def test_line_continuation() -> None:
    out = kinds("echo \\\n  hi")
    assert out == [("WORD", "echo"), ("WORD", "hi")]


def test_unterminated_quote_error() -> None:
    from just_bash.parser.lexer import LexError

    lex = Lexer("echo 'oops")
    lex.next_token()  # echo
    with pytest.raises(LexError):
        lex.next_token()
