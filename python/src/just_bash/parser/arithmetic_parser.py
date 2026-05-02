"""Recursive-descent parser for bash arithmetic ``$(( ... ))`` expressions.

Operator precedence (low to high) follows POSIX / bash:
  - assignment: ``=`` ``+=`` ``-=`` ``*=`` ``/=`` ``%=`` ``<<=`` ``>>=`` ``&=`` ``|=`` ``^=``
  - ternary:    ``? :``
  - logical or: ``||``
  - logical and:``&&``
  - bitwise or: ``|``
  - bitwise xor:``^``
  - bitwise and:``&``
  - equality:   ``==`` ``!=``
  - relational: ``<`` ``<=`` ``>`` ``>=``
  - shift:      ``<<`` ``>>``
  - additive:   ``+`` ``-``
  - multiplicative: ``*`` ``/`` ``%``
  - exponent:   ``**`` (right-associative)
  - unary:      ``-`` ``+`` ``!`` ``~`` ``++`` ``--``
  - postfix:    ``++`` ``--``
  - primary:    number | variable | ``(`` expr ``)``
"""

from __future__ import annotations

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


class ArithParseError(Exception):
    pass


_ASSIGN_OPS = ("<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "=")


def parse_arith_text(text: str) -> Arithmetic:
    p = _Parser(text)
    expr = p.parse_expression()
    p.expect_eof()
    return Arithmetic(expression=expr, source_text=text)


class _Parser:
    __slots__ = ("pos", "text")

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    # --------------------------------------------------------------- utilities
    def _eof(self) -> bool:
        return self.pos >= len(self.text)

    def _skip(self) -> None:
        while not self._eof() and self.text[self.pos].isspace():
            self.pos += 1

    def _peek(self, n: int = 1) -> str:
        self._skip()
        return self.text[self.pos : self.pos + n]

    def _match(self, *ops: str) -> str | None:
        self._skip()
        for op in ops:
            if self.text.startswith(op, self.pos):
                self.pos += len(op)
                return op
        return None

    def expect_eof(self) -> None:
        self._skip()
        if not self._eof():
            raise ArithParseError(f"unexpected token in arithmetic: {self.text[self.pos :]!r}")

    # ------------------------------------------------------------- expressions
    def parse_expression(self) -> ArithExpr:
        return self._parse_assignment()

    def _parse_assignment(self) -> ArithExpr:
        # Look ahead for ``IDENT op``. We snapshot ``pos`` to roll back.
        save = self.pos
        self._skip()
        if not self._eof() and (self.text[self.pos].isalpha() or self.text[self.pos] == "_"):
            j = self.pos
            while j < len(self.text) and (self.text[j].isalnum() or self.text[j] == "_"):
                j += 1
            name = self.text[self.pos : j]
            old_pos = self.pos
            self.pos = j
            self._skip()
            for op in _ASSIGN_OPS:
                if self.text.startswith(op, self.pos):
                    # ``=`` shouldn't swallow the first ``=`` of ``==``.
                    if op == "=" and self.text.startswith("==", self.pos):
                        continue
                    self.pos += len(op)
                    value = self._parse_assignment()
                    return ArithAssignment(operator=op, variable=name, value=value)
            self.pos = old_pos  # not an assignment; fall through
        self.pos = save
        return self._parse_ternary()

    def _parse_ternary(self) -> ArithExpr:
        cond = self._parse_logical_or()
        if self._match("?"):
            then_ = self._parse_assignment()
            if not self._match(":"):
                raise ArithParseError("expected ':' in ternary")
            else_ = self._parse_assignment()
            return ArithTernary(condition=cond, consequent=then_, alternate=else_)
        return cond

    def _parse_logical_or(self) -> ArithExpr:
        left = self._parse_logical_and()
        while self._match("||"):
            right = self._parse_logical_and()
            left = ArithBinary(operator="||", left=left, right=right)
        return left

    def _parse_logical_and(self) -> ArithExpr:
        left = self._parse_bitor()
        while self._match("&&"):
            right = self._parse_bitor()
            left = ArithBinary(operator="&&", left=left, right=right)
        return left

    def _parse_bitor(self) -> ArithExpr:
        left = self._parse_bitxor()
        while True:
            self._skip()
            # disambiguate from ||
            if self.text.startswith("|", self.pos) and not self.text.startswith("||", self.pos):
                self.pos += 1
                right = self._parse_bitxor()
                left = ArithBinary(operator="|", left=left, right=right)
                continue
            return left

    def _parse_bitxor(self) -> ArithExpr:
        left = self._parse_bitand()
        while self._match("^"):
            right = self._parse_bitand()
            left = ArithBinary(operator="^", left=left, right=right)
        return left

    def _parse_bitand(self) -> ArithExpr:
        left = self._parse_equality()
        while True:
            self._skip()
            if self.text.startswith("&", self.pos) and not self.text.startswith("&&", self.pos):
                self.pos += 1
                right = self._parse_equality()
                left = ArithBinary(operator="&", left=left, right=right)
                continue
            return left

    def _parse_equality(self) -> ArithExpr:
        left = self._parse_relational()
        while True:
            op = self._match("==", "!=")
            if op is None:
                return left
            right = self._parse_relational()
            left = ArithBinary(operator=op, left=left, right=right)

    def _parse_relational(self) -> ArithExpr:
        left = self._parse_shift()
        while True:
            op = self._match("<=", ">=", "<", ">")
            if op is None:
                return left
            right = self._parse_shift()
            left = ArithBinary(operator=op, left=left, right=right)

    def _parse_shift(self) -> ArithExpr:
        left = self._parse_additive()
        while True:
            op = self._match("<<", ">>")
            if op is None:
                return left
            right = self._parse_additive()
            left = ArithBinary(operator=op, left=left, right=right)

    def _parse_additive(self) -> ArithExpr:
        left = self._parse_multiplicative()
        while True:
            op = self._match("+", "-")
            if op is None:
                return left
            right = self._parse_multiplicative()
            left = ArithBinary(operator=op, left=left, right=right)

    def _parse_multiplicative(self) -> ArithExpr:
        left = self._parse_exponent()
        while True:
            op = self._match("*", "/", "%")
            if op is None:
                return left
            # Don't consume "**" as "*"
            if op == "*" and self._peek(1) == "*":
                # Already consumed one "*"; put it back? No, simpler: if next char is "*", undo.
                self.pos -= 1
                return left
            right = self._parse_exponent()
            left = ArithBinary(operator=op, left=left, right=right)

    def _parse_exponent(self) -> ArithExpr:
        left = self._parse_unary()
        if self._match("**"):
            right = self._parse_exponent()  # right-associative
            return ArithBinary(operator="**", left=left, right=right)
        return left

    def _parse_unary(self) -> ArithExpr:
        op = self._match("++", "--")
        if op is not None:
            operand = self._parse_unary()
            return ArithUnary(operator=op, operand=operand, prefix=True)
        op = self._match("+", "-", "!", "~")
        if op is not None:
            operand = self._parse_unary()
            return ArithUnary(operator=op, operand=operand, prefix=True)
        return self._parse_postfix()

    def _parse_postfix(self) -> ArithExpr:
        primary = self._parse_primary()
        op = self._match("++", "--")
        if op is not None:
            return ArithUnary(operator=op, operand=primary, prefix=False)
        return primary

    def _parse_primary(self) -> ArithExpr:
        self._skip()
        if self._eof():
            raise ArithParseError("unexpected end of arithmetic expression")
        ch = self.text[self.pos]
        if ch == "(":
            self.pos += 1
            inner = self._parse_assignment()
            if not self._match(")"):
                raise ArithParseError("expected ')'")
            return ArithGroup(expression=inner)
        if ch == "$":
            self.pos += 1
            return self._parse_dollar_var()
        if ch.isdigit():
            return self._parse_number()
        if ch.isalpha() or ch == "_":
            return self._parse_variable()
        raise ArithParseError(f"unexpected character {ch!r} in arithmetic")

    def _parse_dollar_var(self) -> ArithExpr:
        if self._eof():
            raise ArithParseError("expected name after $")
        # ${var}
        if self.text[self.pos] == "{":
            self.pos += 1
            j = self.pos
            while j < len(self.text) and self.text[j] != "}":
                j += 1
            if j >= len(self.text):
                raise ArithParseError("unterminated ${...}")
            name = self.text[self.pos : j]
            self.pos = j + 1
            return ArithVariable(name=name)
        return self._parse_variable()

    def _parse_number(self) -> ArithNumber:
        # Support 0x, 0X, 0..., decimal.
        j = self.pos
        if self.text.startswith(("0x", "0X"), j):
            j += 2
            while j < len(self.text) and self.text[j] in "0123456789abcdefABCDEF":
                j += 1
            value = int(self.text[self.pos : j], 16)
        elif self.text[j] == "0" and j + 1 < len(self.text) and self.text[j + 1].isdigit():
            j += 1
            while j < len(self.text) and self.text[j] in "01234567":
                j += 1
            value = int(self.text[self.pos : j], 8)
        else:
            while j < len(self.text) and self.text[j].isdigit():
                j += 1
            # base#value notation: e.g. 2#1010
            if j < len(self.text) and self.text[j] == "#":
                base = int(self.text[self.pos : j])
                j += 1
                start = j
                while j < len(self.text) and (
                    self.text[j].isalnum() or self.text[j] == "@" or self.text[j] == "_"
                ):
                    j += 1
                digits = self.text[start:j]
                value = _decode_base(base, digits)
            else:
                value = int(self.text[self.pos : j])
        self.pos = j
        return ArithNumber(value=value)

    def _parse_variable(self) -> ArithVariable:
        j = self.pos
        while j < len(self.text) and (self.text[j].isalnum() or self.text[j] == "_"):
            j += 1
        name = self.text[self.pos : j]
        self.pos = j
        return ArithVariable(name=name)


def _decode_base(base: int, digits: str) -> int:
    if not 2 <= base <= 64:
        raise ArithParseError(f"invalid arithmetic base: {base}")
    out = 0
    for d in digits:
        if d.isdigit():
            v = int(d)
        elif "a" <= d <= "z":
            v = ord(d) - ord("a") + 10
        elif "A" <= d <= "Z":
            v = ord(d) - ord("A") + 36
        elif d == "@":
            v = 62
        elif d == "_":
            v = 63
        else:
            raise ArithParseError(f"invalid digit {d!r} in base-{base} number")
        if v >= base:
            raise ArithParseError(f"digit {d!r} not valid in base {base}")
        out = out * base + v
    return out


__all__ = ["ArithParseError", "parse_arith_text"]
