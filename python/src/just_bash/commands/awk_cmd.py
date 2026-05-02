"""``awk`` - pattern-action language with a small but real interpreter.

Supports:
  - ``BEGIN { ... }`` / ``END { ... }`` blocks
  - ``/regex/`` and expression patterns; pattern, action, or both may be omitted
  - User-defined functions with multi-statement bodies and ``return``
  - ``if`` / ``else`` / ``while`` / ``for(init; cond; step)`` / ``for(var in arr)``
  - ``break`` / ``continue`` / ``next`` / ``exit``
  - Local arrays and associative arrays (``arr["k"] = v``, ``arr[1]++``)
  - Builtins: ``length``, ``substr``, ``index``, ``split``, ``sub``, ``gsub``,
    ``match``, ``toupper``, ``tolower``, ``sprintf``, ``printf`` (statement),
    ``int``, ``sqrt``, ``sin``, ``cos``, ``atan2``, ``exp``, ``log``, ``rand``,
    ``srand``, ``system``, ``getline``
  - ``$0``, ``$N`` field access; ``NR``, ``NF``, ``FS``, ``OFS``, ``ORS``,
    ``FNR``, ``FILENAME``, ``SUBSEP``
  - ``-F sep``, ``-v var=val``, ``-f file``
"""

from __future__ import annotations

import math
import random
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# Lexer
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Tok:
    kind: str
    value: str
    pos: int


_KEYWORDS = frozenset(
    {
        "BEGIN",
        "END",
        "function",
        "func",
        "if",
        "else",
        "while",
        "for",
        "do",
        "break",
        "continue",
        "next",
        "exit",
        "return",
        "in",
        "getline",
        "printf",
        "print",
        "delete",
    }
)


def _tokenize(source: str) -> list[Tok]:
    out: list[Tok] = []
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch in " \t":
            i += 1
            continue
        if ch == "\\" and i + 1 < n and source[i + 1] == "\n":
            i += 2
            continue
        if ch in "\n;":
            out.append(Tok("SEP", ch, i))
            i += 1
            continue
        if ch == "#":
            while i < n and source[i] != "\n":
                i += 1
            continue
        if ch == '"':
            j = i + 1
            buf = ['"']
            while j < n and source[j] != '"':
                if source[j] == "\\" and j + 1 < n:
                    buf.append(source[j])
                    buf.append(source[j + 1])
                    j += 2
                    continue
                buf.append(source[j])
                j += 1
            buf.append('"')
            out.append(Tok("STRING", "".join(buf), i))
            i = j + 1
            continue
        if ch == "/" and _is_regex_context(out):
            j = i + 1
            buf = ["/"]
            while j < n and source[j] != "/":
                if source[j] == "\\" and j + 1 < n:
                    buf.append(source[j])
                    buf.append(source[j + 1])
                    j += 2
                    continue
                buf.append(source[j])
                j += 1
            buf.append("/")
            out.append(Tok("REGEX", "".join(buf), i))
            i = j + 1
            continue
        if ch.isdigit() or (ch == "." and i + 1 < n and source[i + 1].isdigit()):
            j = i
            while j < n and (source[j].isdigit() or source[j] == "."):
                j += 1
            out.append(Tok("NUMBER", source[i:j], i))
            i = j
            continue
        if ch.isalpha() or ch == "_":
            j = i
            while j < n and (source[j].isalnum() or source[j] == "_"):
                j += 1
            ident = source[i:j]
            kind = "KEYWORD" if ident in _KEYWORDS else "IDENT"
            out.append(Tok(kind, ident, i))
            i = j
            continue
        # Multi-char operators.
        for op in (
            "==",
            "!=",
            "<=",
            ">=",
            "&&",
            "||",
            "++",
            "--",
            "+=",
            "-=",
            "*=",
            "/=",
            "%=",
            "^=",
            "**=",
            "**",
            "!~",
        ):
            if source.startswith(op, i):
                out.append(Tok("OP", op, i))
                i += len(op)
                break
        else:
            out.append(Tok("OP", ch, i))
            i += 1
    out.append(Tok("EOF", "", n))
    return out


def _is_regex_context(prev_tokens: list[Tok]) -> bool:
    """A bare ``/`` is a regex if the previous token can't start a division."""
    if not prev_tokens:
        return True
    t = prev_tokens[-1]
    if t.kind in ("NUMBER", "STRING", "IDENT", "REGEX"):
        return False
    return not (t.kind == "OP" and t.value in (")", "]", "++", "--"))


# ---------------------------------------------------------------------------
# AST
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Node:
    pass


@dataclass(slots=True)
class _Number(_Node):
    value: float


@dataclass(slots=True)
class _String(_Node):
    value: str


@dataclass(slots=True)
class _Regex(_Node):
    pattern: str


@dataclass(slots=True)
class _Ident(_Node):
    name: str


@dataclass(slots=True)
class _Field(_Node):
    expr: _Node


@dataclass(slots=True)
class _ArrayRef(_Node):
    name: str
    indices: list[_Node]


@dataclass(slots=True)
class _Call(_Node):
    name: str
    args: list[_Node]


@dataclass(slots=True)
class _Unary(_Node):
    op: str
    operand: _Node
    prefix: bool = True


@dataclass(slots=True)
class _Binary(_Node):
    op: str
    left: _Node
    right: _Node


@dataclass(slots=True)
class _Concat(_Node):
    left: _Node
    right: _Node


@dataclass(slots=True)
class _Match(_Node):
    op: str  # ``~`` or ``!~``
    left: _Node
    right: _Node


@dataclass(slots=True)
class _Ternary(_Node):
    cond: _Node
    then_: _Node
    else_: _Node


@dataclass(slots=True)
class _Assign(_Node):
    target: _Node
    op: str
    value: _Node


@dataclass(slots=True)
class _Getline(_Node):
    target: _Node | None = None


# Statements


@dataclass(slots=True)
class _ExprStmt(_Node):
    expr: _Node


@dataclass(slots=True)
class _Block(_Node):
    stmts: list[_Node]


@dataclass(slots=True)
class _If(_Node):
    cond: _Node
    then_: _Node
    else_: _Node | None = None


@dataclass(slots=True)
class _While(_Node):
    cond: _Node
    body: _Node


@dataclass(slots=True)
class _For(_Node):
    init: _Node | None
    cond: _Node | None
    step: _Node | None
    body: _Node


@dataclass(slots=True)
class _ForIn(_Node):
    var: str
    array: str
    body: _Node


@dataclass(slots=True)
class _Print(_Node):
    args: list[_Node]


@dataclass(slots=True)
class _Printf(_Node):
    args: list[_Node]


@dataclass(slots=True)
class _Delete(_Node):
    target: _ArrayRef


@dataclass(slots=True)
class _Break(_Node):
    pass


@dataclass(slots=True)
class _Continue(_Node):
    pass


@dataclass(slots=True)
class _Next(_Node):
    pass


@dataclass(slots=True)
class _Exit(_Node):
    code: _Node | None


@dataclass(slots=True)
class _Return(_Node):
    value: _Node | None


@dataclass(slots=True)
class _Function:
    name: str
    params: list[str]
    body: _Block


@dataclass(slots=True)
class _Rule:
    kind: str  # 'BEGIN' / 'END' / 'main'
    pattern: _Node | None
    action: _Block | None  # None -> default ``{ print }``


@dataclass(slots=True)
class _Program:
    rules: list[_Rule] = field(default_factory=list)
    functions: dict[str, _Function] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class _Parser:
    __slots__ = ("pos", "toks")

    def __init__(self, toks: list[Tok]) -> None:
        self.toks = toks
        self.pos = 0

    def _peek(self, off: int = 0) -> Tok:
        i = min(self.pos + off, len(self.toks) - 1)
        return self.toks[i]

    def _next(self) -> Tok:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _eat(self, kind: str, value: str | None = None) -> Tok | None:
        t = self._peek()
        if t.kind == kind and (value is None or t.value == value):
            return self._next()
        return None

    def _eat_op(self, *vals: str) -> Tok | None:
        t = self._peek()
        if t.kind == "OP" and t.value in vals:
            return self._next()
        return None

    def _expect_op(self, val: str) -> None:
        if not self._eat_op(val):
            t = self._peek()
            raise SyntaxError(f"awk: expected {val!r}, got {t.value!r} at {t.pos}")

    def _skip_seps(self) -> None:
        while self._eat("SEP"):
            pass

    def parse_program(self) -> _Program:
        prog = _Program()
        self._skip_seps()
        while self._peek().kind != "EOF":
            tok = self._peek()
            if tok.kind == "KEYWORD" and tok.value in ("function", "func"):
                fn = self._parse_function()
                prog.functions[fn.name] = fn
            else:
                prog.rules.append(self._parse_rule())
            self._skip_seps()
        return prog

    def _parse_function(self) -> _Function:
        self._next()  # consume ``function``
        name_tok = self._next()
        if name_tok.kind != "IDENT":
            raise SyntaxError(f"awk: expected function name, got {name_tok.value!r}")
        self._expect_op("(")
        params: list[str] = []
        if not self._eat_op(")"):
            while True:
                p = self._next()
                if p.kind != "IDENT":
                    raise SyntaxError("awk: expected parameter name")
                params.append(p.value)
                if self._eat_op(","):
                    continue
                self._expect_op(")")
                break
        self._skip_seps()
        body = self._parse_block()
        return _Function(name=name_tok.value, params=params, body=body)

    def _parse_rule(self) -> _Rule:
        tok = self._peek()
        kind = "main"
        pattern: _Node | None = None
        if tok.kind == "KEYWORD" and tok.value in ("BEGIN", "END"):
            kind = tok.value
            self._next()
        else:
            # Optional pattern.
            if not (tok.kind == "OP" and tok.value == "{"):
                pattern = self._parse_expression()
        # Optional action block.
        if self._peek().kind == "OP" and self._peek().value == "{":
            action = self._parse_block()
        else:
            action = None
        return _Rule(kind=kind, pattern=pattern, action=action)

    def _parse_block(self) -> _Block:
        self._expect_op("{")
        self._skip_seps()
        stmts: list[_Node] = []
        while not (self._peek().kind == "OP" and self._peek().value == "}"):
            if self._peek().kind == "EOF":
                raise SyntaxError("awk: unterminated block")
            stmts.append(self._parse_statement())
            self._skip_seps()
        self._expect_op("}")
        return _Block(stmts=stmts)

    def _parse_statement(self) -> _Node:
        tok = self._peek()
        if tok.kind == "OP" and tok.value == "{":
            return self._parse_block()
        if tok.kind == "KEYWORD":
            kw = tok.value
            if kw == "if":
                return self._parse_if()
            if kw == "while":
                return self._parse_while()
            if kw == "for":
                return self._parse_for()
            if kw == "break":
                self._next()
                return _Break()
            if kw == "continue":
                self._next()
                return _Continue()
            if kw == "next":
                self._next()
                return _Next()
            if kw == "exit":
                self._next()
                code = (
                    None
                    if self._peek().kind in ("SEP", "OP") and self._peek().value in (";", "\n", "}")
                    else self._parse_expression()
                )
                return _Exit(code=code)
            if kw == "return":
                self._next()
                if self._peek().kind == "SEP" or (
                    self._peek().kind == "OP" and self._peek().value == "}"
                ):
                    return _Return(value=None)
                return _Return(value=self._parse_expression())
            if kw == "print":
                return self._parse_print()
            if kw == "printf":
                return self._parse_printf()
            if kw == "delete":
                return self._parse_delete()
        # Expression statement.
        return _ExprStmt(expr=self._parse_expression())

    def _parse_if(self) -> _If:
        self._next()  # if
        self._expect_op("(")
        cond = self._parse_expression()
        self._expect_op(")")
        self._skip_seps()
        then_ = self._parse_statement()
        else_: _Node | None = None
        self._skip_seps()
        if self._peek().kind == "KEYWORD" and self._peek().value == "else":
            self._next()
            self._skip_seps()
            else_ = self._parse_statement()
        return _If(cond=cond, then_=then_, else_=else_)

    def _parse_while(self) -> _While:
        self._next()
        self._expect_op("(")
        cond = self._parse_expression()
        self._expect_op(")")
        self._skip_seps()
        body = self._parse_statement()
        return _While(cond=cond, body=body)

    def _parse_for(self) -> _Node:
        self._next()
        self._expect_op("(")
        # ``for (var in arr)`` form?
        save = self.pos
        if self._peek().kind == "IDENT":
            name = self._next().value
            if self._peek().kind == "KEYWORD" and self._peek().value == "in":
                self._next()
                arr = self._next()
                if arr.kind != "IDENT":
                    raise SyntaxError("awk: expected array name in for-in")
                self._expect_op(")")
                self._skip_seps()
                body = self._parse_statement()
                return _ForIn(var=name, array=arr.value, body=body)
            self.pos = save
        # C-style ``for(init; cond; step)``. The lexer emits ``;`` as a SEP
        # token, not OP, so use ``_eat_semi`` for the inner separators.
        init = None if self._is_semi() else self._parse_expression()
        self._eat_semi(required=True)
        cond = None if self._is_semi() else self._parse_expression()
        self._eat_semi(required=True)
        step = (
            None
            if self._peek().kind == "OP" and self._peek().value == ")"
            else self._parse_expression()
        )
        self._expect_op(")")
        self._skip_seps()
        body = self._parse_statement()
        return _For(init=init, cond=cond, step=step, body=body)

    def _is_semi(self) -> bool:
        t = self._peek()
        return (t.kind == "SEP" and t.value == ";") or (t.kind == "OP" and t.value == ";")

    def _eat_semi(self, *, required: bool = False) -> None:
        if self._is_semi():
            self._next()
            return
        if required:
            t = self._peek()
            raise SyntaxError(f"awk: expected ';', got {t.value!r}")

    def _parse_print(self) -> _Print:
        self._next()
        args: list[_Node] = []
        # Empty ``print`` -> print $0.
        if self._peek().kind in ("SEP", "EOF") or (
            self._peek().kind == "OP" and self._peek().value == "}"
        ):
            return _Print(args=args)
        args.append(self._parse_expression())
        while self._eat_op(","):
            args.append(self._parse_expression())
        return _Print(args=args)

    def _parse_printf(self) -> _Printf:
        self._next()
        args: list[_Node] = [self._parse_expression()]
        while self._eat_op(","):
            args.append(self._parse_expression())
        return _Printf(args=args)

    def _parse_delete(self) -> _Delete:
        self._next()
        if self._peek().kind != "IDENT":
            raise SyntaxError("awk: expected array name in delete")
        name = self._next().value
        indices: list[_Node] = []
        if self._eat_op("["):
            indices.append(self._parse_expression())
            while self._eat_op(","):
                indices.append(self._parse_expression())
            self._expect_op("]")
        return _Delete(target=_ArrayRef(name=name, indices=indices))

    # -------------------------------------------------------- expressions

    def _parse_expression(self) -> _Node:
        return self._parse_ternary()

    def _parse_ternary(self) -> _Node:
        node = self._parse_or()
        if self._eat_op("?"):
            then_ = self._parse_ternary()
            self._expect_op(":")
            else_ = self._parse_ternary()
            return _Ternary(cond=node, then_=then_, else_=else_)
        # Assignment is right-associative; check after ternary so ``a = b ? x : y``
        # binds the assignment outermost.
        return self._maybe_assign(node)

    def _maybe_assign(self, node: _Node) -> _Node:
        tok = self._peek()
        if tok.kind == "OP" and tok.value in ("=", "+=", "-=", "*=", "/=", "%=", "^=", "**="):
            self._next()
            rhs = self._parse_ternary()
            return _Assign(target=node, op=tok.value, value=rhs)
        return node

    def _parse_or(self) -> _Node:
        left = self._parse_and()
        while self._eat_op("||"):
            right = self._parse_and()
            left = _Binary(op="||", left=left, right=right)
        return left

    def _parse_and(self) -> _Node:
        left = self._parse_in()
        while self._eat_op("&&"):
            right = self._parse_in()
            left = _Binary(op="&&", left=left, right=right)
        return left

    def _parse_in(self) -> _Node:
        left = self._parse_match()
        while self._peek().kind == "KEYWORD" and self._peek().value == "in":
            self._next()
            right = self._parse_match()
            left = _Binary(op="in", left=left, right=right)
        return left

    def _parse_match(self) -> _Node:
        left = self._parse_relational()
        while True:
            t = self._peek()
            if t.kind == "OP" and t.value in ("~", "!~"):
                self._next()
                right = self._parse_relational()
                left = _Match(op=t.value, left=left, right=right)
                continue
            return left

    def _parse_relational(self) -> _Node:
        left = self._parse_concat()
        while True:
            t = self._peek()
            if t.kind == "OP" and t.value in ("==", "!=", "<", "<=", ">", ">="):
                self._next()
                right = self._parse_concat()
                left = _Binary(op=t.value, left=left, right=right)
                continue
            return left

    def _parse_concat(self) -> _Node:
        left = self._parse_additive()
        while True:
            tok = self._peek()
            # Implicit string concat when next thing can start a term.
            if tok.kind in ("STRING", "NUMBER", "IDENT") or (
                tok.kind == "OP" and tok.value in ("(", "$")
            ):
                right = self._parse_additive()
                left = _Concat(left=left, right=right)
                continue
            return left

    def _parse_additive(self) -> _Node:
        left = self._parse_multiplicative()
        while True:
            t = self._peek()
            if t.kind == "OP" and t.value in ("+", "-"):
                self._next()
                right = self._parse_multiplicative()
                left = _Binary(op=t.value, left=left, right=right)
                continue
            return left

    def _parse_multiplicative(self) -> _Node:
        left = self._parse_exponent()
        while True:
            t = self._peek()
            if t.kind == "OP" and t.value in ("*", "/", "%"):
                self._next()
                right = self._parse_exponent()
                left = _Binary(op=t.value, left=left, right=right)
                continue
            return left

    def _parse_exponent(self) -> _Node:
        left = self._parse_unary()
        if self._eat_op("**", "^"):
            right = self._parse_exponent()
            return _Binary(op="**", left=left, right=right)
        return left

    def _parse_unary(self) -> _Node:
        t = self._peek()
        if t.kind == "OP" and t.value in ("!", "-", "+"):
            self._next()
            operand = self._parse_unary()
            return _Unary(op=t.value, operand=operand, prefix=True)
        if t.kind == "OP" and t.value in ("++", "--"):
            self._next()
            operand = self._parse_unary()
            return _Unary(op=t.value, operand=operand, prefix=True)
        return self._parse_postfix()

    def _parse_postfix(self) -> _Node:
        node = self._parse_primary()
        t = self._peek()
        if t.kind == "OP" and t.value in ("++", "--"):
            self._next()
            return _Unary(op=t.value, operand=node, prefix=False)
        return node

    def _parse_primary(self) -> _Node:
        t = self._next()
        if t.kind == "NUMBER":
            return _Number(value=float(t.value))
        if t.kind == "STRING":
            return _String(value=_unescape(t.value[1:-1]))
        if t.kind == "REGEX":
            return _Regex(pattern=t.value[1:-1])
        if t.kind == "OP" and t.value == "$":
            return _Field(expr=self._parse_primary())
        if t.kind == "OP" and t.value == "(":
            inner = self._parse_expression()
            self._expect_op(")")
            return inner
        if t.kind == "KEYWORD" and t.value == "getline":
            target: _Node | None = None
            nxt = self._peek()
            if nxt.kind == "IDENT" or (nxt.kind == "OP" and nxt.value == "$"):
                target = self._parse_primary()
            return _Getline(target=target)
        if t.kind == "IDENT":
            name = t.value
            if self._eat_op("("):
                args: list[_Node] = []
                if not self._eat_op(")"):
                    args.append(self._parse_expression())
                    while self._eat_op(","):
                        args.append(self._parse_expression())
                    self._expect_op(")")
                return _Call(name=name, args=args)
            if self._eat_op("["):
                indices = [self._parse_expression()]
                while self._eat_op(","):
                    indices.append(self._parse_expression())
                self._expect_op("]")
                return _ArrayRef(name=name, indices=indices)
            return _Ident(name=name)
        raise SyntaxError(f"awk: unexpected token {t.value!r} at {t.pos}")


def _unescape(s: str) -> str:
    out: list[str] = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            esc = {
                "n": "\n",
                "t": "\t",
                "r": "\r",
                "\\": "\\",
                '"': '"',
                "/": "/",
                "0": "\0",
            }.get(nxt, nxt)
            out.append(esc)
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


# ---------------------------------------------------------------------------
# Runtime
# ---------------------------------------------------------------------------


class _BreakLoop(Exception):
    pass


class _ContinueLoop(Exception):
    pass


class _NextRecord(Exception):
    pass


class _ExitProgram(Exception):
    def __init__(self, code: int = 0) -> None:
        self.code = code


class _ReturnFn(Exception):
    def __init__(self, value: Any) -> None:
        self.value = value


@dataclass(slots=True)
class _Frame:
    locals_: dict[str, Any] = field(default_factory=dict)


class _Awk:
    """Walks the parsed AST against an input stream."""

    def __init__(self, program: _Program, io_ctx: IO, *, fs: int = -1) -> None:
        del fs
        self.program = program
        self.io = io_ctx
        self.globals: dict[str, Any] = {
            "NR": 0,
            "NF": 0,
            "FS": " ",
            "OFS": " ",
            "ORS": "\n",
            "FNR": 0,
            "FILENAME": "",
            "SUBSEP": "\x1c",
            "RS": "\n",
        }
        self.arrays: dict[str, dict[tuple[Any, ...], Any]] = {}
        self.fields: list[str] = []
        self.line: str = ""
        self.frames: list[_Frame] = []
        self._rng = random.Random()

    # --------------------------------------------------------------- variables

    def _get_var(self, name: str) -> Any:
        for frame in reversed(self.frames):
            if name in frame.locals_:
                return frame.locals_[name]
        return self.globals.get(name, "")

    def _set_var(self, name: str, value: Any) -> None:
        for frame in reversed(self.frames):
            if name in frame.locals_:
                frame.locals_[name] = value
                return
        self.globals[name] = value

    def _get_array(self, name: str) -> dict[tuple[Any, ...], Any]:
        for frame in reversed(self.frames):
            if name in frame.locals_ and isinstance(frame.locals_[name], dict):
                return frame.locals_[name]
        if name not in self.arrays:
            self.arrays[name] = {}
        return self.arrays[name]

    # --------------------------------------------------------------- evaluator

    def _eval(self, node: _Node) -> Any:
        if isinstance(node, _Number):
            return node.value
        if isinstance(node, _String):
            return node.value
        if isinstance(node, _Regex):
            return _to_num(re.search(node.pattern, self.line) is not None)
        if isinstance(node, _Ident):
            if node.name in self.arrays:
                return self.arrays[node.name]
            return self._get_var(node.name)
        if isinstance(node, _Field):
            idx = int(_to_num(self._eval(node.expr)))
            return _read_field(self.fields, self.line, idx)
        if isinstance(node, _ArrayRef):
            arr = self._get_array(node.name)
            key = tuple(_to_str(self._eval(i)) for i in node.indices)
            return arr.get(key, "")
        if isinstance(node, _Call):
            return self._call(node.name, node.args)
        if isinstance(node, _Unary):
            return self._eval_unary(node)
        if isinstance(node, _Binary):
            return self._eval_binary(node)
        if isinstance(node, _Concat):
            return _to_str(self._eval(node.left)) + _to_str(self._eval(node.right))
        if isinstance(node, _Match):
            left = _to_str(self._eval(node.left))
            right = node.right
            pat = right.pattern if isinstance(right, _Regex) else _to_str(self._eval(right))
            try:
                hit = re.search(pat, left) is not None
            except re.error:
                hit = False
            return _to_num(hit if node.op == "~" else not hit)
        if isinstance(node, _Ternary):
            return (
                self._eval(node.then_) if _truthy(self._eval(node.cond)) else self._eval(node.else_)
            )
        if isinstance(node, _Assign):
            return self._do_assign(node)
        if isinstance(node, _Getline):
            return 0  # streamed reads are exhausted by the main loop
        raise RuntimeError(f"awk: cannot evaluate {type(node).__name__}")

    def _eval_unary(self, node: _Unary) -> Any:
        if node.op in ("++", "--"):
            cur = _to_num(self._eval(node.operand))
            new = cur + 1 if node.op == "++" else cur - 1
            self._do_simple_assign(node.operand, new)
            return new if node.prefix else cur
        v = self._eval(node.operand)
        if node.op == "+":
            return _to_num(v)
        if node.op == "-":
            return -_to_num(v)
        if node.op == "!":
            return _to_num(not _truthy(v))
        raise RuntimeError(f"awk: unsupported unary {node.op}")

    def _eval_binary(self, node: _Binary) -> Any:
        op = node.op
        if op == "&&":
            return _to_num(_truthy(self._eval(node.left)) and _truthy(self._eval(node.right)))
        if op == "||":
            return _to_num(_truthy(self._eval(node.left)) or _truthy(self._eval(node.right)))
        if op == "in":
            arr_name = node.right.name if isinstance(node.right, _Ident) else None
            if arr_name is None:
                return 0
            arr = self._get_array(arr_name)
            key_val = self._eval(node.left)
            key = (_to_str(key_val),)
            return _to_num(key in arr)
        left = self._eval(node.left)
        right = self._eval(node.right)
        if op == "+":
            return _to_num(left) + _to_num(right)
        if op == "-":
            return _to_num(left) - _to_num(right)
        if op == "*":
            return _to_num(left) * _to_num(right)
        if op == "/":
            r = _to_num(right)
            return _to_num(left) / r if r else 0
        if op == "%":
            r = _to_num(right)
            return _to_num(left) % r if r else 0
        if op == "**":
            return _to_num(left) ** _to_num(right)
        # Comparisons: numeric if both look numeric, else string.
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            ln, rn = float(left), float(right)
            return _to_num(_cmp(ln, rn, op))
        ls, rs = _to_str(left), _to_str(right)
        return _to_num(_cmp(ls, rs, op))

    def _do_assign(self, node: _Assign) -> Any:
        if node.op == "=":
            val = self._eval(node.value)
            self._do_simple_assign(node.target, val)
            return val
        cur = _to_num(self._eval(node.target))
        rhs = _to_num(self._eval(node.value))
        new: float
        op = node.op[:-1]  # strip ``=``
        if op == "+":
            new = cur + rhs
        elif op == "-":
            new = cur - rhs
        elif op == "*":
            new = cur * rhs
        elif op == "/":
            new = cur / rhs if rhs else 0
        elif op == "%":
            new = cur % rhs if rhs else 0
        elif op in ("^", "**"):
            new = cur**rhs
        else:
            raise RuntimeError(f"awk: bad compound op {node.op}")
        self._do_simple_assign(node.target, new)
        return new

    def _do_simple_assign(self, target: _Node, value: Any) -> None:
        if isinstance(target, _Ident):
            self._set_var(target.name, value)
            return
        if isinstance(target, _ArrayRef):
            arr = self._get_array(target.name)
            key = tuple(_to_str(self._eval(i)) for i in target.indices)
            arr[key] = value
            return
        if isinstance(target, _Field):
            idx = int(_to_num(self._eval(target.expr)))
            _set_field(self, idx, _to_str(value))
            return
        raise RuntimeError("awk: invalid assignment target")

    # --------------------------------------------------------------- statements

    def _exec(self, node: _Node) -> None:
        if isinstance(node, _Block):
            for stmt in node.stmts:
                self._exec(stmt)
            return
        if isinstance(node, _ExprStmt):
            self._eval(node.expr)
            return
        if isinstance(node, _If):
            if _truthy(self._eval(node.cond)):
                self._exec(node.then_)
            elif node.else_ is not None:
                self._exec(node.else_)
            return
        if isinstance(node, _While):
            while _truthy(self._eval(node.cond)):
                try:
                    self._exec(node.body)
                except _ContinueLoop:
                    continue
                except _BreakLoop:
                    break
            return
        if isinstance(node, _For):
            if node.init is not None:
                self._eval(node.init)
            while node.cond is None or _truthy(self._eval(node.cond)):
                try:
                    self._exec(node.body)
                except _ContinueLoop:
                    pass
                except _BreakLoop:
                    break
                if node.step is not None:
                    self._eval(node.step)
            return
        if isinstance(node, _ForIn):
            arr = self._get_array(node.array)
            for key in list(arr.keys()):
                k = (
                    key[0]
                    if len(key) == 1
                    else self.globals["SUBSEP"].join(_to_str(p) for p in key)
                )
                self._set_var(node.var, k)
                try:
                    self._exec(node.body)
                except _ContinueLoop:
                    continue
                except _BreakLoop:
                    break
            return
        if isinstance(node, _Print):
            self._do_print(node.args)
            return
        if isinstance(node, _Printf):
            self._do_printf(node.args)
            return
        if isinstance(node, _Delete):
            arr = self._get_array(node.target.name)
            if node.target.indices:
                key = tuple(_to_str(self._eval(i)) for i in node.target.indices)
                arr.pop(key, None)
            else:
                arr.clear()
            return
        if isinstance(node, _Break):
            raise _BreakLoop
        if isinstance(node, _Continue):
            raise _ContinueLoop
        if isinstance(node, _Next):
            raise _NextRecord
        if isinstance(node, _Exit):
            code = int(_to_num(self._eval(node.code))) if node.code else 0
            raise _ExitProgram(code)
        if isinstance(node, _Return):
            val: Any = "" if node.value is None else self._eval(node.value)
            raise _ReturnFn(val)
        raise RuntimeError(f"awk: unknown statement {type(node).__name__}")

    # --------------------------------------------------------------- print / printf

    def _do_print(self, args: list[_Node]) -> None:
        if not args:
            text = self.line
        else:
            text = self.globals["OFS"].join(_to_str(self._eval(a)) for a in args)
        write_out(self.io, text + self.globals["ORS"])

    def _do_printf(self, args: list[_Node]) -> None:
        if not args:
            return
        fmt = _to_str(self._eval(args[0]))
        rendered = _printf_format(fmt, [self._eval(a) for a in args[1:]])
        write_out(self.io, rendered)

    # --------------------------------------------------------------- calls

    def _call(self, name: str, args: list[_Node]) -> Any:
        if name in self.program.functions:
            fn = self.program.functions[name]
            frame = _Frame()
            for i, p in enumerate(fn.params):
                frame.locals_[p] = self._eval(args[i]) if i < len(args) else ""
            self.frames.append(frame)
            try:
                self._exec(fn.body)
            except _ReturnFn as r:
                self.frames.pop()
                return r.value
            self.frames.pop()
            return ""
        return self._builtin(name, args)

    def _builtin(self, name: str, args: list[_Node]) -> Any:
        if name == "length":
            if not args:
                return len(self.line)
            v = self._eval(args[0])
            if isinstance(v, dict):
                return len(v)
            return len(_to_str(v))
        if name == "substr":
            s = _to_str(self._eval(args[0]))
            start = int(_to_num(self._eval(args[1]))) - 1
            if len(args) >= 3:
                length = int(_to_num(self._eval(args[2])))
                return s[max(start, 0) : max(start, 0) + length]
            return s[max(start, 0) :]
        if name == "index":
            s = _to_str(self._eval(args[0]))
            sub = _to_str(self._eval(args[1]))
            i = s.find(sub)
            return float(i + 1)
        if name == "split":
            s = _to_str(self._eval(args[0]))
            arr_node = args[1]
            sep_node = args[2] if len(args) >= 3 else None
            sep = (
                " "
                if sep_node is None
                else (
                    sep_node.pattern
                    if isinstance(sep_node, _Regex)
                    else _to_str(self._eval(sep_node))
                )
            )
            parts = _split_with(s, sep)
            if isinstance(arr_node, _Ident):
                arr = self._get_array(arr_node.name)
                arr.clear()
                for i, part in enumerate(parts, 1):
                    arr[(str(i),)] = part
            return float(len(parts))
        if name == "sub":
            pat = args[0].pattern if isinstance(args[0], _Regex) else _to_str(self._eval(args[0]))
            repl = _to_str(self._eval(args[1]))
            target = args[2] if len(args) >= 3 else _Field(expr=_Number(value=0))
            s = _to_str(self._eval(target))
            new, count = re.subn(pat, _awk_repl(repl), s, count=1)
            self._do_simple_assign(target, new)
            return float(count)
        if name == "gsub":
            pat = args[0].pattern if isinstance(args[0], _Regex) else _to_str(self._eval(args[0]))
            repl = _to_str(self._eval(args[1]))
            target = args[2] if len(args) >= 3 else _Field(expr=_Number(value=0))
            s = _to_str(self._eval(target))
            new, count = re.subn(pat, _awk_repl(repl), s)
            self._do_simple_assign(target, new)
            return float(count)
        if name == "match":
            pat = args[1].pattern if isinstance(args[1], _Regex) else _to_str(self._eval(args[1]))
            s = _to_str(self._eval(args[0]))
            m = re.search(pat, s)
            if m is None:
                self._set_var("RSTART", 0)
                self._set_var("RLENGTH", -1)
                return 0.0
            self._set_var("RSTART", float(m.start() + 1))
            self._set_var("RLENGTH", float(m.end() - m.start()))
            return float(m.start() + 1)
        if name == "toupper":
            return _to_str(self._eval(args[0])).upper()
        if name == "tolower":
            return _to_str(self._eval(args[0])).lower()
        if name == "sprintf":
            fmt = _to_str(self._eval(args[0]))
            return _printf_format(fmt, [self._eval(a) for a in args[1:]])
        if name == "int":
            return float(int(_to_num(self._eval(args[0]))))
        if name == "sqrt":
            return math.sqrt(_to_num(self._eval(args[0])))
        if name == "sin":
            return math.sin(_to_num(self._eval(args[0])))
        if name == "cos":
            return math.cos(_to_num(self._eval(args[0])))
        if name == "atan2":
            return math.atan2(_to_num(self._eval(args[0])), _to_num(self._eval(args[1])))
        if name == "exp":
            return math.exp(_to_num(self._eval(args[0])))
        if name == "log":
            return math.log(_to_num(self._eval(args[0])))
        if name == "rand":
            return self._rng.random()
        if name == "srand":
            seed = int(_to_num(self._eval(args[0]))) if args else 0
            self._rng.seed(seed)
            return 0.0
        if name == "system":
            return 0.0  # sandboxed: pretend commands succeed
        raise RuntimeError(f"awk: unknown function {name}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truthy(v: Any) -> bool:
    if isinstance(v, (int, float)):
        return float(v) != 0
    if isinstance(v, dict):
        return bool(v)
    if v == "":
        return False
    # awk treats numeric strings via their value.
    try:
        return float(v) != 0
    except (TypeError, ValueError):
        return True


def _to_num(v: Any) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, bool):
        return float(int(v))
    if v in (None, "", b""):
        return 0.0
    s = _to_str(v).strip()
    if not s:
        return 0.0
    m = re.match(r"^[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?", s)
    return float(m.group(0)) if m else 0.0


def _to_str(v: Any) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    if v is True:
        return "1"
    if v is False:
        return "0"
    return "" if v is None else str(v)


def _cmp(a: Any, b: Any, op: str) -> bool:
    return {
        "==": a == b,
        "!=": a != b,
        "<": a < b,
        "<=": a <= b,
        ">": a > b,
        ">=": a >= b,
    }[op]


def _read_field(fields: list[str], line: str, idx: int) -> str:
    if idx == 0:
        return line
    if 1 <= idx <= len(fields):
        return fields[idx - 1]
    return ""


def _set_field(awk: _Awk, idx: int, value: str) -> None:
    if idx == 0:
        awk.line = value
        awk.fields = _split_with(value, awk.globals["FS"])
        awk.globals["NF"] = len(awk.fields)
        return
    while len(awk.fields) < idx:
        awk.fields.append("")
    awk.fields[idx - 1] = value
    awk.globals["NF"] = max(awk.globals["NF"], idx)
    awk.line = awk.globals["OFS"].join(awk.fields)


def _split_with(line: str, sep: str) -> list[str]:
    if sep == " ":
        return line.split()
    if len(sep) == 1:
        return line.split(sep)
    return re.split(sep, line)


def _awk_repl(repl: str) -> Callable[[re.Match[str]], str]:
    def fn(m: re.Match[str]) -> str:
        out: list[str] = []
        i = 0
        while i < len(repl):
            ch = repl[i]
            if ch == "\\" and i + 1 < len(repl):
                nxt = repl[i + 1]
                if nxt == "&":
                    out.append("&")
                    i += 2
                    continue
                out.append(nxt)
                i += 2
                continue
            if ch == "&":
                out.append(m.group(0))
                i += 1
                continue
            out.append(ch)
            i += 1
        return "".join(out)

    return fn


_PRINTF_RE = re.compile(
    r"%(?P<flags>[-+ 0#]*)(?P<width>\d*)(?:\.(?P<prec>\d+))?(?P<conv>[%dsifgeoxXc])"
)


def _printf_format(fmt: str, args: list[Any]) -> str:
    out: list[str] = []
    i = 0
    arg_idx = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "\\" and i + 1 < len(fmt):
            nxt = fmt[i + 1]
            out.append({"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(nxt, nxt))
            i += 2
            continue
        if ch != "%":
            out.append(ch)
            i += 1
            continue
        m = _PRINTF_RE.match(fmt, i)
        if m is None:
            out.append(ch)
            i += 1
            continue
        conv = m.group("conv")
        spec = (
            "%"
            + (m.group("flags") or "")
            + (m.group("width") or "")
            + (f".{m.group('prec')}" if m.group("prec") is not None else "")
            + ("d" if conv == "d" else conv)
        )
        i = m.end()
        if conv == "%":
            out.append("%")
            continue
        if arg_idx >= len(args):
            arg: Any = ""
        else:
            arg = args[arg_idx]
            arg_idx += 1
        if conv == "s":
            out.append(spec % _to_str(arg))
        elif conv == "d" or conv == "i":
            out.append(spec % int(_to_num(arg)))
        elif conv in ("f", "g", "e"):
            out.append(spec % _to_num(arg))
        elif conv in ("o", "x", "X"):
            out.append(spec % int(_to_num(arg)))
        elif conv == "c":
            out.append(_to_str(arg)[:1])
    return "".join(out)


# ---------------------------------------------------------------------------
# Top-level command
# ---------------------------------------------------------------------------


def cmd_awk(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, positional = parse_flags(argv, valued={"-F", "-v", "-f"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"awk: {e}\n")
        return 2
    if "-f" in flags:
        program_text = interp.fs.read_text(str(flags["-f"]))
        files = positional
    else:
        if not positional:
            write_err(io_ctx, b"awk: missing program\n")
            return 2
        program_text = positional[0]
        files = positional[1:]
    try:
        program = _Parser(_tokenize(program_text)).parse_program()
    except SyntaxError as e:
        write_err(io_ctx, f"awk: {e}\n".encode())
        return 2
    awk = _Awk(program, io_ctx)
    awk.globals["FS"] = str(flags.get("-F", " "))
    if "-v" in flags:
        for v in str(flags["-v"]).split(","):
            if "=" in v:
                k, _, val = v.partition("=")
                awk.globals[k] = val
    # BEGIN
    try:
        for rule in program.rules:
            if rule.kind == "BEGIN" and rule.action is not None:
                awk._exec(rule.action)
        data, rc = read_input(interp, io_ctx, files)
        text = data.decode("utf-8", errors="replace")
        lines = text.split("\n")
        if text.endswith("\n"):
            lines = lines[:-1]
        for raw in lines:
            awk.globals["NR"] = awk.globals.get("NR", 0) + 1
            awk.globals["FNR"] = awk.globals.get("FNR", 0) + 1
            awk.line = raw
            awk.fields = _split_with(raw, awk.globals["FS"])
            awk.globals["NF"] = len(awk.fields)
            try:
                for rule in program.rules:
                    if rule.kind != "main":
                        continue
                    if not _pattern_match(awk, rule):
                        continue
                    if rule.action is None:
                        write_out(io_ctx, awk.line + awk.globals["ORS"])
                    else:
                        awk._exec(rule.action)
            except _NextRecord:
                continue
        for rule in program.rules:
            if rule.kind == "END" and rule.action is not None:
                awk._exec(rule.action)
    except _ExitProgram as e:
        return e.code
    return rc


def _pattern_match(awk: _Awk, rule: _Rule) -> bool:
    if rule.pattern is None:
        return True
    if isinstance(rule.pattern, _Regex):
        try:
            return re.search(rule.pattern.pattern, awk.line) is not None
        except re.error:
            return False
    return _truthy(awk._eval(rule.pattern))


__all__ = ["cmd_awk"]
