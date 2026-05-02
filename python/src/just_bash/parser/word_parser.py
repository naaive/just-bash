"""Parse a raw word string from the lexer into a structured ``Word`` AST.

The lexer hands the parser raw word text including quotes and ``$...``
expansions. This module decodes that text into ``WordPart`` nodes so the
interpreter can do expansion deterministically.
"""

from __future__ import annotations

from just_bash.ast.nodes import (
    ArithmeticExpansion,
    AssignDefault,
    BraceExpansion,
    BraceItem,
    BraceRange,
    BraceWord,
    CommandSubstitution,
    DefaultValue,
    DoubleQuoted,
    ErrorIfUnset,
    Escaped,
    Length,
    Literal,
    ParameterExpansion,
    ParameterOp,
    PatternRemoval,
    PatternReplacement,
    Script,
    SingleQuoted,
    Substring,
    TildeExpansion,
    UseAlternative,
    Word,
    WordPart,
)


class WordParseError(Exception):
    """Raised when a word's internal structure is malformed (mostly ``${...}``)."""


def parse_word(raw: str, line: int = 0, *, allow_tilde: bool = True) -> Word:
    """Decode raw word text from the lexer into a ``Word`` AST."""
    parts: list[WordPart] = []
    i = 0
    n = len(raw)
    started = True  # tracks word-start position for tilde expansion
    # Process substitution: ``<(cmd)`` or ``>(cmd)`` - the lexer emits these
    # as a WORD whose first character is ``<`` or ``>``.
    if n >= 3 and raw[0] in ("<", ">") and raw[1] == "(" and raw[-1] == ")":
        from just_bash.parser.parser import parse as _parse_script

        inner = raw[2:-1]
        body = _parse_script(inner)
        from just_bash.ast.nodes import ProcessSubstitution

        direction: str = "input" if raw[0] == "<" else "output"
        parts.append(ProcessSubstitution(line=line, body=body, direction=direction))  # type: ignore[arg-type]
        return Word(line=line, parts=parts)
    while i < n:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            parts.append(Escaped(line=line, value=raw[i + 1]))
            i += 2
            started = False
            continue
        if ch == "'":
            end = raw.index("'", i + 1)
            parts.append(SingleQuoted(line=line, value=raw[i + 1 : end]))
            i = end + 1
            started = False
            continue
        if ch == '"':
            end, dq = _parse_double_quoted(raw, i, line)
            parts.append(dq)
            i = end
            started = False
            continue
        if ch == "$":
            end, expansion = _parse_dollar(raw, i, line)
            parts.append(expansion)
            i = end
            started = False
            continue
        if ch == "`":
            end, sub = _parse_backtick(raw, i, line)
            parts.append(sub)
            i = end
            started = False
            continue
        if ch == "~" and allow_tilde and started:
            j = i + 1
            while j < n and (raw[j].isalnum() or raw[j] in "._-"):
                j += 1
            user = raw[i + 1 : j] or None
            parts.append(TildeExpansion(line=line, user=user))
            i = j
            started = False
            continue
        if ch == "{":
            end, brace = _try_parse_brace(raw, i, line)
            if brace is not None:
                parts.append(brace)
                i = end
                started = False
                continue
        # Plain literal text - merge with previous literal if possible.
        if parts and isinstance(parts[-1], Literal):
            parts[-1].value += ch
        else:
            parts.append(Literal(line=line, value=ch))
        i += 1
        started = False
    return Word(line=line, parts=parts)


def _parse_double_quoted(raw: str, start: int, line: int) -> tuple[int, DoubleQuoted]:
    """Parse from the opening ``"`` to its matching close. Returns (end_index, node)."""
    i = start + 1
    n = len(raw)
    parts: list[WordPart] = []
    while i < n:
        ch = raw[i]
        if ch == '"':
            return i + 1, DoubleQuoted(line=line, parts=parts)
        if ch == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            # Inside double quotes only \, $, `, ", and newline get escaped.
            if nxt in ('"', "\\", "$", "`", "\n"):
                parts.append(Escaped(line=line, value=nxt))
                i += 2
                continue
            # Other backslashes are literal.
            if parts and isinstance(parts[-1], Literal):
                parts[-1].value += ch
            else:
                parts.append(Literal(line=line, value=ch))
            i += 1
            continue
        if ch == "$":
            end, exp = _parse_dollar(raw, i, line)
            parts.append(exp)
            i = end
            continue
        if ch == "`":
            end, sub = _parse_backtick(raw, i, line)
            parts.append(sub)
            i = end
            continue
        if parts and isinstance(parts[-1], Literal):
            parts[-1].value += ch
        else:
            parts.append(Literal(line=line, value=ch))
        i += 1
    raise WordParseError("unterminated double-quoted string")


def _parse_dollar(raw: str, start: int, line: int) -> tuple[int, WordPart]:
    """``$``-introduced expansion (parameter / command sub / arithmetic)."""
    n = len(raw)
    if start + 1 >= n:
        return start + 1, Literal(line=line, value="$")
    nxt = raw[start + 1]
    if nxt == "{":
        return _parse_brace_param(raw, start, line)
    if nxt == "(":
        if start + 2 < n and raw[start + 2] == "(":
            return _parse_arith(raw, start, line)
        return _parse_command_sub(raw, start, line)
    if nxt.isalpha() or nxt == "_":
        j = start + 2
        while j < n and (raw[j].isalnum() or raw[j] == "_"):
            j += 1
        return j, ParameterExpansion(line=line, parameter=raw[start + 1 : j])
    if nxt.isdigit() or nxt in "@*#?-$!":
        return start + 2, ParameterExpansion(line=line, parameter=nxt)
    return start + 1, Literal(line=line, value="$")


def _parse_brace_param(raw: str, start: int, line: int) -> tuple[int, ParameterExpansion]:
    """``${...}`` parameter expansion with all the operators we support."""
    n = len(raw)
    i = start + 2  # skip ${
    depth = 1
    body_start = i
    while i < n and depth > 0:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "'":
            i = raw.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _scan_double_quoted_end(raw, i)
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                body = raw[body_start:i]
                return i + 1, _parse_param_body(body, line)
        i += 1
    raise WordParseError("unterminated ${...}")


def _scan_double_quoted_end(raw: str, start: int) -> int:
    i = start + 1
    n = len(raw)
    while i < n:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == '"':
            return i + 1
        i += 1
    raise WordParseError("unterminated double-quoted string in ${...}")


def _parse_param_body(body: str, line: int) -> ParameterExpansion:
    """Decode the body inside ``${...}`` into a parameter name + operation."""
    # ${!arr[@]} / ${!arr[*]} - array key list.
    if body.startswith("!") and "[" in body and body.endswith("]"):
        bracket = body.index("[")
        name = body[1:bracket]
        if name and (name[0].isalpha() or name[0] == "_"):
            subscript = body[bracket + 1 : -1]
            if subscript in ("@", "*"):
                return ParameterExpansion(
                    line=line, parameter=name, subscript=subscript, array_keys=True
                )
    # ${#name} or ${#name[@]} - length.
    if body.startswith("#") and len(body) > 1 and (body[1].isalpha() or body[1] == "_"):
        rest = body[1:]
        # Strip optional [@] / [*] / [N] off the name for length.
        sub: str | None = None
        if "[" in rest and rest.endswith("]"):
            br = rest.index("[")
            sub = rest[br + 1 : -1]
            rest = rest[:br]
        return ParameterExpansion(line=line, parameter=rest, operation=Length(), subscript=sub)
    name_end = 0
    while name_end < len(body) and (body[name_end].isalnum() or body[name_end] == "_"):
        name_end += 1
    if name_end == 0 and body and body[0] in "@*#?-$!":
        # Special parameter like $@, $*, $#, $?
        name_end = 1
    name = body[:name_end]
    rest = body[name_end:]
    subscript: str | None = None
    if rest.startswith("["):
        # Find matching ] respecting nested brackets.
        depth = 1
        j = 1
        while j < len(rest) and depth > 0:
            if rest[j] == "[":
                depth += 1
            elif rest[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        subscript = rest[1:j]
        rest = rest[j + 1 :]
    if not rest:
        return ParameterExpansion(line=line, parameter=name, subscript=subscript)
    op = _parse_param_op(rest, line)
    return ParameterExpansion(line=line, parameter=name, operation=op, subscript=subscript)


def _parse_param_op(rest: str, line: int) -> ParameterOp:
    """Parse the operator suffix inside ``${VAR<rest>}``."""
    # Default/assign/error/alternative
    if rest.startswith((":-", "-")):
        ce = rest.startswith(":-")
        word = parse_word(rest[2:] if ce else rest[1:], line=line)
        return DefaultValue(word=word, check_empty=ce)
    if rest.startswith((":=", "=")):
        ce = rest.startswith(":=")
        word = parse_word(rest[2:] if ce else rest[1:], line=line)
        return AssignDefault(word=word, check_empty=ce)
    if rest.startswith((":?", "?")):
        ce = rest.startswith(":?")
        body = rest[2:] if ce else rest[1:]
        word = parse_word(body, line=line) if body else None
        return ErrorIfUnset(word=word, check_empty=ce)
    if rest.startswith((":+", "+")):
        ce = rest.startswith(":+")
        word = parse_word(rest[2:] if ce else rest[1:], line=line)
        return UseAlternative(word=word, check_empty=ce)
    # Substring
    if rest.startswith(":"):
        return _parse_substring_op(rest[1:], line)
    # Pattern removal
    if rest.startswith("##"):
        return PatternRemoval(pattern=parse_word(rest[2:], line=line), side="prefix", greedy=True)
    if rest.startswith("#"):
        return PatternRemoval(pattern=parse_word(rest[1:], line=line), side="prefix", greedy=False)
    if rest.startswith("%%"):
        return PatternRemoval(pattern=parse_word(rest[2:], line=line), side="suffix", greedy=True)
    if rest.startswith("%"):
        return PatternRemoval(pattern=parse_word(rest[1:], line=line), side="suffix", greedy=False)
    # Pattern replacement: /pat/repl, //pat/repl, /#pat/repl, /%pat/repl
    if rest.startswith("/"):
        return _parse_replacement_op(rest[1:], line)
    raise WordParseError(f"unsupported parameter operator: {rest!r}")


def _parse_substring_op(body: str, line: int) -> Substring:
    # Split on first unescaped ":".
    offset_str, _, length_str = body.partition(":")
    from just_bash.parser.arithmetic_parser import parse_arith_text

    offset = parse_arith_text(offset_str)
    length = parse_arith_text(length_str) if length_str else None
    offset.line = line
    if length is not None:
        length.line = line
    return Substring(offset=offset, length=length)


def _parse_replacement_op(body: str, line: int) -> PatternReplacement:
    all_occ = body.startswith("/")
    if all_occ:
        body = body[1:]
    anchor: str | None = None
    if body.startswith("#"):
        anchor = "start"
        body = body[1:]
    elif body.startswith("%"):
        anchor = "end"
        body = body[1:]
    # Pattern goes up to the first unescaped, unquoted "/".
    pat_end = _find_unquoted(body, "/")
    if pat_end < 0:
        pattern_text, replacement_text = body, None
    else:
        pattern_text = body[:pat_end]
        replacement_text = body[pat_end + 1 :]
    pattern = parse_word(pattern_text, line=line)
    replacement = parse_word(replacement_text, line=line) if replacement_text is not None else None
    return PatternReplacement(
        pattern=pattern,
        replacement=replacement,
        all_occurrences=all_occ,
        anchor=anchor,  # type: ignore[arg-type]
    )


def _find_unquoted(s: str, target: str) -> int:
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "'":
            i = s.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _scan_double_quoted_end(s, i)
            continue
        if ch == target:
            return i
        i += 1
    return -1


def _parse_command_sub(raw: str, start: int, line: int) -> tuple[int, CommandSubstitution]:
    """``$( ... )`` - parse the inner text as a script."""
    from just_bash.parser.parser import parse

    n = len(raw)
    i = start + 2  # skip $(
    depth = 1
    body_start = i
    while i < n and depth > 0:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "'":
            i = raw.index("'", i + 1) + 1
            continue
        if ch == '"':
            i = _scan_double_quoted_end(raw, i)
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                inner = raw[body_start:i]
                script = parse(inner)
                return i + 1, CommandSubstitution(line=line, body=script)
        i += 1
    raise WordParseError("unterminated $(...)")


def _parse_backtick(raw: str, start: int, line: int) -> tuple[int, CommandSubstitution]:
    from just_bash.parser.parser import parse

    n = len(raw)
    i = start + 1
    body: list[str] = []
    while i < n:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            nxt = raw[i + 1]
            if nxt in ("$", "`", "\\"):
                body.append(nxt)
                i += 2
                continue
            body.append(ch)
            body.append(nxt)
            i += 2
            continue
        if ch == "`":
            script = parse("".join(body))
            return i + 1, CommandSubstitution(line=line, body=script, legacy=True)
        body.append(ch)
        i += 1
    raise WordParseError("unterminated backtick command substitution")


def _parse_arith(raw: str, start: int, line: int) -> tuple[int, ArithmeticExpansion]:
    """``$(( expr ))`` arithmetic expansion.

    If the inner contains shell expansions (``$(...)`` / ``$VAR``) that the
    arithmetic parser can't lex, we store the source text without a parsed
    expression; ``eval_arith`` re-expands it at runtime via the word
    machinery and re-parses the resulting numeric text.
    """
    from just_bash.ast.nodes import Arithmetic, ArithNumber
    from just_bash.parser.arithmetic_parser import ArithParseError, parse_arith_text

    n = len(raw)
    i = start + 3  # skip $((
    depth = 1
    body_start = i
    while i < n and depth > 0:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            i += 2
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 1 and i + 1 < n and raw[i + 1] == ")":
                inner = raw[body_start:i]
                try:
                    expr = parse_arith_text(inner)
                    expr.line = line
                except ArithParseError:
                    # Defer parsing to runtime by stashing only the text.
                    expr = Arithmetic(
                        line=line,
                        expression=ArithNumber(value=0),
                        source_text=inner,
                    )
                return i + 2, ArithmeticExpansion(line=line, expression=expr)
            depth -= 1
        i += 1
    raise WordParseError("unterminated $((...))")


def _try_parse_brace(raw: str, start: int, line: int) -> tuple[int, BraceExpansion | None]:
    """Attempt brace expansion. Returns ``(end, None)`` if not a brace pattern."""
    n = len(raw)
    i = start + 1
    depth = 1
    items_text: list[str] = []
    cur: list[str] = []
    has_comma = False
    while i < n and depth > 0:
        ch = raw[i]
        if ch == "\\" and i + 1 < n:
            cur.append(ch)
            cur.append(raw[i + 1])
            i += 2
            continue
        if ch == "'":
            end = raw.index("'", i + 1)
            cur.append(raw[i : end + 1])
            i = end + 1
            continue
        if ch == '"':
            end = _scan_double_quoted_end(raw, i)
            cur.append(raw[i:end])
            i = end
            continue
        if ch == "{":
            depth += 1
            cur.append(ch)
        elif ch == "}":
            depth -= 1
            if depth == 0:
                items_text.append("".join(cur))
                # Decide: range vs comma list vs not-a-brace.
                rng = _try_range(items_text)
                if rng is not None:
                    return i + 1, BraceExpansion(line=line, items=[rng])
                if has_comma:
                    items: list[BraceItem] = [
                        BraceWord(parse_word(t, line=line)) for t in items_text
                    ]
                    return i + 1, BraceExpansion(line=line, items=items)
                return start + 1, None  # no comma, no range -> not a brace expansion
            cur.append(ch)
        elif ch == "," and depth == 1:
            items_text.append("".join(cur))
            cur = []
            has_comma = True
        else:
            cur.append(ch)
        i += 1
    return start + 1, None  # unterminated -> treat as literal


def _try_range(items: list[str]) -> BraceItem | None:
    """If a single-item brace looks like ``a..b`` or ``1..10[..step]``, build a range."""
    if len(items) != 1:
        return None
    text = items[0]
    if ".." not in text:
        return None
    parts = text.split("..")
    if len(parts) not in (2, 3):
        return None
    start, end = parts[0], parts[1]
    step = 1
    if len(parts) == 3:
        try:
            step = int(parts[2])
        except ValueError:
            return None
    is_numeric = _is_int(start) and _is_int(end)
    is_alpha = len(start) == 1 and len(end) == 1 and start.isalpha() and end.isalpha()
    if not (is_numeric or is_alpha):
        return None
    return BraceRange(start=start, end=end, step=step, is_numeric=is_numeric)


def _is_int(s: str) -> bool:
    if not s:
        return False
    if s[0] in "+-":
        s = s[1:]
    return s.isdigit()


__all__ = ["WordParseError", "parse_word"]


_ = Script  # silence unused-import for forward ref module-load
