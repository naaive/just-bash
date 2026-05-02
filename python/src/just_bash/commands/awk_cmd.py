"""``awk`` - tiny pattern-action language.

Supports a small but useful subset:
  - ``BEGIN { ... }`` / ``END { ... }`` blocks
  - pattern ``/regex/`` and expression patterns
  - ``$0``, ``$1`` ... field access, ``NR``, ``NF``, ``FS``, ``OFS``
  - ``print`` and ``printf``
  - simple expression evaluation (arithmetic, string concat, comparisons)
  - ``-F sep`` / ``-v var=value``
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


@dataclass(slots=True)
class AwkRule:
    pattern: str  # 'BEGIN' / 'END' / regex / 'expr' / ''
    pattern_text: str
    action: str


@dataclass(slots=True)
class AwkState:
    fields: list[str] = field(default_factory=list)
    line: str = ""
    nr: int = 0
    fs_value: str = " "
    ofs: str = " "
    ors: str = "\n"
    variables: dict[str, str | float] = field(default_factory=dict)


def cmd_awk(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, positional = parse_flags(argv, valued={"-F", "-v"}, boolean=set())
    except ValueError as e:
        write_err(io_ctx, f"awk: {e}\n")
        return 2
    if not positional:
        write_err(io_ctx, b"awk: missing program\n")
        return 2
    program = positional[0]
    files = positional[1:]
    rules = _parse_program(program)
    state = AwkState(fs_value=str(flags.get("-F", " ")))
    if "-v" in flags:
        for v in str(flags["-v"]).split(","):
            if "=" in v:
                k, _, val = v.partition("=")
                state.variables[k] = val
    # BEGIN
    for rule in rules:
        if rule.pattern == "BEGIN":
            _exec_action(rule.action, state, io_ctx)
    data, rc = read_input(interp, io_ctx, files)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    for raw in lines:
        state.nr += 1
        state.line = raw
        state.fields = _split_fields(raw, state.fs_value)
        for rule in rules:
            if rule.pattern in ("BEGIN", "END"):
                continue
            if not _pattern_matches(rule, state):
                continue
            _exec_action(rule.action, state, io_ctx)
    for rule in rules:
        if rule.pattern == "END":
            _exec_action(rule.action, state, io_ctx)
    return rc


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_program(text: str) -> list[AwkRule]:
    """Split top-level rules ``pattern { action }``. Default action is ``{ print }``."""
    rules: list[AwkRule] = []
    i = 0
    n = len(text)
    while i < n:
        while i < n and text[i] in " \t\n;":
            i += 1
        if i >= n:
            break
        # Pattern up to '{' or end of statement.
        pat, i = _scan_pattern(text, i)
        action: str
        # Skip whitespace.
        while i < n and text[i] in " \t":
            i += 1
        if i < n and text[i] == "{":
            action, i = _scan_action(text, i)
        else:
            action = "{ print }"
        kind, body = _classify_pattern(pat)
        rules.append(AwkRule(pattern=kind, pattern_text=body, action=action))
    return rules


def _scan_pattern(text: str, i: int) -> tuple[str, int]:
    n = len(text)
    out: list[str] = []
    depth = 0
    while i < n:
        ch = text[i]
        if depth == 0 and ch == "{":
            break
        if depth == 0 and ch == "\n":
            break
        if ch == "/" or ch == '"':
            quote = ch
            out.append(ch)
            i += 1
            while i < n and text[i] != quote:
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                i += 1
            if i < n:
                out.append(text[i])
                i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out).strip(), i


def _scan_action(text: str, i: int) -> tuple[str, int]:
    n = len(text)
    assert text[i] == "{"
    depth = 0
    out: list[str] = []
    while i < n:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                out.append(ch)
                return "".join(out), i + 1
        out.append(ch)
        i += 1
    return "".join(out), i


def _classify_pattern(pat: str) -> tuple[str, str]:
    if pat == "":
        return "", ""
    if pat == "BEGIN":
        return "BEGIN", ""
    if pat == "END":
        return "END", ""
    if pat.startswith("/") and pat.endswith("/") and len(pat) >= 2:
        return "regex", pat[1:-1]
    return "expr", pat


# ---------------------------------------------------------------------------
# Pattern eval
# ---------------------------------------------------------------------------


def _pattern_matches(rule: AwkRule, state: AwkState) -> bool:
    if rule.pattern == "":
        return True
    if rule.pattern == "regex":
        try:
            return re.search(rule.pattern_text, state.line) is not None
        except re.error:
            return False
    return _truthy(_eval_expr(rule.pattern_text, state))


# ---------------------------------------------------------------------------
# Expression evaluator
# ---------------------------------------------------------------------------


def _eval_expr(expr: str, state: AwkState) -> str | float:
    expr = expr.strip()
    if not expr:
        return ""
    return _Eval(expr, state).parse_or()


class _Eval:
    """Tiny precedence-climbing evaluator for awk expressions."""

    __slots__ = ("pos", "state", "text")

    def __init__(self, text: str, state: AwkState) -> None:
        self.text = text
        self.pos = 0
        self.state = state

    def _peek(self, n: int = 1) -> str:
        self._skip()
        return self.text[self.pos : self.pos + n]

    def _skip(self) -> None:
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def _eat(self, s: str) -> bool:
        self._skip()
        if self.text.startswith(s, self.pos):
            self.pos += len(s)
            return True
        return False

    def parse_or(self) -> str | float:
        left = self.parse_and()
        while self._eat("||"):
            right = self.parse_and()
            left = 1 if _truthy(left) or _truthy(right) else 0
        return left

    def parse_and(self) -> str | float:
        left = self.parse_relational()
        while self._eat("&&"):
            right = self.parse_relational()
            left = 1 if _truthy(left) and _truthy(right) else 0
        return left

    def parse_relational(self) -> str | float:
        left = self.parse_concat()
        for op in ("==", "!=", "<=", ">=", "<", ">", "~", "!~"):
            if self._eat(op):
                right = self.parse_concat()
                return _apply_relational(op, left, right)
        return left

    def parse_concat(self) -> str | float:
        left = self.parse_additive()
        # Concatenation: implicit when next looks like a primary.
        while True:
            self._skip()
            if self.pos >= len(self.text):
                break
            ch = self.text[self.pos]
            if ch in '"$' or ch.isalpha() or ch.isdigit() or ch == "(":
                right = self.parse_additive()
                left = _to_str(left) + _to_str(right)
                continue
            break
        return left

    def parse_additive(self) -> str | float:
        left = self.parse_multiplicative()
        while True:
            if self._eat("+"):
                right = self.parse_multiplicative()
                left = _to_num(left) + _to_num(right)
                continue
            if self._eat("-"):
                right = self.parse_multiplicative()
                left = _to_num(left) - _to_num(right)
                continue
            break
        return left

    def parse_multiplicative(self) -> str | float:
        left = self.parse_unary()
        while True:
            if self._eat("*"):
                right = self.parse_unary()
                left = _to_num(left) * _to_num(right)
                continue
            if self._eat("/"):
                right = self.parse_unary()
                rn = _to_num(right)
                left = _to_num(left) / rn if rn else 0
                continue
            if self._eat("%"):
                right = self.parse_unary()
                rn = _to_num(right)
                left = _to_num(left) % rn if rn else 0
                continue
            break
        return left

    def parse_unary(self) -> str | float:
        if self._eat("!"):
            return 0 if _truthy(self.parse_unary()) else 1
        if self._eat("-"):
            return -_to_num(self.parse_unary())
        if self._eat("+"):
            return _to_num(self.parse_unary())
        return self.parse_primary()

    def parse_primary(self) -> str | float:
        self._skip()
        if self.pos >= len(self.text):
            return ""
        ch = self.text[self.pos]
        if ch == "(":
            self.pos += 1
            v = self.parse_or()
            self._eat(")")
            return v
        if ch == '"':
            self.pos += 1
            out = []
            while self.pos < len(self.text) and self.text[self.pos] != '"':
                if self.text[self.pos] == "\\" and self.pos + 1 < len(self.text):
                    nxt = self.text[self.pos + 1]
                    out.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(nxt, nxt))
                    self.pos += 2
                    continue
                out.append(self.text[self.pos])
                self.pos += 1
            if self.pos < len(self.text):
                self.pos += 1
            return "".join(out)
        if ch == "$":
            self.pos += 1
            num = self.parse_primary()
            return _read_field(self.state, int(_to_num(num)))
        if ch.isdigit() or ch == ".":
            j = self.pos
            while j < len(self.text) and (self.text[j].isdigit() or self.text[j] == "."):
                j += 1
            value = float(self.text[self.pos : j])
            self.pos = j
            return value
        if ch.isalpha() or ch == "_":
            j = self.pos
            while j < len(self.text) and (self.text[j].isalnum() or self.text[j] == "_"):
                j += 1
            name = self.text[self.pos : j]
            self.pos = j
            return _lookup_var(self.state, name)
        # Unknown - return empty string.
        self.pos = len(self.text)
        return ""


def _apply_relational(op: str, left: str | float, right: str | float) -> str | float:
    if op == "~":
        return 1 if re.search(_to_str(right), _to_str(left)) else 0
    if op == "!~":
        return 0 if re.search(_to_str(right), _to_str(left)) else 1
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        ln, rn = float(left), float(right)
        return {
            "==": 1 if ln == rn else 0,
            "!=": 1 if ln != rn else 0,
            "<=": 1 if ln <= rn else 0,
            ">=": 1 if ln >= rn else 0,
            "<": 1 if ln < rn else 0,
            ">": 1 if ln > rn else 0,
        }[op]
    ls, rs = _to_str(left), _to_str(right)
    return {
        "==": 1 if ls == rs else 0,
        "!=": 1 if ls != rs else 0,
        "<=": 1 if ls <= rs else 0,
        ">=": 1 if ls >= rs else 0,
        "<": 1 if ls < rs else 0,
        ">": 1 if ls > rs else 0,
    }[op]


def _to_str(v: str | float) -> str:
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _to_num(v: str | float) -> float:
    if isinstance(v, (int, float)):
        return float(v)
    s = v.strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        # awk parses leading numeric prefix.
        m = re.match(r"^[+-]?(\d+(\.\d*)?|\.\d+)", s)
        return float(m.group(0)) if m else 0.0


def _truthy(v: str | float) -> bool:
    if isinstance(v, (int, float)):
        return v != 0
    return v != ""


def _read_field(state: AwkState, idx: int) -> str:
    if idx == 0:
        return state.line
    if 1 <= idx <= len(state.fields):
        return state.fields[idx - 1]
    return ""


def _lookup_var(state: AwkState, name: str) -> str | float:
    if name == "NR":
        return state.nr
    if name == "NF":
        return len(state.fields)
    if name == "FS":
        return state.fs_value
    if name == "OFS":
        return state.ofs
    if name == "ORS":
        return state.ors
    return state.variables.get(name, "")


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------


def _exec_action(action: str, state: AwkState, io_ctx: IO) -> None:
    """Execute the action body. Body must be wrapped in ``{ ... }``."""
    body = action.strip()
    if body.startswith("{"):
        body = body[1:]
    if body.endswith("}"):
        body = body[:-1]
    for stmt in _split_statements(body):
        stmt = stmt.strip()
        if not stmt:
            continue
        _exec_stmt(stmt, state, io_ctx)


def _split_statements(body: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    in_quote = False
    quote_ch = ""
    i = 0
    while i < len(body):
        ch = body[i]
        if in_quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(body):
                cur.append(body[i + 1])
                i += 2
                continue
            if ch == quote_ch:
                in_quote = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_ch = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        if depth == 0 and ch in (";", "\n"):
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if cur:
        out.append("".join(cur))
    return out


def _exec_stmt(stmt: str, state: AwkState, io_ctx: IO) -> None:
    if stmt.startswith("print"):
        rest = stmt[5:].strip()
        if not rest:
            write_out(io_ctx, state.line + state.ors)
            return
        # Comma-separated expressions joined by OFS.
        parts = _split_top_level(rest, ",")
        values = [_to_str(_eval_expr(p, state)) for p in parts]
        write_out(io_ctx, state.ofs.join(values) + state.ors)
        return
    if stmt.startswith("printf"):
        rest = stmt[6:].strip()
        parts = _split_top_level(rest, ",")
        if not parts:
            return
        fmt = _to_str(_eval_expr(parts[0], state))
        args = [_to_str(_eval_expr(p, state)) for p in parts[1:]]
        rendered = _printf(fmt, args)
        write_out(io_ctx, rendered)
        return
    # Compound assignment: NAME OP= EXPR
    for compound in ("+=", "-=", "*=", "/=", "%="):
        if compound in stmt:
            name, _, value = stmt.partition(compound)
            name = name.strip()
            if not name.isidentifier():
                break
            cur = _to_num(_lookup_var(state, name))
            rhs = _to_num(_eval_expr(value, state))
            new: float
            if compound == "+=":
                new = cur + rhs
            elif compound == "-=":
                new = cur - rhs
            elif compound == "*=":
                new = cur * rhs
            elif compound == "/=":
                new = cur / rhs if rhs else 0
            else:
                new = cur % rhs if rhs else 0
            state.variables[name] = new
            return
    # Plain assignment: NAME = EXPR
    if "=" in stmt and not any(op in stmt for op in ("==", "!=", "<=", ">=")):
        name, _, value = stmt.partition("=")
        name = name.strip()
        if name.isidentifier():
            v = _eval_expr(value, state)
            if isinstance(v, (int, float)) and float(v).is_integer():
                state.variables[name] = float(v)
            else:
                state.variables[name] = v
            return
    # Bare expression: evaluate and discard (could be `next` etc., not supported).
    _eval_expr(stmt, state)


def _split_top_level(text: str, sep: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    depth = 0
    in_quote = False
    quote_ch = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if in_quote:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 2
                continue
            if ch == quote_ch:
                in_quote = False
            i += 1
            continue
        if ch in ('"', "'"):
            in_quote = True
            quote_ch = ch
            cur.append(ch)
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if depth == 0 and ch == sep:
            out.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    if cur:
        out.append("".join(cur))
    return [c.strip() for c in out]


# ---------------------------------------------------------------------------
# Field splitting
# ---------------------------------------------------------------------------


def _split_fields(line: str, fs: str) -> list[str]:
    if fs == " ":
        return line.split()
    if len(fs) == 1:
        return line.split(fs)
    return re.split(fs, line)


# ---------------------------------------------------------------------------
# printf
# ---------------------------------------------------------------------------


_AWK_FMT = re.compile(r"%(?P<flags>[-+ 0#]*)(?P<width>\d*)(?:\.(?P<prec>\d+))?(?P<conv>[%dsfgoxX])")


def _printf(fmt: str, args: list[str]) -> str:
    out: list[str] = []
    i = 0
    while i < len(fmt):
        ch = fmt[i]
        if ch == "\\" and i + 1 < len(fmt):
            nxt = fmt[i + 1]
            out.append({"n": "\n", "t": "\t", "\\": "\\"}.get(nxt, nxt))
            i += 2
            continue
        if ch != "%":
            out.append(ch)
            i += 1
            continue
        m = _AWK_FMT.match(fmt, i)
        if m is None:
            out.append(ch)
            i += 1
            continue
        conv = m.group("conv")
        i = m.end()
        if conv == "%":
            out.append("%")
            continue
        if not args:
            arg = ""
        else:
            arg = args.pop(0)
        spec = (
            "%"
            + (m.group("flags") or "")
            + (m.group("width") or "")
            + (f".{m.group('prec')}" if m.group("prec") else "")
            + conv
        )
        if conv == "s":
            out.append(spec % arg)
        elif conv == "d":
            out.append(spec % int(_to_num(arg)))
        elif conv in ("f", "g"):
            out.append(spec % _to_num(arg))
        elif conv in ("o", "x", "X"):
            out.append(spec % int(_to_num(arg)))
    return "".join(out)


__all__ = ["cmd_awk"]
