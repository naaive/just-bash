"""Word expansion.

Implements the bash word-expansion pipeline:
  1. Brace expansion           (``{a,b,c}``)
  2. Tilde expansion           (``~``)
  3. Parameter / variable      (``$VAR``, ``${VAR:-d}``)
  4. Command substitution      (``$(cmd)``)
  5. Arithmetic expansion      (``$(( ... ))``)
  6. Word splitting on ``$IFS``
  7. Pathname (glob) expansion (``*.txt``)
  8. Quote removal

The interpreter calls ``expand_word`` for arguments and ``expand_word_no_split``
for assignments / patterns / heredocs.
"""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING

from just_bash.ast.nodes import (
    ArithmeticExpansion,
    AssignDefault,
    BraceExpansion,
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
    PatternRemoval,
    PatternReplacement,
    SingleQuoted,
    Substring,
    TildeExpansion,
    UseAlternative,
    Word,
    WordPart,
)
from just_bash.interpreter.errors import InterpreterError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import Interpreter


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------


def expand_word(interp: Interpreter, word: Word) -> list[str]:
    """Full expansion pipeline producing zero, one, or many strings."""
    # Step 1: brace expansion runs on the whole word at once.
    after_brace = _brace_expand(word)
    out: list[str] = []
    for w in after_brace:
        # Steps 2-5: produce a "structured string" (list of (text, quoted) pieces).
        pieces = _expand_to_pieces(interp, w)
        # Step 6: word-split unquoted pieces on $IFS.
        split = _word_split(pieces, interp.env.get("IFS"))
        # Step 7: glob each split, unless any part of that field was quoted.
        for raw, had_quoted in split:
            if had_quoted:
                out.append(raw)
                continue
            globbed = _glob(interp, raw)
            out.extend(globbed if globbed else [raw])
    return out


def expand_word_no_split(interp: Interpreter, word: Word) -> str:
    """Expand a word as if it were inside double quotes - no word split / no glob."""
    pieces = _expand_to_pieces(interp, word, force_quoted=True)
    return "".join(text for text, _ in pieces)


def expand_pattern(interp: Interpreter, word: Word) -> str:
    """Expand a word that will be used as a pattern (glob, case, ${VAR#pat}).

    Quoted parts contribute literal text (regex-escaped at the call site);
    unquoted parts contribute glob metacharacters that should keep their
    meaning.
    """
    pieces = _expand_to_pieces(interp, word)
    out: list[str] = []
    for text, quoted in pieces:
        if quoted:
            # Escape glob metacharacters so they're treated literally.
            out.append(_escape_glob(text))
        else:
            out.append(text)
    return "".join(out)


# ---------------------------------------------------------------------------
# Brace expansion
# ---------------------------------------------------------------------------


def _brace_expand(word: Word) -> list[Word]:
    """Cartesian product over any ``BraceExpansion`` parts in the word."""
    chunks: list[list[list[WordPart]]] = [[[]]]
    for part in word.parts:
        if isinstance(part, BraceExpansion):
            options: list[list[WordPart]] = []
            for item in part.items:
                if isinstance(item, BraceWord):
                    options.append(item.word.parts)
                else:  # BraceRange
                    options.extend([[Literal(value=v)] for v in _materialize_range(item)])
            new_chunks: list[list[list[WordPart]]] = []
            for current in chunks:
                for option in options:
                    new_chunks.append([*current, option])
            chunks = new_chunks
        else:
            for current in chunks:
                current.append([part])
    return [Word(parts=[p for group in c for p in group]) for c in chunks]


def _materialize_range(r: BraceRange) -> list[str]:
    if r.is_numeric:
        start = int(r.start)
        end = int(r.end)
        step = abs(r.step) if r.step else 1
        if start <= end:
            seq = list(range(start, end + 1, step))
        else:
            seq = list(range(start, end - 1, -step))
        # Zero-pad if any input was zero-padded.
        width = max(len(r.start.lstrip("-+")), len(r.end.lstrip("-+")))
        pad = (r.start.startswith("0") and len(r.start) > 1) or (
            r.end.startswith("0") and len(r.end) > 1
        )
        return [_pad(n, width) if pad else str(n) for n in seq]
    # Single-character alphabetic range.
    a, b = ord(r.start), ord(r.end)
    step = abs(r.step) if r.step else 1
    if a <= b:
        return [chr(c) for c in range(a, b + 1, step)]
    return [chr(c) for c in range(a, b - 1, -step)]


def _pad(n: int, width: int) -> str:
    sign = "-" if n < 0 else ""
    return f"{sign}{abs(n):0{width if not sign else max(width - 1, 1)}d}"


# ---------------------------------------------------------------------------
# Expansion to (text, quoted) pieces
# ---------------------------------------------------------------------------


_Piece = tuple[str, bool]  # (text, quoted)


def _expand_to_pieces(
    interp: Interpreter,
    word: Word,
    *,
    force_quoted: bool = False,
) -> list[_Piece]:
    out: list[_Piece] = []
    for part in word.parts:
        out.extend(_expand_part(interp, part, force_quoted=force_quoted))
    return out


def _expand_part(interp: Interpreter, part: WordPart, *, force_quoted: bool) -> list[_Piece]:
    if isinstance(part, Literal):
        return [(part.value, force_quoted)]
    if isinstance(part, SingleQuoted):
        return [(part.value, True)]
    if isinstance(part, Escaped):
        return [(part.value, True)]
    if isinstance(part, DoubleQuoted):
        pieces: list[_Piece] = []
        for inner in part.parts:
            pieces.extend(_expand_part(interp, inner, force_quoted=True))
        return pieces
    if isinstance(part, ParameterExpansion):
        return [(_expand_parameter(interp, part), force_quoted)]
    if isinstance(part, CommandSubstitution):
        return [(_expand_command_sub(interp, part), force_quoted)]
    if isinstance(part, ArithmeticExpansion):
        from just_bash.interpreter.arithmetic import eval_arith

        return [(str(eval_arith(interp, part.expression)), force_quoted)]
    if isinstance(part, TildeExpansion):
        home = interp.env.get("HOME") if part.user is None else None
        if home is None:
            return [("~" + (part.user or ""), force_quoted)]
        return [(home, force_quoted)]
    raise InterpreterError(f"unsupported word part: {type(part).__name__}")


def _expand_parameter(interp: Interpreter, part: ParameterExpansion) -> str:
    name = part.parameter
    raw_value = _read_parameter(interp, name)
    op = part.operation
    if op is None:
        return raw_value or ""
    if isinstance(op, Length):
        return str(len(raw_value or ""))
    is_unset = raw_value is None
    is_empty_or_unset = is_unset or raw_value == ""
    if isinstance(op, DefaultValue):
        if (op.check_empty and is_empty_or_unset) or (not op.check_empty and is_unset):
            return expand_word_no_split(interp, op.word)
        return raw_value or ""
    if isinstance(op, AssignDefault):
        if (op.check_empty and is_empty_or_unset) or (not op.check_empty and is_unset):
            new_val = expand_word_no_split(interp, op.word)
            interp.env.set_var(name, new_val)
            return new_val
        return raw_value or ""
    if isinstance(op, ErrorIfUnset):
        if (op.check_empty and is_empty_or_unset) or (not op.check_empty and is_unset):
            msg = (
                expand_word_no_split(interp, op.word)
                if op.word
                else f"{name}: parameter null or not set"
            )
            raise InterpreterError(f"{name}: {msg}")
        return raw_value or ""
    if isinstance(op, UseAlternative):
        if (op.check_empty and is_empty_or_unset) or (not op.check_empty and is_unset):
            return ""
        return expand_word_no_split(interp, op.word)
    if isinstance(op, Substring):
        from just_bash.interpreter.arithmetic import eval_arith

        s = raw_value or ""
        offset = eval_arith(interp, op.offset)
        if offset < 0:
            offset = max(len(s) + offset, 0)
        if op.length is None:
            return s[offset:]
        length = eval_arith(interp, op.length)
        if length < 0:
            return s[offset : len(s) + length]
        return s[offset : offset + length]
    if isinstance(op, PatternRemoval):
        s = raw_value or ""
        pattern = expand_pattern(interp, op.pattern)
        return _strip_pattern(s, pattern, side=op.side, greedy=op.greedy)
    if isinstance(op, PatternReplacement):
        s = raw_value or ""
        pattern = expand_pattern(interp, op.pattern)
        replacement = (
            expand_word_no_split(interp, op.replacement) if op.replacement is not None else ""
        )
        return _replace_pattern(
            s, pattern, replacement, all_occ=op.all_occurrences, anchor=op.anchor
        )
    raise InterpreterError(f"unsupported parameter operation: {type(op).__name__}")


def _read_parameter(interp: Interpreter, name: str) -> str | None:
    """Resolve a parameter name to its current value (or ``None`` if unset)."""
    if name == "?":
        return str(interp.env.last_exit)
    if name == "#":
        return str(len(interp.env.positional))
    if name == "@" or name == "*":
        return " ".join(interp.env.positional)
    if name == "$":
        return "0"  # we don't have a real PID
    if name == "0":
        return interp.env.script_name
    if name.isdigit():
        idx = int(name) - 1
        if 0 <= idx < len(interp.env.positional):
            return interp.env.positional[idx]
        return None
    if name == "-":
        return "".join(sorted(interp.env.shell_options))
    return interp.env.get(name)


def _expand_command_sub(interp: Interpreter, part: CommandSubstitution) -> str:
    """Run ``$(...)`` and capture stdout, stripping a single trailing newline."""
    output = interp.run_substitution(part.body)
    return output.rstrip("\n")


# ---------------------------------------------------------------------------
# Word splitting
# ---------------------------------------------------------------------------


def _word_split(pieces: list[_Piece], ifs: str | None) -> list[tuple[str, bool]]:
    """Split an unquoted ``$IFS`` run into separate fields.

    Returns a list of ``(field_text, had_quoted_part)`` pairs. Quoted pieces
    contribute their full text and never start a new field on their own
    boundaries.
    """
    if ifs is None:
        ifs = " \t\n"
    if not pieces:
        return [("", False)]
    fields: list[tuple[str, bool]] = []
    current = ""
    had_quoted = False
    for text, quoted in pieces:
        if quoted:
            current += text
            had_quoted = True
            continue
        # Walk text char-by-char looking for IFS chars.
        i = 0
        while i < len(text):
            ch = text[i]
            if ch in ifs:
                # End current field if non-empty.
                if current or had_quoted:
                    fields.append((current, had_quoted))
                    current = ""
                    had_quoted = False
                # Skip whitespace IFS run.
                if ch in " \t\n":
                    while i < len(text) and text[i] in " \t\n":
                        i += 1
                    continue
                i += 1
                continue
            current += ch
            i += 1
    if current or had_quoted:
        fields.append((current, had_quoted))
    if not fields:
        return [("", True)]  # quoted-empty stays as one empty field
    return fields


# ---------------------------------------------------------------------------
# Glob
# ---------------------------------------------------------------------------


def _glob(interp: Interpreter, pattern: str) -> list[str]:
    if not _has_glob_meta(pattern):
        return []
    return interp.fs.glob(pattern)


def _has_glob_meta(pattern: str) -> bool:
    in_bracket = False
    for ch in pattern:
        if ch == "[":
            in_bracket = True
        elif ch == "]":
            if in_bracket:
                return True
            in_bracket = False
        elif not in_bracket and ch in ("*", "?"):
            return True
    return False


def _escape_glob(text: str) -> str:
    return "".join("[" + ch + "]" if ch in "*?[" else ch for ch in text)


# ---------------------------------------------------------------------------
# Pattern matching for ${VAR#p} / ${VAR%p}
# ---------------------------------------------------------------------------


def _strip_pattern(s: str, pattern: str, *, side: str, greedy: bool) -> str:
    if not pattern:
        return s
    if side == "prefix":
        if greedy:
            for i in range(len(s), -1, -1):
                if fnmatch.fnmatchcase(s[:i], pattern):
                    return s[i:]
        else:
            for i in range(len(s) + 1):
                if fnmatch.fnmatchcase(s[:i], pattern):
                    return s[i:]
        return s
    # suffix
    if greedy:
        for i in range(0, len(s) + 1):
            if fnmatch.fnmatchcase(s[i:], pattern):
                return s[:i]
    else:
        for i in range(len(s), -1, -1):
            if fnmatch.fnmatchcase(s[i:], pattern):
                return s[:i]
    return s


def _replace_pattern(
    s: str, pattern: str, replacement: str, *, all_occ: bool, anchor: str | None
) -> str:
    if not pattern:
        return s
    import re

    rx = fnmatch.translate(pattern)
    # fnmatch.translate produces a regex that matches the entire string. We
    # want to use it as a substring/anchored pattern instead.
    rx = _strip_translate_anchors(rx)
    if anchor == "start":
        rx = "^" + rx
    elif anchor == "end":
        rx = rx + "$"
    try:
        compiled = re.compile(rx, re.DOTALL)
    except re.error:
        return s
    return compiled.sub(replacement, s, count=0 if all_occ else 1)


def _strip_translate_anchors(rx: str) -> str:
    # ``fnmatch.translate`` outputs ``(?s:...)\Z``; turn it into ``...``.
    if rx.startswith("(?s:") and rx.endswith(r")\Z"):
        return rx[4:-3]
    if rx.endswith(r"\Z"):
        return rx[:-2]
    return rx


__all__ = [
    "expand_pattern",
    "expand_word",
    "expand_word_no_split",
]
