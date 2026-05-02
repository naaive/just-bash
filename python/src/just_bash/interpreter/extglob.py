"""Translate bash glob + extglob patterns into Python regex.

Supported features:
  - Basic globs: ``*`` ``?`` ``[abc]`` ``[!abc]``
  - Extended globs (always on; bash gates these on ``shopt -s extglob`` but
    enabling them unconditionally is a strict superset):
      - ``?(p1|p2|...)`` zero or one occurrence of any alternative
      - ``*(p1|p2|...)`` zero or more occurrences
      - ``+(p1|p2|...)`` one or more occurrences
      - ``@(p1|p2|...)`` exactly one occurrence
      - ``!(p1|p2|...)`` anything except those alternatives
"""

from __future__ import annotations

import re


def extglob_to_regex(pattern: str) -> str:
    """Translate ``pattern`` (with extglob) to an anchored Python regex."""
    return _convert(pattern)


def extglob_match(value: str, pattern: str) -> bool:
    """Anchored match of ``pattern`` against ``value`` honouring extglob."""
    try:
        rx = re.compile("\\A" + _convert(pattern) + "\\Z", re.DOTALL)
    except re.error:
        return False
    return rx.match(value) is not None


def _convert(pattern: str) -> str:
    parser = _Parser(pattern)
    return parser.parse()


class _Parser:
    __slots__ = ("pos", "text")

    def __init__(self, text: str) -> None:
        self.text = text
        self.pos = 0

    def parse(self) -> str:
        return self._sequence(stop="")

    def _sequence(self, stop: str) -> str:
        out: list[str] = []
        while self.pos < len(self.text):
            ch = self.text[self.pos]
            if stop and ch in stop:
                return "".join(out)
            if ch == "\\" and self.pos + 1 < len(self.text):
                out.append(re.escape(self.text[self.pos + 1]))
                self.pos += 2
                continue
            if ch == "*":
                if self._is_extglob_open():
                    out.append(self._extglob("*"))
                    continue
                out.append(".*")
                self.pos += 1
                continue
            if ch == "?":
                if self._is_extglob_open():
                    out.append(self._extglob("?"))
                    continue
                out.append(".")
                self.pos += 1
                continue
            if ch in ("@", "+", "!") and self._is_extglob_open():
                out.append(self._extglob(ch))
                continue
            if ch == "[":
                out.append(self._char_class())
                continue
            out.append(re.escape(ch))
            self.pos += 1
        return "".join(out)

    def _is_extglob_open(self) -> bool:
        return self.pos + 1 < len(self.text) and self.text[self.pos + 1] == "("

    def _char_class(self) -> str:
        start = self.pos
        self.pos += 1  # consume [
        body: list[str] = ["["]
        if self.pos < len(self.text) and self.text[self.pos] in ("!", "^"):
            # Both ``!`` and ``^`` negate the class in bash globs.
            body.append("^")
            self.pos += 1
        while self.pos < len(self.text) and self.text[self.pos] != "]":
            ch = self.text[self.pos]
            if ch == "\\" and self.pos + 1 < len(self.text):
                body.append(re.escape(self.text[self.pos + 1]))
                self.pos += 2
                continue
            # POSIX character class [:NAME:] — translate to a Python equivalent.
            if ch == "[" and self.pos + 1 < len(self.text) and self.text[self.pos + 1] == ":":
                end = self.text.find(":]", self.pos + 2)
                if end != -1:
                    name = self.text[self.pos + 2 : end]
                    body.append(_POSIX_CLASSES.get(name, ""))
                    self.pos = end + 2
                    continue
            if ch in ("\\", "]"):
                body.append("\\" + ch)
            else:
                body.append(ch)
            self.pos += 1
        if self.pos >= len(self.text):
            # Unterminated bracket - treat the whole thing as literal.
            self.pos = start
            self.pos += 1
            return re.escape("[")
        body.append("]")
        self.pos += 1  # consume ]
        return "".join(body)

    def _extglob(self, op: str) -> str:
        """Parse one of ``?( | * | + | @ | ! )(alts)``."""
        # ``op`` consumed at the front, ``(`` immediately after.
        self.pos += 2  # skip ``op(``
        alts = self._collect_alts()
        # ``alts`` was terminated by ``)`` which we already consumed.
        body = "|".join(alts)
        if op == "?":
            return f"(?:{body})?"
        if op == "*":
            return f"(?:{body})*"
        if op == "+":
            return f"(?:{body})+"
        if op == "@":
            return f"(?:{body})"
        if op == "!":
            # Negated: anything that doesn't match the alternatives. We use
            # a negative lookahead anchored at this position; the rest of
            # the pattern continues after.
            return f"(?:(?!(?:{body})).)*"
        raise ValueError(op)

    def _collect_alts(self) -> list[str]:
        alts: list[list[str]] = [[]]
        depth = 1
        while self.pos < len(self.text) and depth > 0:
            ch = self.text[self.pos]
            if ch == "(":
                depth += 1
                alts[-1].append(re.escape(ch))
                self.pos += 1
                continue
            if ch == ")":
                depth -= 1
                if depth == 0:
                    self.pos += 1
                    break
                alts[-1].append(re.escape(ch))
                self.pos += 1
                continue
            if ch == "|" and depth == 1:
                alts.append([])
                self.pos += 1
                continue
            # Recurse via a fresh parser positioned at this offset, capped
            # at ``)`` and ``|``.
            saved = self.pos
            sub = _Parser(self.text)
            sub.pos = self.pos
            inner = sub._sequence(stop="|)")
            if sub.pos == saved:
                # Avoid infinite loop on unconsumed character.
                alts[-1].append(re.escape(ch))
                self.pos += 1
            else:
                alts[-1].append(inner)
                self.pos = sub.pos
        return ["".join(a) for a in alts]


# POSIX character-class names mapped to ASCII char ranges suitable for
# inclusion inside a Python ``[...]`` set.
_POSIX_CLASSES: dict[str, str] = {
    "alpha": "a-zA-Z",
    "alnum": "a-zA-Z0-9",
    "digit": "0-9",
    "lower": "a-z",
    "upper": "A-Z",
    "space": " \\t\\n\\r\\f\\v",
    "blank": " \\t",
    "xdigit": "0-9a-fA-F",
    "cntrl": "\\x00-\\x1f\\x7f",
    "print": "\\x20-\\x7e",
    "graph": "\\x21-\\x7e",
    "punct": "!-/:-@\\[-`{-~",
    "ascii": "\\x00-\\x7f",
    "word": "a-zA-Z0-9_",
}


__all__ = ["extglob_match", "extglob_to_regex"]
