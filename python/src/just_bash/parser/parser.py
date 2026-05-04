"""Bash recursive-descent parser.

Produces a ``Script`` AST. The grammar tracked here is the practical subset of
bash that the MVP interpreter handles - simple commands, pipelines, ``&&``
``||`` ``;`` chains, redirections, ``if`` / ``for`` / ``while`` / ``until`` /
``case``, command groups, subshells, function definitions, ``[[ ]]`` and
``(( ))`` compound commands.
"""

from __future__ import annotations

from typing import cast

from just_bash.ast.nodes import (
    Arithmetic,
    ArithmeticCommand,
    Assignment,
    Case,
    CaseItem,
    Command,
    CompoundCommand,
    CondAnd,
    CondBinary,
    Conditional,
    ConditionalCommand,
    CondNot,
    CondOr,
    CondUnary,
    For,
    FunctionDef,
    Group,
    HereDoc,
    If,
    IfClause,
    Pipeline,
    Redirection,
    Script,
    SimpleCommand,
    Statement,
    Subshell,
    Until,
    While,
    Word,
)
from just_bash.ast.nodes import (
    Literal as _LiteralNode,
)
from just_bash.parser.arithmetic_parser import parse_arith_text
from just_bash.parser.lexer import Lexer, Token, TokenKind
from just_bash.parser.word_parser import parse_word


class ParseError(Exception):
    def __init__(self, message: str, token: Token | None = None) -> None:
        if token is not None:
            message = f"line {token.line}:{token.column}: {message} (got {token.text!r})"
        super().__init__(message)
        self.token = token


_RESERVED_WORDS = frozenset(
    {
        "if",
        "then",
        "elif",
        "else",
        "fi",
        "for",
        "in",
        "do",
        "done",
        "while",
        "until",
        "case",
        "esac",
        "function",
        "select",
        "time",
        "{",
        "}",
        "!",
        "[[",
        "]]",
    }
)
_TERMINATORS = frozenset({";", "\n", "&"})

# Commands whose ``NAME=...`` arguments are part of an assignment context.
# Mirrors ``Interpreter._ASSIGN_CONTEXT_CMDS`` — kept in the parser so we can
# recognise ``declare -A m=([k]=v ...)`` compound initialisers.
_ASSIGN_CONTEXT_NAMES = frozenset({"declare", "typeset", "local", "export", "readonly"})
_BINARY_COND_OPS = frozenset(
    {"=", "==", "!=", "=~", "<", ">", "-eq", "-ne", "-lt", "-le", "-gt", "-ge", "-nt", "-ot", "-ef"}
)
_UNARY_COND_OPS = frozenset(
    {
        "-a",
        "-b",
        "-c",
        "-d",
        "-e",
        "-f",
        "-g",
        "-h",
        "-k",
        "-p",
        "-r",
        "-s",
        "-t",
        "-u",
        "-w",
        "-x",
        "-G",
        "-L",
        "-N",
        "-O",
        "-S",
        "-z",
        "-n",
        "-v",
        "-R",
    }
)


class Parser:
    """Token-driven parser that builds AST nodes."""

    __slots__ = ("_heredocs", "_lookahead", "lexer")

    def __init__(self, source: str) -> None:
        self.lexer = Lexer(source)
        self._lookahead: list[Token] = []
        self._heredocs: list[tuple[HereDoc, bool]] = []  # pending heredocs (unused in MVP)

    # ----------------------------------------------------------- token helpers
    def _peek(self, offset: int = 0) -> Token:
        while len(self._lookahead) <= offset:
            self._lookahead.append(self.lexer.next_token())
        return self._lookahead[offset]

    def _next(self) -> Token:
        if self._lookahead:
            return self._lookahead.pop(0)
        return self.lexer.next_token()

    def _consume(self, kind: TokenKind, text: str | None = None) -> Token:
        tok = self._next()
        if tok.kind is not kind:
            raise ParseError(f"expected {kind.name}", tok)
        if text is not None and tok.text != text:
            raise ParseError(f"expected {text!r}", tok)
        return tok

    def _at_eof(self) -> bool:
        return self._peek().kind is TokenKind.EOF

    def _skip_newlines(self) -> None:
        while self._peek().kind is TokenKind.NEWLINE:
            self._next()

    def _is_reserved(self, tok: Token, *words: str) -> bool:
        return tok.kind is TokenKind.WORD and tok.text in words

    def _drain_to_newline_for_heredoc(self) -> None:
        """Force the lexer past the next NEWLINE so a heredoc body collects.

        Heredoc bodies are gathered inside the lexer when it reads a NEWLINE.
        Until that newline is read, ``op_tok.heredoc_body`` stays ``None``.
        """
        offset = 0
        while True:
            tok = self._peek(offset)
            if tok.kind is TokenKind.NEWLINE or tok.kind is TokenKind.EOF:
                return
            offset += 1

    # ----------------------------------------------------------------- entry
    def parse(self) -> Script:
        statements: list[Statement] = []
        self._skip_newlines()
        while not self._at_eof():
            stmt = self._parse_statement()
            if stmt is not None:
                statements.append(stmt)
            self._skip_newlines()
        return Script(statements=statements)

    # -------------------------------------------------------------- statements
    def _parse_statement(self) -> Statement | None:
        first = self._parse_pipeline()
        if first is None:
            return None
        pipelines = [first]
        operators: list[str] = []
        background = False
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.OPERATOR and tok.text in ("&&", "||"):
                self._next()
                self._skip_newlines()
                nxt = self._parse_pipeline()
                if nxt is None:
                    raise ParseError("expected command after && or ||", tok)
                operators.append(tok.text)
                pipelines.append(nxt)
                continue
            if tok.kind is TokenKind.OPERATOR and tok.text == ";":
                self._next()
                # Trailing ; is fine; if more commands follow on the same logical line, keep going.
                if self._is_command_start():
                    operators.append(";")
                    nxt = self._parse_pipeline()
                    if nxt is None:
                        break
                    pipelines.append(nxt)
                    continue
                break
            if tok.kind is TokenKind.OPERATOR and tok.text == "&":
                self._next()
                background = True
                break
            break
        return Statement(
            pipelines=pipelines,
            operators=cast("list[str]", operators),  # type: ignore[arg-type]
            background=background,
            line=first.line,
        )

    def _is_command_start(self) -> bool:
        tok = self._peek()
        if tok.kind is TokenKind.EOF:
            return False
        if tok.kind is TokenKind.NEWLINE:
            return False
        if tok.kind is TokenKind.OPERATOR and tok.text in {
            ")",
            "}",
            ";",
            "&",
            "&&",
            "||",
            "|",
            ";;",
        }:
            return False
        return not (
            tok.kind is TokenKind.WORD
            and tok.text in {"then", "else", "elif", "fi", "do", "done", "esac", "}"}
        )

    # ---------------------------------------------------------------- pipeline
    def _parse_pipeline(self) -> Pipeline | None:
        self._skip_newlines()
        if not self._is_command_start():
            return None
        negated = False
        tok = self._peek()
        if tok.kind is TokenKind.WORD and tok.text == "!":
            self._next()
            negated = True
            self._skip_newlines()
        cmd = self._parse_command()
        if cmd is None:
            raise ParseError("expected command", self._peek())
        commands: list[Command] = [cmd]
        pipe_stderr: list[bool] = []
        while True:
            t = self._peek()
            if t.kind is TokenKind.OPERATOR and t.text == "|":
                self._next()
                pipe_stderr.append(False)
                self._skip_newlines()
                nxt = self._parse_command()
                if nxt is None:
                    raise ParseError("expected command after |", t)
                commands.append(nxt)
                continue
            if t.kind is TokenKind.OPERATOR and t.text == "|&":
                self._next()
                pipe_stderr.append(True)
                self._skip_newlines()
                nxt = self._parse_command()
                if nxt is None:
                    raise ParseError("expected command after |&", t)
                commands.append(nxt)
                continue
            break
        return Pipeline(
            commands=commands,
            negated=negated,
            pipe_stderr=pipe_stderr,
            line=cmd.line if hasattr(cmd, "line") else 0,
        )

    # ----------------------------------------------------------------- commands
    def _parse_command(self) -> Command | None:
        tok = self._peek()
        if tok.kind is TokenKind.WORD:
            if tok.text == "if":
                return self._parse_if()
            if tok.text == "for":
                return self._parse_for()
            if tok.text == "while":
                return self._parse_while()
            if tok.text == "until":
                return self._parse_until()
            if tok.text == "case":
                return self._parse_case()
            if tok.text == "select":
                # ``select`` is a non-interactive iteration in our sandbox: we
                # parse its body but execute it as if the user picked nothing
                # (the ``in`` words become a one-pass loop body so post-loop
                # state is consistent with bash's "user pressed Ctrl-D"
                # behaviour).
                return self._parse_select()
            if tok.text == "function":
                return self._parse_function_keyword()
            if tok.text == "{":
                return self._parse_group()
            if tok.text == "[[":
                return self._parse_conditional_command()
        if tok.kind is TokenKind.OPERATOR and tok.text == "(":
            return self._parse_subshell()
        if tok.kind is TokenKind.OPERATOR and tok.text.startswith("((") and tok.text.endswith("))"):
            return self._parse_arith_command_token()
        # Function definition: name() { ... }. The name must be a plain
        # identifier - tokens like ``arr=`` (assignment-prefix) or ``arr+=``
        # are NOT function definitions even though the lexer also follows
        # them with a ``(`` (in ``arr=()`` array literal form).
        if (
            tok.kind is TokenKind.WORD
            and tok.text
            and (tok.text[0].isalpha() or tok.text[0] == "_")
            and all(c.isalnum() or c == "_" for c in tok.text)
            and self._peek(1).kind is TokenKind.OPERATOR
            and self._peek(1).text == "("
            and self._peek(2).kind is TokenKind.OPERATOR
            and self._peek(2).text == ")"
        ):
            return self._parse_function_paren()
        return self._parse_simple_command()

    # ------------------------------------------------- simple command + assigns
    def _parse_simple_command(self) -> SimpleCommand | None:
        line = self._peek().line
        assignments: list[Assignment] = []
        # Leading assignments.
        while True:
            tok = self._peek()
            if tok.kind is not TokenKind.WORD:
                break
            assn = _try_parse_assignment(tok)
            if assn is None:
                break
            self._next()
            # Array form: assignment text ends in ``=`` (or ``+=``) and the
            # next token is ``(``. Read words until the matching ``)``.
            if (
                assn.value is None
                and assn.array is None
                and (tok.text.endswith("=") or tok.text.endswith("+="))
                and self._peek().kind is TokenKind.OPERATOR
                and self._peek().text == "("
            ):
                self._next()  # consume "("
                arr_words: list[Word] = []
                while True:
                    nxt = self._peek()
                    if nxt.kind is TokenKind.OPERATOR and nxt.text == ")":
                        self._next()
                        break
                    if nxt.kind is TokenKind.NEWLINE:
                        self._next()
                        continue
                    if nxt.kind is TokenKind.EOF:
                        raise ParseError("unterminated array literal", nxt)
                    if nxt.kind is TokenKind.WORD:
                        arr_words.append(parse_word(nxt.text, line=nxt.line))
                        self._next()
                        continue
                    raise ParseError("unexpected token in array literal", nxt)
                assn.array = arr_words
            assignments.append(assn)
        # Command name.
        name: Word | None = None
        args: list[Word] = []
        redirections: list[Redirection] = []
        first_word = True
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.IO_NUMBER or (
                tok.kind is TokenKind.OPERATOR
                and tok.text
                in {"<", ">", ">>", ">|", "<>", "<<<", "<<", "<<-", "&>", "&>>", ">&", "<&"}
            ):
                redirections.append(self._parse_redirection())
                continue
            if tok.kind is TokenKind.WORD:
                w = parse_word(tok.text, line=tok.line)
                self._next()
                if first_word and name is None:
                    name = w
                else:
                    # ``declare -A NAME=(elem ...)`` — when we're in an
                    # assignment-context command and an arg ends with ``=``
                    # or ``+=`` immediately followed by ``(``, gather the
                    # compound array literal back into a single arg string
                    # so the builtin can re-parse it.
                    if (
                        name is not None
                        and len(name.parts) == 1
                        and isinstance(name.parts[0], _LiteralNode)
                        and name.parts[0].value in _ASSIGN_CONTEXT_NAMES
                        and (tok.text.endswith("=") or tok.text.endswith("+="))
                        and self._peek().kind is TokenKind.OPERATOR
                        and self._peek().text == "("
                    ):
                        self._next()  # consume "("
                        words: list[str] = [tok.text, "("]
                        while True:
                            nxt = self._peek()
                            if nxt.kind is TokenKind.OPERATOR and nxt.text == ")":
                                self._next()
                                words.append(")")
                                break
                            if nxt.kind is TokenKind.NEWLINE:
                                self._next()
                                continue
                            if nxt.kind is TokenKind.EOF:
                                raise ParseError("unterminated compound array literal", nxt)
                            if nxt.kind is TokenKind.WORD:
                                words.append(nxt.text)
                                self._next()
                                continue
                            raise ParseError("unexpected token in compound array literal", nxt)
                        # Re-emit as a single word so ``_b_declare`` sees the
                        # full ``name=(elem elem)`` string. Elements are
                        # joined with NUL (\x00) so values containing real
                        # whitespace survive expansion + re-splitting.
                        glued = words[0] + "(" + "\x00".join(words[2:-1]) + ")"
                        args.append(parse_word(glued, line=tok.line))
                        first_word = False
                        continue
                    args.append(w)
                first_word = False
                continue
            break
        if name is None and not assignments and not redirections:
            return None
        return SimpleCommand(
            name=name,
            args=args,
            assignments=assignments,
            redirections=redirections,
            line=line,
        )

    def _parse_redirection(self) -> Redirection:
        tok = self._peek()
        fd: int | None = None
        if tok.kind is TokenKind.IO_NUMBER:
            self._next()
            fd = int(tok.text)
            tok = self._peek()
        if tok.kind is not TokenKind.OPERATOR:
            raise ParseError("expected redirection operator", tok)
        op = tok.text
        op_tok = self._next()
        # Heredocs: the lexer captured the delimiter on the operator token,
        # but the body is only collected after the next NEWLINE the lexer
        # reads. Force the lookahead to advance to that newline so the body
        # is populated before we build the HereDoc node.
        if op in ("<<", "<<-"):
            self._drain_to_newline_for_heredoc()
            body_text = op_tok.heredoc_body or ""
            from just_bash.ast.nodes import Literal as LiteralNode

            if op_tok.heredoc_quoted:
                content = Word(line=op_tok.line, parts=[LiteralNode(value=body_text)])
            else:
                content = parse_word(body_text, line=op_tok.line, allow_tilde=False)
            heredoc = HereDoc(
                line=op_tok.line,
                delimiter=op_tok.heredoc_delim or "",
                content=content,
                strip_tabs=op_tok.heredoc_strip_tabs,
                quoted=op_tok.heredoc_quoted,
            )
            return Redirection(operator=op, target=heredoc, fd=fd, line=op_tok.line)  # type: ignore[arg-type]
        target_tok = self._next()
        if target_tok.kind is not TokenKind.WORD:
            raise ParseError("expected redirection target", target_tok)
        target_word = parse_word(target_tok.text, line=target_tok.line)
        return Redirection(operator=op, target=target_word, fd=fd, line=op_tok.line)  # type: ignore[arg-type]

    # ------------------------------------------------------------------- if
    def _parse_if(self) -> If:
        line = self._peek().line
        self._consume(TokenKind.WORD, "if")
        clauses: list[IfClause] = []
        else_body: list[Statement] | None = None
        condition = self._parse_compound_list_until({"then"})
        self._consume(TokenKind.WORD, "then")
        body = self._parse_compound_list_until({"elif", "else", "fi"})
        clauses.append(IfClause(condition=condition, body=body))
        while self._is_reserved(self._peek(), "elif"):
            self._next()
            cond = self._parse_compound_list_until({"then"})
            self._consume(TokenKind.WORD, "then")
            b = self._parse_compound_list_until({"elif", "else", "fi"})
            clauses.append(IfClause(condition=cond, body=b))
        if self._is_reserved(self._peek(), "else"):
            self._next()
            else_body = self._parse_compound_list_until({"fi"})
        self._consume(TokenKind.WORD, "fi")
        return If(
            clauses=clauses,
            else_body=else_body,
            line=line,
            redirections=self._parse_trailing_redirections(),
        )

    def _parse_compound_list_until(self, terminators: set[str]) -> list[Statement]:
        out: list[Statement] = []
        self._skip_newlines()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.EOF:
                raise ParseError(f"unexpected EOF, expected one of {sorted(terminators)}", tok)
            if tok.kind is TokenKind.WORD and tok.text in terminators:
                return out
            stmt = self._parse_statement()
            if stmt is not None:
                out.append(stmt)
            self._skip_newlines()

    # ------------------------------------------------------------------- for
    def _parse_for(self) -> For:
        line = self._peek().line
        self._consume(TokenKind.WORD, "for")
        # Detect C-style ``for ((init; cond; step))`` form. The lexer
        # already collapsed ``(( ... ))`` into a single OPERATOR token.
        nxt = self._peek()
        if nxt.kind is TokenKind.OPERATOR and nxt.text.startswith("((") and nxt.text.endswith("))"):
            return self._parse_c_for(line)
        var_tok = self._next()
        if var_tok.kind is not TokenKind.WORD:
            raise ParseError("expected for-loop variable", var_tok)
        variable = var_tok.text
        self._skip_newlines()
        words: list[Word] | None = None
        if self._is_reserved(self._peek(), "in"):
            self._next()
            words = []
            while True:
                tok = self._peek()
                if tok.kind is TokenKind.OPERATOR and tok.text in (";", "\n"):
                    self._next()
                    break
                if tok.kind is TokenKind.NEWLINE:
                    self._next()
                    break
                if tok.kind is TokenKind.WORD and tok.text in {"do"}:
                    break
                if tok.kind is TokenKind.WORD:
                    self._next()
                    words.append(parse_word(tok.text, line=tok.line))
                    continue
                if tok.kind is TokenKind.EOF:
                    raise ParseError("unexpected EOF in for-loop", tok)
                raise ParseError("unexpected token in for-loop", tok)
        self._skip_newlines()
        # optional ;
        if self._peek().kind is TokenKind.OPERATOR and self._peek().text == ";":
            self._next()
        self._skip_newlines()
        self._consume(TokenKind.WORD, "do")
        body = self._parse_compound_list_until({"done"})
        self._consume(TokenKind.WORD, "done")
        return For(
            variable=variable,
            words=words,
            body=body,
            line=line,
            redirections=self._parse_trailing_redirections(),
        )

    def _parse_c_for(self, line: int) -> For:
        """Parse ``for ((init; cond; step)); do ... done``.

        We model it as a regular ``For`` whose body is wrapped: the init runs
        once before the loop via a synthetic prologue statement, the cond is
        re-checked each iteration, and the step is appended to the body. To
        keep the AST shape compact we synthesize a ``While`` and reuse the
        existing executor instead.
        """
        cstyle_tok = self._next()
        # Peel off the ``((...))`` wrappers.
        body_text = cstyle_tok.text[2:-2]
        # Three semicolon-delimited expressions.
        sections = _split_top_arith(body_text)
        if len(sections) != 3:
            raise ParseError("expected three ;-separated arithmetic expressions", cstyle_tok)
        init_text, cond_text, step_text = sections
        from just_bash.ast.nodes import (
            ArithmeticCommand as _AC,
        )
        from just_bash.ast.nodes import (
            Pipeline as _Pi,
        )
        from just_bash.ast.nodes import (
            Statement as _St,
        )

        def _arith_stmt(text: str, *, default: str = "1", set_e_safe: bool = False) -> _St:
            text = text.strip() or default
            expr = parse_arith_text(text)
            cmd = _AC(expression=expr, line=line)
            return _St(
                pipelines=[_Pi(commands=[cmd], line=line)],
                line=line,
                set_e_safe=set_e_safe,
            )

        # init/cond/step run for their side effects or as loop machinery;
        # bash exempts them from ``set -e`` (only the body's statements
        # count toward errexit).
        init_stmt = _arith_stmt(init_text, default="0", set_e_safe=True)
        cond_stmt = _arith_stmt(cond_text, default="1", set_e_safe=True)
        step_stmt = _arith_stmt(step_text, default="0", set_e_safe=True)
        # A trailing ``:`` no-op keeps the loop body's last exit code at 0
        # so the for-loop as a whole reports success even if the step's
        # arithmetic value is zero (which would otherwise be rc=1).
        from just_bash.ast.nodes import SimpleCommand as _SC

        noop_cmd = _SC(name=parse_word(":", line=line), line=line)
        noop_stmt = _St(
            pipelines=[_Pi(commands=[noop_cmd], line=line)],
            line=line,
            set_e_safe=True,
        )
        # Skip optional ``;`` and newlines, expect ``do``.
        self._skip_newlines()
        if self._peek().kind is TokenKind.OPERATOR and self._peek().text == ";":
            self._next()
        self._skip_newlines()
        self._consume(TokenKind.WORD, "do")
        body = self._parse_compound_list_until({"done"})
        self._consume(TokenKind.WORD, "done")
        # Append step to body; wrap init+While inside a Group so the For-like
        # node can reuse the existing for-execution path. Easier: return a
        # synthetic ``Group`` containing init then While(cond, body+step).
        from just_bash.ast.nodes import Group as _Gr
        from just_bash.ast.nodes import While as _Wh

        wh = _Wh(
            condition=[cond_stmt],
            body=[*body, step_stmt, noop_stmt],
            line=line,
        )
        wh_stmt = _St(pipelines=[_Pi(commands=[wh], line=line)], line=line)
        group = _Gr(body=[init_stmt, wh_stmt], line=line)
        # We have to return a For-typed node; wrap inside a one-shot ``For``
        # whose body evaluates the synthesized group. Use the existing
        # synthesized statement wiring by treating this as ``for _ in _; do
        # GROUP; done`` with a single iteration -> easier: just return Group.
        # The caller stores it in a Pipeline.commands list, which accepts any
        # CompoundCommand. Cast accordingly.
        return group  # type: ignore[return-value]

    def _parse_select(self) -> For:
        """Parse ``select VAR in WORDS; do BODY; done``.

        Sandboxed semantics: the body runs once per word (no interactive
        prompt). This keeps scripts that use ``select`` for menu-style
        iteration deterministic.
        """
        line = self._peek().line
        self._consume(TokenKind.WORD, "select")
        var_tok = self._next()
        if var_tok.kind is not TokenKind.WORD:
            raise ParseError("expected select variable", var_tok)
        variable = var_tok.text
        self._skip_newlines()
        words: list[Word] | None = None
        if self._is_reserved(self._peek(), "in"):
            self._next()
            words = []
            while True:
                tok = self._peek()
                if tok.kind is TokenKind.OPERATOR and tok.text in (";", "\n"):
                    self._next()
                    break
                if tok.kind is TokenKind.NEWLINE:
                    self._next()
                    break
                if tok.kind is TokenKind.WORD and tok.text == "do":
                    break
                if tok.kind is TokenKind.WORD:
                    self._next()
                    words.append(parse_word(tok.text, line=tok.line))
                    continue
                if tok.kind is TokenKind.EOF:
                    raise ParseError("unexpected EOF in select", tok)
                raise ParseError("unexpected token in select", tok)
        self._skip_newlines()
        if self._peek().kind is TokenKind.OPERATOR and self._peek().text == ";":
            self._next()
        self._skip_newlines()
        self._consume(TokenKind.WORD, "do")
        body = self._parse_compound_list_until({"done"})
        self._consume(TokenKind.WORD, "done")
        return For(
            variable=variable,
            words=words,
            body=body,
            line=line,
            redirections=self._parse_trailing_redirections(),
        )

    # ------------------------------------------------------------ while/until
    def _parse_while(self) -> While:
        return cast("While", self._parse_loop("while", While))

    def _parse_until(self) -> Until:
        return cast("Until", self._parse_loop("until", Until))

    def _parse_loop(self, kw: str, ctor: type) -> CompoundCommand:
        line = self._peek().line
        self._consume(TokenKind.WORD, kw)
        condition = self._parse_compound_list_until({"do"})
        self._consume(TokenKind.WORD, "do")
        body = self._parse_compound_list_until({"done"})
        self._consume(TokenKind.WORD, "done")
        return ctor(
            condition=condition,
            body=body,
            line=line,
            redirections=self._parse_trailing_redirections(),
        )

    # ------------------------------------------------------------------- case
    def _parse_case(self) -> Case:
        line = self._peek().line
        self._consume(TokenKind.WORD, "case")
        word_tok = self._next()
        if word_tok.kind is not TokenKind.WORD:
            raise ParseError("expected case word", word_tok)
        word = parse_word(word_tok.text, line=word_tok.line)
        self._skip_newlines()
        if not self._is_reserved(self._peek(), "in"):
            raise ParseError("expected 'in'", self._peek())
        self._next()
        self._skip_newlines()
        items: list[CaseItem] = []
        while True:
            tok = self._peek()
            if self._is_reserved(tok, "esac"):
                self._next()
                break
            if tok.kind is TokenKind.EOF:
                raise ParseError("unexpected EOF in case", tok)
            items.append(self._parse_case_item())
            self._skip_newlines()
        return Case(
            word=word,
            items=items,
            line=line,
            redirections=self._parse_trailing_redirections(),
        )

    def _parse_case_item(self) -> CaseItem:
        # Optional leading (
        if self._peek().kind is TokenKind.OPERATOR and self._peek().text == "(":
            self._next()
        patterns: list[Word] = []
        while True:
            tok = self._next()
            if tok.kind is not TokenKind.WORD:
                raise ParseError("expected case pattern", tok)
            patterns.append(parse_word(tok.text, line=tok.line))
            sep = self._peek()
            if sep.kind is TokenKind.OPERATOR and sep.text == "|":
                self._next()
                continue
            if sep.kind is TokenKind.OPERATOR and sep.text == ")":
                self._next()
                break
            raise ParseError("expected | or ) in case pattern", sep)
        body: list[Statement] = []
        self._skip_newlines()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.OPERATOR and tok.text in {";;", ";&", ";;&"}:
                terminator = tok.text
                self._next()
                return CaseItem(patterns=patterns, body=body, terminator=terminator)  # type: ignore[arg-type]
            if self._is_reserved(tok, "esac"):
                return CaseItem(patterns=patterns, body=body, terminator=";;")
            stmt = self._parse_statement()
            if stmt is not None:
                body.append(stmt)
            self._skip_newlines()

    def _parse_arith_command_token(self) -> ArithmeticCommand:
        tok = self._next()
        # tok.text is "((<body>))" - strip the wrappers.
        body = tok.text[2:-2]
        expr = parse_arith_text(body)
        return ArithmeticCommand(expression=expr, line=tok.line)

    def _parse_subshell(self) -> Subshell:
        line = self._peek().line
        self._consume(TokenKind.OPERATOR, "(")
        body = self._parse_compound_list_until_close_paren()
        self._consume(TokenKind.OPERATOR, ")")
        return Subshell(body=body, line=line, redirections=self._parse_trailing_redirections())

    def _parse_trailing_redirections(self) -> list[Redirection]:
        """Collect redirections following a compound command (``) >file``, ``done >file``)."""
        out: list[Redirection] = []
        while True:
            t = self._peek()
            if t.kind is TokenKind.IO_NUMBER:
                out.append(self._parse_redirection())
                continue
            if t.kind is TokenKind.OPERATOR and t.text in {
                "<",
                ">",
                ">>",
                ">|",
                "<>",
                "<<<",
                "<<",
                "<<-",
                "&>",
                "&>>",
                ">&",
                "<&",
            }:
                out.append(self._parse_redirection())
                continue
            return out

    def _parse_compound_list_until_close_paren(self) -> list[Statement]:
        out: list[Statement] = []
        self._skip_newlines()
        while True:
            tok = self._peek()
            if tok.kind is TokenKind.OPERATOR and tok.text == ")":
                return out
            if tok.kind is TokenKind.EOF:
                raise ParseError("unexpected EOF in subshell", tok)
            stmt = self._parse_statement()
            if stmt is not None:
                out.append(stmt)
            self._skip_newlines()

    def _parse_group(self) -> Group:
        line = self._peek().line
        self._consume(TokenKind.WORD, "{")
        body = self._parse_compound_list_until({"}"})
        self._consume(TokenKind.WORD, "}")
        return Group(body=body, line=line, redirections=self._parse_trailing_redirections())

    # ---------------------------------------------------------------- functions
    def _parse_function_keyword(self) -> FunctionDef:
        line = self._peek().line
        self._consume(TokenKind.WORD, "function")
        name_tok = self._next()
        if name_tok.kind is not TokenKind.WORD:
            raise ParseError("expected function name", name_tok)
        # Optional ()
        if self._peek().kind is TokenKind.OPERATOR and self._peek().text == "(":
            self._next()
            self._consume(TokenKind.OPERATOR, ")")
        self._skip_newlines()
        body = self._parse_compound_command_for_function()
        return FunctionDef(name=name_tok.text, body=body, line=line)

    def _parse_function_paren(self) -> FunctionDef:
        line = self._peek().line
        name_tok = self._next()
        self._consume(TokenKind.OPERATOR, "(")
        self._consume(TokenKind.OPERATOR, ")")
        self._skip_newlines()
        body = self._parse_compound_command_for_function()
        return FunctionDef(name=name_tok.text, body=body, line=line)

    def _parse_compound_command_for_function(self) -> CompoundCommand:
        tok = self._peek()
        if tok.kind is TokenKind.WORD and tok.text == "{":
            return self._parse_group()
        if tok.kind is TokenKind.OPERATOR and tok.text == "(":
            return cast("CompoundCommand", self._parse_subshell())
        if tok.kind is TokenKind.WORD and tok.text in {"if", "for", "while", "until", "case"}:
            cmd = self._parse_command()
            if not isinstance(
                cmd,
                (
                    If,
                    For,
                    While,
                    Until,
                    Case,
                    Group,
                    Subshell,
                    ArithmeticCommand,
                    ConditionalCommand,
                ),
            ):
                raise ParseError("expected compound command for function body", tok)
            return cmd
        raise ParseError("expected compound command for function body", tok)

    # ------------------------------------------------------------ [[ ... ]]
    def _parse_conditional_command(self) -> ConditionalCommand:
        line = self._peek().line
        self._consume(TokenKind.WORD, "[[")
        expr = self._parse_cond_or()
        if not self._is_reserved(self._peek(), "]]"):
            raise ParseError("expected ']]'", self._peek())
        self._next()
        return ConditionalCommand(expression=expr, line=line)

    def _parse_cond_or(self) -> Conditional:
        left = self._parse_cond_and()
        while self._peek().kind is TokenKind.OPERATOR and self._peek().text == "||":
            self._next()
            right = self._parse_cond_and()
            left = CondOr(left=left, right=right)
        return left

    def _parse_cond_and(self) -> Conditional:
        left = self._parse_cond_unary()
        while self._peek().kind is TokenKind.OPERATOR and self._peek().text == "&&":
            self._next()
            right = self._parse_cond_unary()
            left = CondAnd(left=left, right=right)
        return left

    def _parse_cond_unary(self) -> Conditional:
        tok = self._peek()
        if tok.kind is TokenKind.WORD and tok.text == "!":
            self._next()
            return CondNot(operand=self._parse_cond_unary())
        if tok.kind is TokenKind.OPERATOR and tok.text == "(":
            self._next()
            inner = self._parse_cond_or()
            if not (self._peek().kind is TokenKind.OPERATOR and self._peek().text == ")"):
                raise ParseError("expected ')'", self._peek())
            self._next()
            return inner
        return self._parse_cond_primary()

    def _parse_cond_primary(self) -> Conditional:
        first = self._next()
        if first.kind is not TokenKind.WORD:
            raise ParseError("expected word in conditional", first)
        if first.text in _UNARY_COND_OPS:
            operand_tok = self._next()
            if operand_tok.kind is not TokenKind.WORD:
                raise ParseError("expected operand", operand_tok)
            return CondUnary(
                operator=first.text, operand=parse_word(operand_tok.text, line=operand_tok.line)
            )
        # Binary or single-word.
        nxt = self._peek()
        if (nxt.kind is TokenKind.WORD and nxt.text in _BINARY_COND_OPS) or (
            nxt.kind is TokenKind.OPERATOR and nxt.text in {"<", ">"}
        ):
            op_tok = self._next()
            if op_tok.text == "=~":
                # The regex RHS may contain ``(`` ``)`` ``|`` etc. that the
                # lexer has split into separate tokens. Glue everything up to
                # the next conditional terminator back into a single regex.
                right_text = self._collect_regex_rhs()
                return CondBinary(
                    operator=op_tok.text,
                    left=parse_word(first.text, line=first.line),
                    right=parse_word(right_text, line=op_tok.line),
                )
            right_tok = self._next()
            if right_tok.kind is not TokenKind.WORD:
                raise ParseError("expected right operand", right_tok)
            return CondBinary(
                operator=op_tok.text,
                left=parse_word(first.text, line=first.line),
                right=parse_word(right_tok.text, line=right_tok.line),
            )
        # Single word: truthy if non-empty.
        return CondUnary(operator="-n", operand=parse_word(first.text, line=first.line))

    def _collect_regex_rhs(self) -> str:
        """Glue tokens together until a conditional terminator is reached.

        ``[[ s =~ a(b)c ]]`` lexes into ``a`` ``(`` ``b`` ``)`` ``c`` — we
        re-join them so the regex engine receives the original POSIX ERE.
        Stops at ``]]``, ``&&``, ``||`` (at cond depth 0), or a closing
        ``)`` that matches an unbalanced opener.
        """
        parts: list[str] = []
        paren_depth = 0
        while True:
            tok = self._peek()
            text = tok.text
            if tok.kind is TokenKind.WORD and text == "]]" and paren_depth == 0:
                break
            if tok.kind is TokenKind.OPERATOR and text in ("&&", "||") and paren_depth == 0:
                break
            if tok.kind is TokenKind.OPERATOR and text == ")" and paren_depth == 0:
                break
            if tok.kind is TokenKind.OPERATOR and text == "(":
                paren_depth += 1
            elif tok.kind is TokenKind.OPERATOR and text == ")":
                paren_depth -= 1
            parts.append(text)
            self._next()
        if not parts:
            raise ParseError("expected regex after =~", self._peek())
        return "".join(parts)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_parse_assignment(tok: Token) -> Assignment | None:
    """Detect ``NAME=VALUE`` / ``NAME+=VALUE`` / ``NAME[KEY]=VALUE`` shapes."""
    text = tok.text
    if not text:
        return None
    if not (text[0].isalpha() or text[0] == "_"):
        return None
    i = 1
    while i < len(text) and (text[i].isalnum() or text[i] == "_"):
        i += 1
    if i >= len(text):
        return None
    subscript: str | None = None
    if text[i] == "[":
        # NAME[KEY]=value form. Find matching ].
        depth = 1
        j = i + 1
        while j < len(text) and depth > 0:
            if text[j] == "[":
                depth += 1
            elif text[j] == "]":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if j >= len(text) or text[j] != "]":
            return None
        subscript = text[i + 1 : j]
        i = j + 1
        if i >= len(text):
            return None
    append = False
    if text[i] == "+" and i + 1 < len(text) and text[i + 1] == "=":
        append = True
        eq = i + 1
    elif text[i] == "=":
        eq = i
    else:
        return None
    name = text[: i if subscript is None else text.index("[")]
    value_text = text[eq + 1 :]
    value = parse_word(value_text, line=tok.line) if value_text else None
    a = Assignment(name=name, value=value, append=append, line=tok.line)
    if subscript is not None:
        a.subscript = subscript
    return a


def _split_top_arith(text: str) -> list[str]:
    """Split ``init; cond; step`` honouring nested parens / quotes."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    in_q = False
    quote = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if in_q:
            cur.append(ch)
            if ch == "\\" and i + 1 < len(text):
                cur.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                in_q = False
            i += 1
            continue
        if ch in ("'", '"'):
            in_q = True
            quote = ch
            cur.append(ch)
        elif ch == "(":
            depth += 1
            cur.append(ch)
        elif ch == ")":
            depth -= 1
            cur.append(ch)
        elif ch == ";" and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
        i += 1
    if cur:
        parts.append("".join(cur))
    return parts


def parse(source: str) -> Script:
    """Top-level convenience wrapper: source text -> ``Script`` AST."""
    return Parser(source).parse()


__all__ = ["ParseError", "Parser", "parse"]


_ = Arithmetic  # silence unused-import for type-only forward references
