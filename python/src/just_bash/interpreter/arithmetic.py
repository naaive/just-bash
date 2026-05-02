"""Evaluate arithmetic expressions.

Bash arithmetic always works in integers. We use Python ``int`` (arbitrary
precision); ``CLAUDE.md`` notes "we explicitly don't support 64-bit integers"
which I read as "no need to wrap; integer overflow semantics aren't reproduced
exactly". For the MVP this is fine.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.ast.nodes import (
    ArithAssignment,
    ArithBinary,
    ArithExpr,
    ArithGroup,
    Arithmetic,
    ArithNumber,
    ArithTernary,
    ArithUnary,
    ArithVariable,
)
from just_bash.interpreter.errors import InterpreterError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import Interpreter


def eval_arith(interp: Interpreter, expr: Arithmetic | ArithExpr | None) -> int:
    if expr is None:
        return 0
    if isinstance(expr, Arithmetic):
        if expr.expression is None:
            return 0
        # If the source text contained ``$(...)`` or ``${...}`` shell
        # expansions, the original parse couldn't fully resolve them. Re-run
        # the word-expansion machinery on ``source_text`` so command
        # substitutions / parameter expansions are resolved, then re-parse the
        # arithmetic expression on the resulting numeric text.
        src = expr.source_text or ""
        if "$" in src or "`" in src:
            from just_bash.interpreter.expansion import expand_word_no_split
            from just_bash.parser.arithmetic_parser import parse_arith_text
            from just_bash.parser.word_parser import parse_word

            try:
                resolved = expand_word_no_split(interp, parse_word(src))
                reparsed = parse_arith_text(resolved)
                return _eval(interp, reparsed.expression) if reparsed.expression else 0
            except Exception:
                # Fall through to the originally parsed AST.
                pass
        return _eval(interp, expr.expression)
    return _eval(interp, expr)


def _eval(interp: Interpreter, node: ArithExpr) -> int:
    if isinstance(node, ArithNumber):
        return node.value
    if isinstance(node, ArithVariable):
        return _read_var(interp, node.name)
    if isinstance(node, ArithGroup):
        return _eval(interp, node.expression)
    if isinstance(node, ArithUnary):
        return _eval_unary(interp, node)
    if isinstance(node, ArithBinary):
        return _eval_binary(interp, node)
    if isinstance(node, ArithTernary):
        return (
            _eval(interp, node.consequent)
            if _eval(interp, node.condition) != 0
            else _eval(interp, node.alternate)
        )
    if isinstance(node, ArithAssignment):
        return _eval_assignment(interp, node)
    raise InterpreterError(f"unsupported arithmetic node: {type(node).__name__}")


def _read_var(interp: Interpreter, name: str) -> int:
    if not name:
        return 0
    if name.isdigit():
        idx = int(name) - 1
        if 0 <= idx < len(interp.env.positional):
            return _coerce_int(interp.env.positional[idx])
        return 0
    val = interp.env.get(name)
    if val is None or val == "":
        return 0
    return _coerce_int(val)


def _coerce_int(value: str) -> int:
    s = value.strip()
    if not s:
        return 0
    try:
        if s.startswith(("0x", "0X")):
            return int(s, 16)
        if len(s) > 1 and s.startswith("0") and s[1:].isdigit():
            return int(s, 8)
        return int(s)
    except ValueError:
        # Recursively expand variable references stored as strings.
        # In practice for the MVP this just returns 0.
        return 0


def _eval_unary(interp: Interpreter, node: ArithUnary) -> int:
    if node.operator in ("++", "--"):
        if not isinstance(node.operand, ArithVariable):
            raise InterpreterError("operand of ++/-- must be a variable")
        name = node.operand.name
        old = _read_var(interp, name)
        new = old + 1 if node.operator == "++" else old - 1
        interp.env.set_var(name, str(new))
        return new if node.prefix else old
    operand = _eval(interp, node.operand)
    if node.operator == "+":
        return operand
    if node.operator == "-":
        return -operand
    if node.operator == "!":
        return 0 if operand != 0 else 1
    if node.operator == "~":
        return ~operand
    raise InterpreterError(f"unsupported unary op: {node.operator}")


def _eval_binary(interp: Interpreter, node: ArithBinary) -> int:
    # Short-circuit ops.
    if node.operator == "&&":
        left = _eval(interp, node.left)
        if left == 0:
            return 0
        return 1 if _eval(interp, node.right) != 0 else 0
    if node.operator == "||":
        left = _eval(interp, node.left)
        if left != 0:
            return 1
        return 1 if _eval(interp, node.right) != 0 else 0
    left = _eval(interp, node.left)
    right = _eval(interp, node.right)
    op = node.operator
    if op == "+":
        return left + right
    if op == "-":
        return left - right
    if op == "*":
        return left * right
    if op == "/":
        if right == 0:
            raise InterpreterError("division by zero")
        # Bash uses C-style truncated division.
        q = abs(left) // abs(right)
        return q if (left >= 0) == (right >= 0) else -q
    if op == "%":
        if right == 0:
            raise InterpreterError("division by zero")
        sign = -1 if left < 0 else 1
        return sign * (abs(left) % abs(right))
    if op == "**":
        if right < 0:
            raise InterpreterError("negative exponent")
        return left**right
    if op == "<<":
        return left << right
    if op == ">>":
        return left >> right
    if op == "<":
        return 1 if left < right else 0
    if op == "<=":
        return 1 if left <= right else 0
    if op == ">":
        return 1 if left > right else 0
    if op == ">=":
        return 1 if left >= right else 0
    if op == "==":
        return 1 if left == right else 0
    if op == "!=":
        return 1 if left != right else 0
    if op == "&":
        return left & right
    if op == "|":
        return left | right
    if op == "^":
        return left ^ right
    if op == ",":
        return right
    raise InterpreterError(f"unsupported binary op: {op}")


def _eval_assignment(interp: Interpreter, node: ArithAssignment) -> int:
    rhs = _eval(interp, node.value)
    if node.operator == "=":
        new = rhs
    else:
        old = _read_var(interp, node.variable)
        binop = node.operator[:-1]
        new = _eval(
            interp,
            ArithBinary(operator=binop, left=ArithNumber(old), right=ArithNumber(rhs)),
        )
    interp.env.set_var(node.variable, str(new))
    return new


__all__ = ["eval_arith"]
