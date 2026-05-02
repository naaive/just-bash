"""Bash lexer.

The lexer produces a flat token stream that the parser consumes. Words keep
their raw text including quotes and dollar expansions; word-internal structure
(``${var}`` / ``$(cmd)`` / ``"..."``) is parsed lazily by ``WordParser`` when
the parser asks for it.

Why split it this way: bash word-splitting rules depend on context (inside
``[[ ]]`` or ``case`` patterns the rules differ). Keeping the lexer dumb about
words and letting the parser drive expansion parsing makes the code easier to
reason about than trying to lex everything eagerly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenKind(Enum):
    WORD = auto()  # raw word text including quotes / expansions
    OPERATOR = auto()  # |, ||, &, &&, ;, ;;, (, ), <, >, >>, <<, <<<, etc.
    NEWLINE = auto()  # \n - statement terminator
    IO_NUMBER = auto()  # leading FD, e.g. 2 in 2>file
    KEYWORD = auto()  # if/then/else/fi/for/while/etc. (resolved by parser)
    EOF = auto()


@dataclass(slots=True)
class Token:
    kind: TokenKind
    text: str
    line: int
    column: int
    # ``heredoc_body`` / delimiter are set on ``<<`` / ``<<-`` operator
    # tokens after the body has been collected by the lexer. This decouples
    # body capture from the parser's token consumption.
    heredoc_delim: str | None = None
    heredoc_body: str | None = None
    heredoc_quoted: bool = False
    heredoc_strip_tabs: bool = False


class LexError(Exception):
    """Raised on unrecoverable lexer errors (unterminated quotes, etc.)."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"line {line}:{column}: {message}")
        self.line = line
        self.column = column


# Two-character operators must be checked before single-character ones.
_TWO_CHAR_OPS = (
    "&&",
    "||",
    ">>",
    "<<",
    ">|",
    "<&",
    ">&",
    "<>",
    ";;",
    "&>",
    "|&",
)
_THREE_CHAR_OPS = ("<<<", "<<-", "&>>", ";;&")
_SINGLE_CHAR_OPS = "|&;()<>"


class Lexer:
    """Hand-written, character-by-character bash lexer.

    Iteration model: ``next_token()`` returns the next token; callers loop
    until ``EOF``. ``peek_token()`` is a one-token lookahead.
    """

    __slots__ = ("_col", "_line", "_peeked", "_pending_heredocs", "_pos", "source")

    def __init__(self, source: str) -> None:
        self.source = source
        self._pos = 0
        self._line = 1
        self._col = 1
        self._peeked: Token | None = None
        # Heredocs that need their body collected after the next newline.
        self._pending_heredocs: list[Token] = []

    # ------------------------------------------------------------------ char IO
    def _eof(self) -> bool:
        return self._pos >= len(self.source)

    def _peek_char(self, offset: int = 0) -> str:
        i = self._pos + offset
        if i >= len(self.source):
            return ""
        return self.source[i]

    def _advance(self) -> str:
        ch = self.source[self._pos]
        self._pos += 1
        if ch == "\n":
            self._line += 1
            self._col = 1
        else:
            self._col += 1
        return ch

    def _starts_with(self, s: str) -> bool:
        return self.source.startswith(s, self._pos)

    # -------------------------------------------------------------- public API
    def peek_token(self) -> Token:
        if self._peeked is None:
            self._peeked = self._read_token()
        return self._peeked

    def next_token(self) -> Token:
        if self._peeked is not None:
            t = self._peeked
            self._peeked = None
            return t
        return self._read_token()

    # ------------------------------------------------------------------ engine
    def _read_token(self) -> Token:
        self._skip_whitespace_and_comments()
        if self._eof():
            return Token(TokenKind.EOF, "", self._line, self._col)

        line, col = self._line, self._col
        ch = self._peek_char()

        if ch == "\n":
            self._advance()
            # If we just finished the line that introduced one or more
            # heredocs, collect their bodies now.
            if self._pending_heredocs:
                self._collect_heredoc_bodies()
            return Token(TokenKind.NEWLINE, "\n", line, col)

        # \\\n is a line continuation: silently consume.
        if ch == "\\" and self._peek_char(1) == "\n":
            self._advance()
            self._advance()
            return self._read_token()

        # ((expr)) - arithmetic command. Capture as a single OPERATOR token so
        # the parser hands the raw text to the arithmetic parser (preserving
        # operators that the lexer doesn't otherwise tokenize, like ``>=``).
        if ch == "(" and self._peek_char(1) == "(":
            return self._read_arith_command_token(line, col)
        # [[ ... ]] - conditional expression keyword. Two-char keyword.
        # Skip when ``[[`` is immediately followed by ``:`` because that's a
        # POSIX char class like ``[[:space:]]`` and belongs in a glob word.
        if ch == "[" and self._peek_char(1) == "[" and self._peek_char(2) != ":":
            self._advance()
            self._advance()
            return Token(TokenKind.WORD, "[[", line, col)
        if ch == "]" and self._peek_char(1) == "]":
            self._advance()
            self._advance()
            return Token(TokenKind.WORD, "]]", line, col)
        # Heredoc: ``<<-DELIM`` and ``<<DELIM``. Must come before generic
        # two-char ops so we capture the delimiter immediately.
        if self._starts_with("<<-") and not self._starts_with("<<<"):
            for _ in "<<-":
                self._advance()
            tok = Token(TokenKind.OPERATOR, "<<-", line, col, heredoc_strip_tabs=True)
            self._read_heredoc_delimiter_into(tok)
            return tok
        if self._starts_with("<<") and not self._starts_with("<<<"):
            self._advance()
            self._advance()
            tok = Token(TokenKind.OPERATOR, "<<", line, col)
            self._read_heredoc_delimiter_into(tok)
            return tok
        # Process substitution: ``<(cmd)`` / ``>(cmd)``. Capture the whole
        # ``<(...)`` as a single WORD token so the word parser can later
        # decode it as a process-substitution part.
        if (ch == "<" or ch == ">") and self._peek_char(1) == "(":
            return self._read_process_sub_token(line, col)
        # Operators (longest match wins).
        for op in _THREE_CHAR_OPS:
            if self._starts_with(op):
                for _ in op:
                    self._advance()
                return Token(TokenKind.OPERATOR, op, line, col)
        for op in _TWO_CHAR_OPS:
            if self._starts_with(op):
                for _ in op:
                    self._advance()
                return Token(TokenKind.OPERATOR, op, line, col)
        if ch in _SINGLE_CHAR_OPS:
            self._advance()
            return Token(TokenKind.OPERATOR, ch, line, col)

        # IO_NUMBER: digits followed by < or > (no intervening whitespace).
        if ch.isdigit():
            j = self._pos
            while j < len(self.source) and self.source[j].isdigit():
                j += 1
            if j < len(self.source) and self.source[j] in "<>":
                num = self.source[self._pos : j]
                for _ in num:
                    self._advance()
                return Token(TokenKind.IO_NUMBER, num, line, col)

        # Word.
        text = self._read_word()
        return Token(TokenKind.WORD, text, line, col)

    def _read_process_sub_token(self, line: int, col: int) -> Token:
        """Capture ``<(cmds)`` or ``>(cmds)`` as a single WORD token.

        Returning a WORD lets the word parser turn it into a
        ``ProcessSubstitution`` node next to other word parts (so things like
        ``cat <(cmd) suffix`` still work).
        """
        direction = self._peek_char()
        self._advance()  # < or >
        body = self._read_balanced("(", ")")
        return Token(TokenKind.WORD, direction + body, line, col)

    # ------------------------------------------------------------- heredocs
    def _read_heredoc_delimiter_into(self, tok: Token) -> None:
        """Read the delimiter that follows ``<<`` / ``<<-`` and queue body capture."""
        # Skip horizontal whitespace, then read one word as the delimiter.
        while not self._eof() and self._peek_char() in (" ", "\t"):
            self._advance()
        if self._eof() or self._peek_char() == "\n":
            raise LexError("missing heredoc delimiter", tok.line, tok.column)
        raw_delim = self._read_word()
        # If any part of the delimiter was quoted, expansions inside the body
        # are suppressed (matches bash semantics).
        quoted = any(ch in raw_delim for ch in ("'", '"', "\\"))
        clean = _strip_quotes(raw_delim)
        tok.heredoc_quoted = quoted
        tok.heredoc_delim = clean
        self._pending_heredocs.append(tok)

    def _collect_heredoc_bodies(self) -> None:
        """Drain ``self._pending_heredocs`` reading their bodies from source."""
        for tok in self._pending_heredocs:
            delim = tok.heredoc_delim or ""
            body_lines: list[str] = []
            while not self._eof():
                line_start = self._pos
                # Read up to the next \n or EOF.
                end = self.source.find("\n", line_start)
                if end == -1:
                    line = self.source[line_start:]
                    self._pos = len(self.source)
                    self._col += len(line)
                    if line.strip("\t" if tok.heredoc_strip_tabs else "") == delim or line == delim:
                        break
                    body_lines.append(line.lstrip("\t") if tok.heredoc_strip_tabs else line)
                    break
                line = self.source[line_start:end]
                check = line.lstrip("\t") if tok.heredoc_strip_tabs else line
                if check == delim:
                    self._pos = end + 1
                    self._line += 1
                    self._col = 1
                    break
                body_lines.append(line.lstrip("\t") if tok.heredoc_strip_tabs else line)
                self._pos = end + 1
                self._line += 1
                self._col = 1
            tok.heredoc_body = "\n".join(body_lines) + ("\n" if body_lines else "")
        self._pending_heredocs = []

    # ----------------------------------------------------------- char-class IO
    def _skip_whitespace_and_comments(self) -> None:
        while not self._eof():
            ch = self._peek_char()
            if ch in (" ", "\t"):
                self._advance()
            elif ch == "#":
                while not self._eof() and self._peek_char() != "\n":
                    self._advance()
            else:
                return

    def _read_word(self) -> str:
        """Read a single word, preserving quotes and ``$...`` expansions verbatim."""
        out: list[str] = []
        while not self._eof():
            ch = self._peek_char()
            if ch in (" ", "\t", "\n"):
                break
            # Extglob ``?( | * | + | @ | ! ) (`` keeps the ``(...)`` body as
            # part of the word; without this the case-pattern parser sees
            # the inner ``(`` as a separator.
            if ch in "?*+@!" and self._peek_char(1) == "(":
                out.append(self._advance())
                out.append(self._read_balanced("(", ")"))
                continue
            if ch in _SINGLE_CHAR_OPS:
                break
            # Backslash escape outside any quote.
            if ch == "\\":
                out.append(self._advance())
                if not self._eof():
                    out.append(self._advance())
                continue
            if ch == "'":
                out.append(self._read_single_quoted())
                continue
            if ch == '"':
                out.append(self._read_double_quoted())
                continue
            if ch == "$":
                out.append(self._read_dollar())
                continue
            if ch == "`":
                out.append(self._read_backtick())
                continue
            out.append(self._advance())
        return "".join(out)

    def _read_single_quoted(self) -> str:
        start_line, start_col = self._line, self._col
        out = [self._advance()]  # opening '
        while not self._eof():
            ch = self._advance()
            out.append(ch)
            if ch == "'":
                return "".join(out)
        raise LexError("unterminated single-quoted string", start_line, start_col)

    def _read_double_quoted(self) -> str:
        start_line, start_col = self._line, self._col
        out = [self._advance()]  # opening "
        while not self._eof():
            ch = self._peek_char()
            if ch == "\\":
                out.append(self._advance())
                if not self._eof():
                    out.append(self._advance())
                continue
            if ch == "$":
                out.append(self._read_dollar())
                continue
            if ch == "`":
                out.append(self._read_backtick())
                continue
            out.append(self._advance())
            if ch == '"':
                return "".join(out)
        raise LexError("unterminated double-quoted string", start_line, start_col)

    def _read_dollar(self) -> str:
        """Read ``$``-introduced expansions including their balanced wrappers."""
        out = [self._advance()]  # $
        if self._eof():
            return "".join(out)
        nxt = self._peek_char()
        if nxt == "'":
            # ``$'...'`` ANSI-C quoted string. We keep the literal ``$'...'``
            # form in the word so ``parse_word`` can decode the escapes.
            out.append(self._advance())
            while not self._eof():
                ch = self._peek_char()
                if ch == "\\" and not self._eof():
                    out.append(self._advance())
                    if not self._eof():
                        out.append(self._advance())
                    continue
                out.append(self._advance())
                if ch == "'":
                    return "".join(out)
            return "".join(out)
        if nxt == '"':
            # ``$"..."`` is locale-translated bash string; we just expand
            # like a normal double-quoted string.
            out.append(self._read_double_quoted())
            return "".join(out)
        if nxt == "{":
            out.append(self._read_balanced("{", "}"))
            return "".join(out)
        if nxt == "(":
            # $(( ... )) vs $( ... )
            if self._peek_char(1) == "(":
                out.append(self._read_double_paren())
                return "".join(out)
            out.append(self._read_balanced("(", ")"))
            return "".join(out)
        # $VAR / $1 / $? - read identifier or special.
        if nxt.isalpha() or nxt == "_":
            while not self._eof() and (self._peek_char().isalnum() or self._peek_char() == "_"):
                out.append(self._advance())
        elif nxt.isdigit() or nxt in "@*#?-$!":
            out.append(self._advance())
        return "".join(out)

    def _read_backtick(self) -> str:
        start_line, start_col = self._line, self._col
        out = [self._advance()]  # opening `
        while not self._eof():
            ch = self._peek_char()
            if ch == "\\":
                out.append(self._advance())
                if not self._eof():
                    out.append(self._advance())
                continue
            out.append(self._advance())
            if ch == "`":
                return "".join(out)
        raise LexError("unterminated backtick command substitution", start_line, start_col)

    def _read_balanced(self, open_ch: str, close_ch: str) -> str:
        """Consume opening and matching close, respecting nested quotes/expansions."""
        start_line, start_col = self._line, self._col
        out = [self._advance()]  # consume opener
        depth = 1
        while not self._eof() and depth > 0:
            ch = self._peek_char()
            if ch == "\\":
                out.append(self._advance())
                if not self._eof():
                    out.append(self._advance())
                continue
            if ch == "'":
                out.append(self._read_single_quoted())
                continue
            if ch == '"':
                out.append(self._read_double_quoted())
                continue
            if ch == "$":
                out.append(self._read_dollar())
                continue
            if ch == "`":
                out.append(self._read_backtick())
                continue
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    out.append(self._advance())
                    return "".join(out)
            out.append(self._advance())
        raise LexError(f"unterminated {open_ch}...{close_ch}", start_line, start_col)

    def _read_arith_command_token(self, line: int, col: int) -> Token:
        """Read ``(( ... ))`` as a single OPERATOR token with the raw body."""
        start_line, start_col = line, col
        self._advance()  # first (
        self._advance()  # second (
        body_start = self._pos
        depth = 1
        while not self._eof() and depth > 0:
            ch = self._peek_char()
            if ch == "\\" and not self._eof():
                self._advance()
                if not self._eof():
                    self._advance()
                continue
            if ch == "'":
                self._read_single_quoted()
                continue
            if ch == '"':
                self._read_double_quoted()
                continue
            if ch == "$":
                self._read_dollar()
                continue
            if ch == "(":
                depth += 1
                self._advance()
                continue
            if ch == ")":
                if depth == 1 and self._peek_char(1) == ")":
                    body = self.source[body_start : self._pos]
                    self._advance()
                    self._advance()
                    return Token(TokenKind.OPERATOR, f"(({body}))", start_line, start_col)
                depth -= 1
                self._advance()
                continue
            self._advance()
        raise LexError("unterminated (( ... ))", start_line, start_col)

    def _read_double_paren(self) -> str:
        """Read ``(( ... ))`` for ``$((...))`` arithmetic expansion."""
        start_line, start_col = self._line, self._col
        out = [self._advance(), self._advance()]  # ((
        depth = 1
        while not self._eof() and depth > 0:
            ch = self._peek_char()
            if ch == "\\":
                out.append(self._advance())
                if not self._eof():
                    out.append(self._advance())
                continue
            if ch == "'":
                out.append(self._read_single_quoted())
                continue
            if ch == '"':
                out.append(self._read_double_quoted())
                continue
            if ch == "$":
                out.append(self._read_dollar())
                continue
            if ch == "(":
                depth += 1
                out.append(self._advance())
                continue
            if ch == ")":
                # )) closes; lone ) is a nested group.
                if self._peek_char(1) == ")" and depth == 1:
                    out.append(self._advance())
                    out.append(self._advance())
                    return "".join(out)
                depth -= 1
                out.append(self._advance())
                continue
            out.append(self._advance())
        raise LexError("unterminated $((...))", start_line, start_col)


def tokenize(source: str) -> list[Token]:
    """Eagerly tokenize a whole script. Useful for tests and debugging."""
    lex = Lexer(source)
    out: list[Token] = []
    while True:
        tok = lex.next_token()
        out.append(tok)
        if tok.kind is TokenKind.EOF:
            return out


def _strip_quotes(text: str) -> str:
    """Remove enclosing quotes / backslashes from a heredoc delimiter word."""
    out: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            out.append(text[i + 1])
            i += 2
            continue
        if ch in ("'", '"'):
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)
