"""Evaluate ``[[ ... ]]`` conditional expressions and the ``test`` / ``[`` builtin."""

from __future__ import annotations

import fnmatch
import re
from typing import TYPE_CHECKING

from just_bash.ast.nodes import (
    CondAnd,
    CondBinary,
    Conditional,
    CondNot,
    CondOr,
    CondUnary,
    Word,
)
from just_bash.interpreter.errors import InterpreterError
from just_bash.interpreter.expansion import expand_pattern, expand_word_no_split

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import Interpreter


def eval_conditional(interp: Interpreter, expr: Conditional) -> bool:
    if isinstance(expr, CondNot):
        return not eval_conditional(interp, expr.operand)
    if isinstance(expr, CondAnd):
        return eval_conditional(interp, expr.left) and eval_conditional(interp, expr.right)
    if isinstance(expr, CondOr):
        return eval_conditional(interp, expr.left) or eval_conditional(interp, expr.right)
    if isinstance(expr, CondUnary):
        return _eval_unary(interp, expr.operator, expr.operand)
    if isinstance(expr, CondBinary):
        return _eval_binary(interp, expr.operator, expr.left, expr.right)
    raise InterpreterError(f"unsupported conditional: {type(expr).__name__}")


def _eval_unary(interp: Interpreter, op: str, operand: Word) -> bool:
    s = expand_word_no_split(interp, operand)
    if op == "-z":
        return s == ""
    if op == "-n":
        return s != ""
    if op == "-e":
        return interp.fs.exists(s)
    if op == "-f":
        return interp.fs.is_file(s)
    if op == "-d":
        return interp.fs.is_dir(s)
    if op == "-r" or op == "-w" or op == "-x":
        # Permissions aren't enforced in the VFS; report based on existence.
        return interp.fs.exists(s)
    if op == "-s":
        try:
            node = interp.fs.stat(s)
        except OSError:
            return False
        return getattr(node, "size", 0) > 0
    if op == "-v":
        return interp.env.has(s)
    raise InterpreterError(f"unsupported test operator: {op}")


_POSIX_REGEX_CLASSES = {
    "alpha": "a-zA-Z",
    "alnum": "a-zA-Z0-9",
    "digit": "0-9",
    "lower": "a-z",
    "upper": "A-Z",
    "space": r" \t\n\r\f\v",
    "blank": r" \t",
    "xdigit": "0-9a-fA-F",
    "cntrl": r"\x00-\x1f\x7f",
    "print": r"\x20-\x7e",
    "graph": r"\x21-\x7e",
    "punct": r"!-/:-@\[-`{-~",
    "ascii": r"\x00-\x7f",
    "word": r"a-zA-Z0-9_",
}


def _translate_posix_classes(regex: str) -> str:
    """Replace POSIX bracket-classes ``[:NAME:]`` with Python equivalents."""
    if "[:" not in regex:
        return regex
    out: list[str] = []
    i = 0
    while i < len(regex):
        if regex.startswith("[:", i):
            end = regex.find(":]", i + 2)
            if end != -1:
                name = regex[i + 2 : end]
                replacement = _POSIX_REGEX_CLASSES.get(name)
                if replacement is not None:
                    out.append(replacement)
                    i = end + 2
                    continue
        out.append(regex[i])
        i += 1
    return "".join(out)


def _expand_regex_rhs(interp: Interpreter, word: Word) -> str:
    """Expand a Word for use as a regex RHS.

    Acts like ``expand_word_no_split`` but turns ``Escaped(value=c)`` parts
    into ``\\c`` so the regex engine sees the backslash bash promised.
    """
    from just_bash.ast.nodes import Escaped
    from just_bash.interpreter.expansion import _expand_to_pieces

    out: list[str] = []
    for part in word.parts:
        if isinstance(part, Escaped):
            out.append("\\" + part.value)
            continue
        # Re-use the standard expander for everything else (literals,
        # quoted strings, parameter expansion, command substitution, ...).
        sub = type(word)(line=word.line, parts=[part])
        pieces = _expand_to_pieces(interp, sub, force_quoted=True)
        out.append("".join(p.text for p in pieces))
    return "".join(out)


def _eval_binary(interp: Interpreter, op: str, left: Word, right: Word) -> bool:
    lv = expand_word_no_split(interp, left)
    if op == "=~":
        # Right side is a regex: bash keeps backslashes literal so the regex
        # engine sees ``\*`` etc. unmodified. Expand parameter references but
        # restore the backslash that the word parser stripped from ``\X``.
        rv = _expand_regex_rhs(interp, right)
        rv = _translate_posix_classes(rv)
        try:
            m = re.search(rv, lv)
        except re.error as e:
            raise InterpreterError(f"invalid regex: {e}") from e
        if m is None:
            interp.env.set_array("BASH_REMATCH", [])
            return False
        # ``BASH_REMATCH[0]`` is the full match; subsequent indices are
        # the captured groups (None -> empty string).
        groups: list[str] = [m.group(0)]
        for g in m.groups():
            groups.append(g if g is not None else "")
        interp.env.set_array("BASH_REMATCH", groups)
        return True
    if op in ("=", "==", "!="):
        # Right is a glob pattern (only when it has glob meta + isn't fully quoted).
        # Bash always treats RHS as a pattern unless quoted; the parser already
        # distinguishes literal/escaped via the Word AST so ``expand_pattern``
        # gets it right.
        pattern = expand_pattern(interp, right)
        if "[:" in pattern or (any(c in pattern for c in "?*+@!") and "(" in pattern):
            from just_bash.interpreter.extglob import extglob_match

            matched = extglob_match(lv, pattern)
        else:
            matched = fnmatch.fnmatchcase(lv, pattern)
        return matched if op != "!=" else not matched
    rv = expand_word_no_split(interp, right)
    if op == "<":
        return lv < rv
    if op == ">":
        return lv > rv
    if op in {"-eq", "-ne", "-lt", "-le", "-gt", "-ge"}:
        ln = _to_int(lv)
        rn = _to_int(rv)
        return {
            "-eq": ln == rn,
            "-ne": ln != rn,
            "-lt": ln < rn,
            "-le": ln <= rn,
            "-gt": ln > rn,
            "-ge": ln >= rn,
        }[op]
    raise InterpreterError(f"unsupported binary test operator: {op}")


def _to_int(s: str) -> int:
    s = s.strip()
    if not s:
        return 0
    try:
        return int(s)
    except ValueError as e:
        raise InterpreterError(f"integer expected: {s!r}") from e


# ---------------------------------------------------------------------------
# ``test`` / ``[`` builtin: parses the expression form on its own.
# ---------------------------------------------------------------------------


def eval_test_args(interp: Interpreter, args: list[str]) -> bool:
    """Evaluate ``test ARG...`` / ``[ ARG... ]``.

    Implements POSIX ``test`` precedence: unary > binary > ! > -a > -o.
    """
    p = _TestParser(interp, args)
    result = p.parse_expr()
    if p.pos != len(p.args):
        raise InterpreterError(f"test: too many arguments at {p.args[p.pos]!r}")
    return result


class _TestParser:
    __slots__ = ("args", "interp", "pos")

    def __init__(self, interp: Interpreter, args: list[str]) -> None:
        self.interp = interp
        self.args = args
        self.pos = 0

    def parse_expr(self) -> bool:
        return self._parse_or()

    def _parse_or(self) -> bool:
        left = self._parse_and()
        while self._peek() == "-o":
            self.pos += 1
            right = self._parse_and()
            left = left or right
        return left

    def _parse_and(self) -> bool:
        left = self._parse_not()
        while self._peek() == "-a":
            self.pos += 1
            right = self._parse_not()
            left = left and right
        return left

    def _parse_not(self) -> bool:
        if self._peek() == "!":
            self.pos += 1
            return not self._parse_not()
        return self._parse_primary()

    def _parse_primary(self) -> bool:
        if self._peek() == "(":
            self.pos += 1
            inner = self._parse_or()
            if self._peek() != ")":
                raise InterpreterError("test: expected ')'")
            self.pos += 1
            return inner
        if self.pos >= len(self.args):
            raise InterpreterError("test: missing operand")
        arg = self.args[self.pos]
        # Three-arg forms: A op B
        if self.pos + 2 < len(self.args) and self.args[self.pos + 1] in _TEST_BINARY:
            a, op, b = self.args[self.pos : self.pos + 3]
            self.pos += 3
            return _apply_binary(self.interp, op, a, b)
        # Two-arg forms: -OP A
        if arg in _TEST_UNARY and self.pos + 1 < len(self.args):
            self.pos += 2
            return _apply_unary(self.interp, arg, self.args[self.pos - 1])
        # Single-arg: non-empty?
        self.pos += 1
        return arg != ""

    def _peek(self) -> str | None:
        if self.pos >= len(self.args):
            return None
        return self.args[self.pos]


_TEST_BINARY = frozenset({"=", "==", "!=", "<", ">", "-eq", "-ne", "-lt", "-le", "-gt", "-ge"})
_TEST_UNARY = frozenset({"-z", "-n", "-e", "-f", "-d", "-r", "-w", "-x", "-s", "-v"})


def _apply_unary(interp: Interpreter, op: str, value: str) -> bool:
    if op == "-z":
        return value == ""
    if op == "-n":
        return value != ""
    if op == "-e":
        return interp.fs.exists(value)
    if op == "-f":
        return interp.fs.is_file(value)
    if op == "-d":
        return interp.fs.is_dir(value)
    if op in ("-r", "-w", "-x"):
        return interp.fs.exists(value)
    if op == "-s":
        try:
            node = interp.fs.stat(value)
        except OSError:
            return False
        return getattr(node, "size", 0) > 0
    if op == "-v":
        return interp.env.has(value)
    raise InterpreterError(f"test: unknown unary op {op!r}")


def _apply_binary(interp: Interpreter, op: str, a: str, b: str) -> bool:
    del interp
    if op in ("=", "=="):
        return a == b
    if op == "!=":
        return a != b
    if op == "<":
        return a < b
    if op == ">":
        return a > b
    if op in {"-eq", "-ne", "-lt", "-le", "-gt", "-ge"}:
        ln = _to_int(a)
        rn = _to_int(b)
        return {
            "-eq": ln == rn,
            "-ne": ln != rn,
            "-lt": ln < rn,
            "-le": ln <= rn,
            "-gt": ln > rn,
            "-ge": ln >= rn,
        }[op]
    raise InterpreterError(f"test: unknown binary op {op!r}")


__all__ = ["eval_conditional", "eval_test_args"]
