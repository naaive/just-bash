"""Arithmetic expression parser."""

from __future__ import annotations

from just_bash.ast.nodes import (
    ArithAssignment,
    ArithBinary,
    ArithNumber,
    ArithTernary,
    ArithUnary,
    ArithVariable,
)
from just_bash.parser.arithmetic_parser import parse_arith_text


def test_number() -> None:
    expr = parse_arith_text("42").expression
    assert isinstance(expr, ArithNumber)
    assert expr.value == 42


def test_hex_number() -> None:
    expr = parse_arith_text("0x10").expression
    assert isinstance(expr, ArithNumber)
    assert expr.value == 16


def test_octal_number() -> None:
    expr = parse_arith_text("010").expression
    assert isinstance(expr, ArithNumber)
    assert expr.value == 8


def test_base_notation() -> None:
    expr = parse_arith_text("2#1010").expression
    assert isinstance(expr, ArithNumber)
    assert expr.value == 10


def test_binary_precedence() -> None:
    expr = parse_arith_text("1 + 2 * 3").expression
    # Should parse as 1 + (2 * 3)
    assert isinstance(expr, ArithBinary)
    assert expr.operator == "+"
    assert isinstance(expr.right, ArithBinary)
    assert expr.right.operator == "*"


def test_unary_minus() -> None:
    expr = parse_arith_text("-5").expression
    assert isinstance(expr, ArithUnary)
    assert expr.operator == "-"


def test_post_increment() -> None:
    expr = parse_arith_text("x++").expression
    assert isinstance(expr, ArithUnary)
    assert expr.operator == "++"
    assert expr.prefix is False


def test_assignment() -> None:
    expr = parse_arith_text("x = 5").expression
    assert isinstance(expr, ArithAssignment)
    assert expr.variable == "x"


def test_compound_assignment() -> None:
    expr = parse_arith_text("x += 3").expression
    assert isinstance(expr, ArithAssignment)
    assert expr.operator == "+="


def test_ternary() -> None:
    expr = parse_arith_text("x > 0 ? 1 : -1").expression
    assert isinstance(expr, ArithTernary)


def test_variable_with_dollar() -> None:
    expr = parse_arith_text("$x + 1").expression
    assert isinstance(expr, ArithBinary)
    assert isinstance(expr.left, ArithVariable)


def test_exponent_right_associative() -> None:
    # 2 ** 3 ** 2 should be 2 ** (3 ** 2) = 512
    expr = parse_arith_text("2 ** 3 ** 2").expression
    assert isinstance(expr, ArithBinary)
    assert expr.operator == "**"
    assert isinstance(expr.right, ArithBinary)
    assert expr.right.operator == "**"
