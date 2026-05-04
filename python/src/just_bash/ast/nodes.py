"""Bash AST nodes.

This is a Python port of the TypeScript AST in
``packages/just-bash/src/ast/types.ts``. Every shell construct supported by the
interpreter has a node here. Nodes are immutable-style dataclasses; the parser
constructs them and the interpreter walks them.

Architecture: ``Input -> Lexer -> Parser -> AST -> Interpreter -> ExecResult``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal as LiteralT

# ---------------------------------------------------------------------------
# Word parts
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Node:
    """Base class for AST nodes. ``line`` is 1-based, 0 if unknown."""

    line: int = 0


@dataclass(slots=True)
class Literal(Node):
    """Plain text from the source, no expansions involved."""

    value: str = ""


@dataclass(slots=True)
class SingleQuoted(Node):
    """``'literal'`` - no expansions inside."""

    value: str = ""


@dataclass(slots=True)
class Escaped(Node):
    """Backslash-escaped character outside quotes."""

    value: str = ""


@dataclass(slots=True)
class DoubleQuoted(Node):
    """``"text $var"`` - parts are expanded but stay one word."""

    parts: list[WordPart] = field(default_factory=list)


@dataclass(slots=True)
class ParameterExpansion(Node):
    """``$VAR`` or ``${VAR...}`` with an optional operation.

    ``subscript`` carries an array index when the source is ``${arr[i]}``,
    ``${arr[@]}`` or ``${arr[*]}``. Plain ``$VAR`` leaves it ``None``.
    """

    parameter: str = ""
    operation: ParameterOp | None = None
    subscript: str | None = None  # raw text inside [...]; "@" / "*" are special
    array_keys: bool = False  # ${!arr[@]} / ${!arr[*]}
    indirect: bool = False  # ${!ref}: dereference $parameter, then read that var
    name_prefix: bool = False  # ${!prefix*} / ${!prefix@}: list matching var names


@dataclass(slots=True)
class CommandSubstitution(Node):
    """``$(cmd)`` or backtick ``cmd``."""

    body: Script = field(default_factory=lambda: Script())
    legacy: bool = False  # backticks


@dataclass(slots=True)
class ArithmeticExpansion(Node):
    """``$((expr))``."""

    expression: Arithmetic = field(default_factory=lambda: Arithmetic())


@dataclass(slots=True)
class TildeExpansion(Node):
    """``~`` or ``~user``. None means current user."""

    user: str | None = None


@dataclass(slots=True)
class ProcessSubstitution(Node):
    """``<(cmd)`` or ``>(cmd)``.

    ``direction == "input"`` for ``<(cmd)`` (run cmd, expose its stdout as a
    pseudo-file path); ``"output"`` for ``>(cmd)`` (the path becomes the
    target of writes that are then fed to cmd's stdin).
    """

    body: Script = field(default_factory=lambda: Script())
    direction: LiteralT["input", "output"] = "input"


@dataclass(slots=True)
class Glob(Node):
    """Pathname pattern expanded during pathname expansion."""

    pattern: str = ""


@dataclass(slots=True)
class BraceWord:
    """Plain word item inside a brace expansion."""

    word: Word


@dataclass(slots=True)
class BraceRange:
    """``{1..10}`` or ``{a..z..2}`` - inclusive numeric or single-char range."""

    start: str
    end: str
    step: int = 1
    is_numeric: bool = True


BraceItem = BraceWord | BraceRange


@dataclass(slots=True)
class BraceExpansion(Node):
    """``{a,b,c}`` or ``{1..10}``."""

    items: list[BraceItem] = field(default_factory=list)


WordPart = (
    Literal
    | SingleQuoted
    | DoubleQuoted
    | Escaped
    | ParameterExpansion
    | CommandSubstitution
    | ArithmeticExpansion
    | TildeExpansion
    | ProcessSubstitution
    | BraceExpansion
    | Glob
)


@dataclass(slots=True)
class Word(Node):
    """A sequence of parts that form one shell word before expansion."""

    parts: list[WordPart] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Parameter expansion operations
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class DefaultValue:
    """``${VAR:-default}`` or ``${VAR-default}``."""

    word: Word
    check_empty: bool


@dataclass(slots=True)
class AssignDefault:
    """``${VAR:=default}``."""

    word: Word
    check_empty: bool


@dataclass(slots=True)
class ErrorIfUnset:
    """``${VAR:?msg}``."""

    word: Word | None
    check_empty: bool


@dataclass(slots=True)
class UseAlternative:
    """``${VAR:+alt}``."""

    word: Word
    check_empty: bool


@dataclass(slots=True)
class Length:
    """``${#VAR}``."""


@dataclass(slots=True)
class Substring:
    """``${VAR:offset:length}`` (length optional)."""

    offset: Arithmetic
    length: Arithmetic | None


@dataclass(slots=True)
class PatternRemoval:
    """``${VAR#p}`` ``##`` ``%`` ``%%``."""

    pattern: Word
    side: LiteralT["prefix", "suffix"]
    greedy: bool


@dataclass(slots=True)
class PatternReplacement:
    """``${VAR/p/r}`` ``//`` and ``/#`` / ``/%`` anchors."""

    pattern: Word
    replacement: Word | None
    all_occurrences: bool
    anchor: LiteralT["start", "end"] | None


@dataclass(slots=True)
class CaseModification:
    """``${VAR^}``, ``${VAR^^}``, ``${VAR,}``, ``${VAR,,}`` - case folding."""

    direction: LiteralT["upper", "lower"] = "upper"
    all_chars: bool = False
    pattern: Word | None = None  # optional pattern, e.g. ``${VAR^^[a-c]}``


@dataclass(slots=True)
class Transform:
    """``${VAR@op}`` - ``Q`` quote, ``E`` escape, ``U`` upper, ``L`` lower, ``a`` attrs."""

    operator: LiteralT["Q", "E", "U", "L", "u", "P", "K", "k", "A", "a"] = "Q"


ParameterOp = (
    DefaultValue
    | AssignDefault
    | ErrorIfUnset
    | UseAlternative
    | Length
    | Substring
    | PatternRemoval
    | PatternReplacement
    | CaseModification
    | Transform
)


# ---------------------------------------------------------------------------
# Arithmetic expressions
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class ArithNumber:
    value: int


@dataclass(slots=True)
class ArithVariable:
    name: str
    # ``arr[expr]`` access inside ``$((...))`` / ``((...))``. The subscript
    # holds the raw text between the brackets; evaluator re-parses it as an
    # arithmetic sub-expression after expanding any inner ``$VAR`` etc.
    subscript: str | None = None


@dataclass(slots=True)
class ArithBinary:
    operator: str
    left: ArithExpr
    right: ArithExpr


@dataclass(slots=True)
class ArithUnary:
    operator: str
    operand: ArithExpr
    prefix: bool


@dataclass(slots=True)
class ArithTernary:
    condition: ArithExpr
    consequent: ArithExpr
    alternate: ArithExpr


@dataclass(slots=True)
class ArithAssignment:
    operator: str
    variable: str
    value: ArithExpr


@dataclass(slots=True)
class ArithGroup:
    expression: ArithExpr


ArithExpr = (
    ArithNumber
    | ArithVariable
    | ArithBinary
    | ArithUnary
    | ArithTernary
    | ArithAssignment
    | ArithGroup
)


@dataclass(slots=True)
class Arithmetic(Node):
    """Wraps a single arithmetic expression, used by ``$((...))`` and ``((...))``."""

    expression: ArithExpr | None = None
    source_text: str = ""


# ---------------------------------------------------------------------------
# Conditional ([[ ... ]])
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class CondBinary:
    operator: str
    left: Word
    right: Word


@dataclass(slots=True)
class CondUnary:
    operator: str
    operand: Word


@dataclass(slots=True)
class CondNot:
    operand: Conditional


@dataclass(slots=True)
class CondAnd:
    left: Conditional
    right: Conditional


@dataclass(slots=True)
class CondOr:
    left: Conditional
    right: Conditional


Conditional = CondBinary | CondUnary | CondNot | CondAnd | CondOr


@dataclass(slots=True)
class ConditionalCommand(Node):
    expression: Conditional | None = None
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class ArithmeticCommand(Node):
    expression: Arithmetic = field(default_factory=lambda: Arithmetic())
    redirections: list[Redirection] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Redirections / heredocs
# ---------------------------------------------------------------------------


RedirectOp = LiteralT["<", ">", ">>", ">&", "<&", "<>", ">|", "&>", "&>>", "<<<", "<<", "<<-"]


@dataclass(slots=True)
class HereDoc(Node):
    delimiter: str = ""
    content: Word = field(default_factory=lambda: Word())
    strip_tabs: bool = False
    quoted: bool = False


@dataclass(slots=True)
class Redirection(Node):
    operator: RedirectOp = ">"
    target: Word | HereDoc = field(default_factory=lambda: Word())
    fd: int | None = None


# ---------------------------------------------------------------------------
# Assignments
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class Assignment(Node):
    name: str = ""
    value: Word | None = None
    append: bool = False
    array: list[Word] | None = None
    # ``arr[key]=value`` form: raw subscript text. Resolved at runtime.
    subscript: str | None = None


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class SimpleCommand(Node):
    name: Word | None = None
    args: list[Word] = field(default_factory=list)
    assignments: list[Assignment] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class IfClause:
    condition: list[Statement]
    body: list[Statement]


@dataclass(slots=True)
class If(Node):
    clauses: list[IfClause] = field(default_factory=list)
    else_body: list[Statement] | None = None
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class For(Node):
    variable: str = ""
    words: list[Word] | None = None  # None means iterate over $@
    body: list[Statement] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class While(Node):
    condition: list[Statement] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class Until(Node):
    condition: list[Statement] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class CaseItem(Node):
    patterns: list[Word] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)
    terminator: LiteralT[";;", ";&", ";;&"] = ";;"


@dataclass(slots=True)
class Case(Node):
    word: Word = field(default_factory=lambda: Word())
    items: list[CaseItem] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class Subshell(Node):
    body: list[Statement] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


@dataclass(slots=True)
class Group(Node):
    body: list[Statement] = field(default_factory=list)
    redirections: list[Redirection] = field(default_factory=list)


CompoundCommand = (
    If | For | While | Until | Case | Subshell | Group | ArithmeticCommand | ConditionalCommand
)


@dataclass(slots=True)
class FunctionDef(Node):
    name: str = ""
    body: CompoundCommand | None = None
    redirections: list[Redirection] = field(default_factory=list)


Command = SimpleCommand | CompoundCommand | FunctionDef


@dataclass(slots=True)
class Pipeline(Node):
    commands: list[Command] = field(default_factory=list)
    negated: bool = False
    pipe_stderr: list[bool] = field(default_factory=list)


@dataclass(slots=True)
class Statement(Node):
    """Pipelines connected with ``&&`` / ``||`` / ``;``.

    ``operators`` has length ``len(pipelines) - 1``; ``operators[i]`` is the
    operator between ``pipelines[i]`` and ``pipelines[i + 1]``.
    """

    pipelines: list[Pipeline] = field(default_factory=list)
    operators: list[LiteralT["&&", "||", ";"]] = field(default_factory=list)
    background: bool = False
    # True when this is a synthesized statement that should be exempt from
    # ``set -e`` (e.g. the init / step of a C-style ``for ((;;))`` whose
    # arithmetic result is part of the loop machinery, not the script's
    # success/failure path).
    set_e_safe: bool = False


@dataclass(slots=True)
class Script(Node):
    statements: list[Statement] = field(default_factory=list)
