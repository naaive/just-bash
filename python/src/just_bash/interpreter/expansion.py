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
from dataclasses import dataclass
from typing import TYPE_CHECKING

from just_bash.ast.nodes import (
    ArithmeticExpansion,
    AssignDefault,
    BraceExpansion,
    BraceRange,
    BraceWord,
    CaseModification,
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
    ProcessSubstitution,
    SingleQuoted,
    Substring,
    TildeExpansion,
    Transform,
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
    return "".join(p.text for p in pieces)


def expand_pattern(interp: Interpreter, word: Word) -> str:
    """Expand a word that will be used as a pattern (glob, case, ${VAR#pat}).

    Quoted parts contribute literal text (regex-escaped at the call site);
    unquoted parts contribute glob metacharacters that should keep their
    meaning.
    """
    pieces = _expand_to_pieces(interp, word)
    out: list[str] = []
    for p in pieces:
        if p.quoted:
            # Escape glob metacharacters so they're treated literally.
            out.append(_escape_glob(p.text))
        else:
            out.append(p.text)
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


@dataclass(slots=True)
class _Piece:
    """One fragment of a partially-expanded word.

    ``end_field`` is set on the boundary between elements of ``"${arr[@]}"``
    so that word splitting honors the array's existing field boundaries even
    when the whole expansion is inside double quotes.
    """

    text: str
    quoted: bool
    end_field: bool = False


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
        return [_Piece(part.value, force_quoted)]
    if isinstance(part, SingleQuoted):
        return [_Piece(part.value, True)]
    if isinstance(part, Escaped):
        return [_Piece(part.value, True)]
    if isinstance(part, DoubleQuoted):
        pieces: list[_Piece] = []
        for inner in part.parts:
            pieces.extend(_expand_part(interp, inner, force_quoted=True))
        return pieces
    if isinstance(part, ParameterExpansion):
        return _expand_parameter_pieces(interp, part, force_quoted)
    if isinstance(part, CommandSubstitution):
        return [_Piece(_expand_command_sub(interp, part), force_quoted)]
    if isinstance(part, ArithmeticExpansion):
        from just_bash.interpreter.arithmetic import eval_arith

        return [_Piece(str(eval_arith(interp, part.expression)), force_quoted)]
    if isinstance(part, TildeExpansion):
        home = interp.env.get("HOME") if part.user is None else None
        if home is None:
            return [_Piece("~" + (part.user or ""), force_quoted)]
        return [_Piece(home, force_quoted)]
    if isinstance(part, ProcessSubstitution):
        return [_Piece(_expand_process_sub(interp, part), force_quoted)]
    raise InterpreterError(f"unsupported word part: {type(part).__name__}")


def _expand_process_sub(interp: Interpreter, part: ProcessSubstitution) -> str:
    """Materialize a ``<(cmd)`` / ``>(cmd)`` as a unique VFS path."""
    interp.fs.mkdir("/dev/fd", parents=True, exist_ok=True)
    interp._procsub_counter += 1
    path = f"/dev/fd/{interp._procsub_counter}"
    if part.direction == "input":
        # Run the substitution and stash its stdout at ``path``.
        output = interp.run_substitution(part.body)
        interp.fs.write_file(path, output)
        return path
    # ``>(cmd)``: register a deferred sink; we track writes and feed the body
    # command at the end of the surrounding statement.
    interp.fs.write_file(path, b"")
    interp._pending_output_subs.append((path, part.body))
    return path


def _expand_parameter_pieces(
    interp: Interpreter, part: ParameterExpansion, force_quoted: bool
) -> list[_Piece]:
    """Like ``_expand_parameter`` but returns one piece per array field."""
    # ``${!prefix*}`` / ``${!prefix@}`` - list of variable names with prefix.
    if part.name_prefix:
        names = sorted(n for n in interp.env.all_var_names() if n.startswith(part.parameter))
        if part.subscript == "*" and force_quoted:
            ifs = interp.env.get("IFS") or " \t\n"
            sep = ifs[0] if ifs else " "
            return [_Piece(sep.join(names), force_quoted)]
        return [_Piece(n, force_quoted, end_field=True) for n in names]
    # ``${!ref[@]}`` etc. — indirect AT/STAR isn't fully supported; resolve
    # the indirection to a plain reference first.
    if (
        part.indirect
        and not part.array_keys
        and not (part.subscript in ("@", "*") or part.parameter in ("@", "*"))
    ):
        return [_Piece(_expand_parameter(interp, part), force_quoted)]
    is_at_star = part.subscript in ("@", "*") or part.parameter in ("@", "*")
    splat_form = part.subscript if part.subscript in ("@", "*") else part.parameter
    if is_at_star or part.array_keys:
        elements = _read_array_elements(interp, part)
        if part.array_keys and interp.env.get_assoc(part.parameter) is None:
            # Indexed array (or scalar / positional): keys are 0..N-1.
            elements = [str(i) for i in range(len(elements))]
        if isinstance(part.operation, Length):
            return [_Piece(str(len(elements)), force_quoted)]
        if isinstance(part.operation, Substring):
            from just_bash.interpreter.arithmetic import eval_arith

            offset = eval_arith(interp, part.operation.offset)
            # Positional parameters (``$@`` / ``$*``) are 1-indexed in bash:
            # ``${@:2}`` starts at $2. Real arrays remain 0-indexed.
            is_positional = part.parameter in ("@", "*")
            if is_positional and offset >= 1:
                offset -= 1
            elif offset < 0:
                offset = max(len(elements) + offset, 0)
            if part.operation.length is None:
                elements = elements[offset:]
            else:
                length = eval_arith(interp, part.operation.length)
                if length < 0:
                    elements = elements[offset : len(elements) + length]
                else:
                    elements = elements[offset : offset + length]
        if splat_form == "*" and force_quoted:
            ifs = interp.env.get("IFS") or " \t\n"
            sep = ifs[0] if ifs else " "
            return [_Piece(sep.join(elements), force_quoted)]
        # ``$@`` / ``"$@"`` / ``${arr[@]}`` etc. produce one field per element.
        return [_Piece(e, force_quoted, end_field=True) for e in elements]
    return [_Piece(_expand_parameter(interp, part), force_quoted)]


def _read_array_elements(interp: Interpreter, part: ParameterExpansion) -> list[str]:
    name = part.parameter
    if name in ("@", "*"):
        return list(interp.env.positional)
    if name == "PIPESTATUS":
        return [str(s) for s in interp.env.last_pipeline_status]
    if name == "FUNCNAME":
        # Innermost-first list of executing function names. ``bash -c`` does
        # NOT append a synthetic ``main`` frame — only ``bash script.sh``
        # does — and our harness uses ``-c`` so we follow that convention.
        return [n for n, _ in reversed(interp.env.call_stack)]
    if name == "BASH_SOURCE":
        return ["main"] * len(interp.env.call_stack)
    if name == "BASH_LINENO":
        return [str(line) for _, line in reversed(interp.env.call_stack)]
    assoc = interp.env.get_assoc(name)
    if assoc is not None:
        if part.array_keys:
            return list(assoc.keys())
        return list(assoc.values())
    arr = interp.env.get_array(name)
    if arr is not None:
        return list(arr)
    val = interp.env.get(name)
    if val is None:
        return []
    return [val]


def _expand_parameter(interp: Interpreter, part: ParameterExpansion) -> str:
    name = part.parameter
    if part.indirect:
        # ``${!ref}``: read ``$ref`` to get the actual variable name, then
        # read that. Honour the same operator suffix afterwards.
        ref_value = interp.env.get(name) or ""
        name = ref_value.strip()
        if not name:
            return ""
    if part.subscript is not None and part.subscript not in ("@", "*"):
        # Indexed or associative array access: ``${arr[key]}``.
        from just_bash.parser.word_parser import parse_word

        sub_word = parse_word(part.subscript, line=part.line)
        expanded = expand_word_no_split(interp, sub_word)
        assoc = interp.env.get_assoc(name)
        if assoc is not None:
            raw_value: str | None = assoc.get(expanded)
        else:
            from just_bash.interpreter.arithmetic import eval_arith
            from just_bash.parser.arithmetic_parser import parse_arith_text

            idx = eval_arith(interp, parse_arith_text(expanded.strip() or "0"))
            # Synthetic introspection arrays (FUNCNAME / BASH_SOURCE /
            # BASH_LINENO) are read straight off the call stack.
            if name in ("FUNCNAME", "BASH_SOURCE", "BASH_LINENO"):
                synth = _read_array_elements(
                    interp, ParameterExpansion(parameter=name, line=part.line)
                )
                raw_value = synth[idx] if 0 <= idx < len(synth) else None
                # Skip the assoc/array branches below; jump to operator
                # processing (which already handles unset / default / etc.).
                return _apply_param_operator(interp, part, raw_value, name)
            arr = interp.env.get_array(name)
            if arr is None:
                scalar = interp.env.get(name) or ""
                raw_value = scalar if idx == 0 else None
            else:
                raw_value = arr[idx] if 0 <= idx < len(arr) else None
    else:
        raw_value = _read_parameter(interp, name)
    return _apply_param_operator(interp, part, raw_value, name)


def _apply_param_operator(
    interp: Interpreter,
    part: ParameterExpansion,
    raw_value: str | None,
    name: str,
) -> str:
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
    if isinstance(op, CaseModification):
        s = raw_value or ""
        pat: str | None = None
        if op.pattern is not None:
            pat = expand_pattern(interp, op.pattern)
        return _case_modify(s, direction=op.direction, all_chars=op.all_chars, pattern=pat)
    if isinstance(op, Transform):
        return _transform(raw_value or "", op.operator)
    raise InterpreterError(f"unsupported parameter operation: {type(op).__name__}")


def _case_modify(s: str, *, direction: str, all_chars: bool, pattern: str | None) -> str:
    """Apply ``^^`` / ``^`` / ``,,`` / ``,`` case modification.

    With a pattern, only characters that match the pattern (interpreted as a
    one-char fnmatch glob) are folded. The default pattern matches any char.
    """
    if not s:
        return s
    fold = (lambda c: c.upper()) if direction == "upper" else (lambda c: c.lower())
    if pattern is None or pattern in ("", "?"):
        if all_chars:
            return fold(s)
        return fold(s[0]) + s[1:]
    import fnmatch as _fn

    def maybe(c: str) -> str:
        return fold(c) if _fn.fnmatchcase(c, pattern) else c

    if all_chars:
        return "".join(maybe(c) for c in s)
    return maybe(s[0]) + s[1:]


def _transform(s: str, op: str) -> str:
    """Apply ``${VAR@op}`` transformation.

    ``Q`` shell-quotes the value (bash's single-quote style), ``E``
    interprets backslash escapes, ``U``/``L``/``u`` change case,
    ``A`` returns a ``declare`` statement that recreates the variable,
    ``P`` would expand as a PS1-style prompt (degenerate here). Unsupported
    operators return the value unchanged.
    """
    if op == "Q":
        return _bash_quote_q(s)
    if op == "E":
        # ``$'...'``-style escape interpretation.
        out: list[str] = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                nxt = s[i + 1]
                out.append({"n": "\n", "t": "\t", "r": "\r", "\\": "\\", "0": "\0"}.get(nxt, nxt))
                i += 2
                continue
            out.append(ch)
            i += 1
        return "".join(out)
    if op == "U":
        return s.upper()
    if op == "L":
        return s.lower()
    if op == "u":
        return s[:1].upper() + s[1:] if s else s
    if op in ("A", "K", "k", "P", "a"):
        return s
    return s


def _bash_quote_q(s: str) -> str:
    """Match bash's ``${var@Q}`` single-quote style.

    Empty -> ``''``; control chars -> ``$'…'``; otherwise always wraps in
    ``'…'`` with embedded ``'`` escaped as ``'\\''`` (bash always quotes
    even safe identifiers, unlike ``printf %q``).
    """
    if s == "":
        return "''"
    if any(c < " " for c in s):
        out: list[str] = ["$'"]
        for c in s:
            if c == "\n":
                out.append("\\n")
            elif c == "\t":
                out.append("\\t")
            elif c == "\r":
                out.append("\\r")
            elif c == "\\":
                out.append("\\\\")
            elif c == "'":
                out.append("\\'")
            elif c < " ":
                out.append(f"\\x{ord(c):02x}")
            else:
                out.append(c)
        out.append("'")
        return "".join(out)
    return "'" + s.replace("'", "'\\''") + "'"


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
    if name == "FUNCNAME":
        return interp.env.call_stack[-1][0] if interp.env.call_stack else ""
    if name == "BASH_SOURCE":
        return "main" if interp.env.call_stack else ""
    if name == "BASH_LINENO":
        return str(interp.env.call_stack[-1][1]) if interp.env.call_stack else "0"
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
    boundaries, but a piece marked ``end_field`` always closes the current
    field (used for ``"${arr[@]}"`` boundaries).
    """
    if ifs is None:
        ifs = " \t\n"
    if not pieces:
        return [("", False)]
    fields: list[tuple[str, bool]] = []
    current = ""
    had_quoted = False
    for piece in pieces:
        text, quoted = piece.text, piece.quoted
        if quoted and not piece.end_field:
            current += text
            had_quoted = True
            continue
        if piece.end_field:
            # Array-element boundary: emit (text + current) and break field.
            current += text
            had_quoted = had_quoted or quoted
            fields.append((current, had_quoted))
            current = ""
            had_quoted = False
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
        # Bash semantics: unquoted empty expansions produce ZERO fields,
        # but a literal ``""`` (or any quoted piece) keeps one empty field.
        if any(p.quoted for p in pieces):
            return [("", True)]
        return []
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


def _glob_match(value: str, pattern: str) -> bool:
    """Anchored glob match honouring extglob extensions and POSIX char classes."""
    from just_bash.interpreter.extglob import extglob_match

    if "[:" in pattern or (any(c in pattern for c in "@?+*!") and "(" in pattern):
        return extglob_match(value, pattern)
    return fnmatch.fnmatchcase(value, pattern)


def _strip_pattern(s: str, pattern: str, *, side: str, greedy: bool) -> str:
    if not pattern:
        return s
    if side == "prefix":
        if greedy:
            for i in range(len(s), -1, -1):
                if _glob_match(s[:i], pattern):
                    return s[i:]
        else:
            for i in range(len(s) + 1):
                if _glob_match(s[:i], pattern):
                    return s[i:]
        return s
    # suffix
    if greedy:
        for i in range(0, len(s) + 1):
            if _glob_match(s[i:], pattern):
                return s[:i]
    else:
        for i in range(len(s), -1, -1):
            if _glob_match(s[i:], pattern):
                return s[:i]
    return s


def _replace_pattern(
    s: str, pattern: str, replacement: str, *, all_occ: bool, anchor: str | None
) -> str:
    if not pattern:
        return s
    import re

    # Patterns with extglob meta or POSIX char classes route through the
    # extglob translator (which knows about them); plain globs use fnmatch.
    if "[:" in pattern or (any(c in pattern for c in "@?+*!") and "(" in pattern):
        from just_bash.interpreter.extglob import extglob_to_regex

        rx = extglob_to_regex(pattern)
    else:
        rx = fnmatch.translate(pattern)
        # fnmatch.translate produces a regex that matches the entire string;
        # strip the trailing anchor so we can use it for substring matches.
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
