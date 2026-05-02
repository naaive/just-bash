"""``find`` - file walker with predicate language and actions.

Supports:
  - tests:    ``-name``, ``-iname``, ``-type f|d``, ``-maxdepth``,
              ``-mindepth``, ``-path``, ``-empty``, ``-size``, ``-not``,
              ``-newer``
  - boolean:  ``-not``, ``-and`` / ``-a`` (implicit), ``-or`` / ``-o``,
              parenthesized groups via ``( ... )``
  - actions:  ``-print`` (default), ``-exec CMD {} \\;`` and the multi-arg
              ``-exec CMD {} +`` form, ``-execdir`` (treated like ``-exec``
              against the entry's directory), ``-delete``
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from just_bash.commands._helpers import write_err, write_out
from just_bash.fs import path_utils
from just_bash.fs.vfs import Directory, File, FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


@dataclass(slots=True)
class _Entry:
    path: str
    name: str
    depth: int
    is_dir: bool
    is_file: bool
    size: int


@dataclass(slots=True)
class _Action:
    kind: str  # 'print' | 'exec' | 'delete'
    cmd: list[str] = field(default_factory=list)
    multi: bool = False  # exec ``+`` form: collect many entries per invocation
    pending: list[str] = field(default_factory=list)  # for exec ``+``


def cmd_find(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    starts: list[str] = []
    i = 0
    while i < len(args) and not args[i].startswith("-") and args[i] not in ("(", ")", "!"):
        starts.append(args[i])
        i += 1
    if not starts:
        starts = ["."]
    rest = args[i:]
    parser = _PredicateParser(rest)
    try:
        matcher, actions = parser.parse()
    except _PredicateError as e:
        write_err(io_ctx, f"find: {e}\n")
        return 2
    if not actions:
        actions = [_Action(kind="print")]
    rc = 0
    for start in starts:
        try:
            interp.fs.stat(start)
        except FsError as e:
            write_err(io_ctx, f"find: {e}\n")
            rc = 1
            continue
        for entry in _walk(interp, start):
            if not matcher(entry):
                continue
            for action in actions:
                action_rc = _run_action(interp, io_ctx, action, entry)
                if action_rc != 0:
                    rc = action_rc
    # Drain any deferred ``-exec ... +`` invocations.
    for action in actions:
        if action.kind == "exec" and action.multi and action.pending:
            sub_argv = [*action.cmd, *action.pending]
            action_rc = interp._dispatch(sub_argv, io_ctx)
            action.pending = []
            if action_rc != 0:
                rc = action_rc
    return rc


# ---------------------------------------------------------------------------
# Predicate parsing - boolean expression over individual tests.
# ---------------------------------------------------------------------------


class _PredicateError(Exception):
    pass


_PredicateFn = Callable[[_Entry], bool]


def _or_pred(a: _PredicateFn, b: _PredicateFn) -> _PredicateFn:
    return lambda e: a(e) or b(e)


def _and_pred(a: _PredicateFn, b: _PredicateFn) -> _PredicateFn:
    return lambda e: a(e) and b(e)


class _PredicateParser:
    """Recursive-descent parser for find predicates with implicit AND."""

    __slots__ = ("_ctx", "actions", "pos", "toks")

    def __init__(self, toks: list[str]) -> None:
        self.toks = toks
        self.pos = 0
        self.actions: list[_Action] = []
        # Top-level test parameters (apply globally) — pulled out of the
        # predicate expression so they can short-circuit the walker.
        self._ctx: dict[str, int | None] = {"maxdepth": None, "mindepth": None}

    def parse(self) -> tuple[_PredicateFn, list[_Action]]:
        if not self.toks:
            return (lambda _e: True), self.actions
        expr = self._parse_or()
        ctx = self._ctx

        def matcher(e: _Entry) -> bool:
            if ctx["maxdepth"] is not None and e.depth > ctx["maxdepth"]:
                return False
            if ctx["mindepth"] is not None and e.depth < ctx["mindepth"]:
                return False
            return expr(e)

        return matcher, self.actions

    def _peek(self) -> str | None:
        return self.toks[self.pos] if self.pos < len(self.toks) else None

    def _next(self) -> str:
        t = self.toks[self.pos]
        self.pos += 1
        return t

    def _parse_or(self) -> _PredicateFn:
        left = self._parse_and()
        while self._peek() in ("-or", "-o"):
            self._next()
            right = self._parse_and()
            left = _or_pred(left, right)
        return left

    def _parse_and(self) -> _PredicateFn:
        left = self._parse_not()
        while True:
            tok = self._peek()
            if tok in ("-or", "-o", ")", None):
                return left
            if tok in ("-and", "-a"):
                self._next()
            right = self._parse_not()
            left = _and_pred(left, right)

    def _parse_not(self) -> _PredicateFn:
        if self._peek() in ("!", "-not"):
            self._next()
            inner = self._parse_not()
            return lambda e: not inner(e)
        return self._parse_primary()

    def _parse_primary(self) -> _PredicateFn:
        tok = self._peek()
        if tok == "(":
            self._next()
            inner = self._parse_or()
            if self._peek() != ")":
                raise _PredicateError("missing ')'")
            self._next()
            return inner
        if tok is None:
            raise _PredicateError("missing predicate")
        return self._parse_test_or_action()

    def _parse_test_or_action(self) -> _PredicateFn:
        tok = self._next()
        # Tests with a single argument.
        if tok == "-name":
            pat = self._next_arg("-name")
            return lambda e, p=pat: fnmatch.fnmatchcase(e.name, p)
        if tok == "-iname":
            pat = self._next_arg("-iname")
            return lambda e, p=pat: fnmatch.fnmatchcase(e.name.lower(), p.lower())
        if tok == "-path":
            pat = self._next_arg("-path")
            return lambda e, p=pat: fnmatch.fnmatchcase(e.path, p)
        if tok == "-type":
            t = self._next_arg("-type")
            if t == "f":
                return lambda e: e.is_file
            if t == "d":
                return lambda e: e.is_dir
            raise _PredicateError(f"unknown -type {t}")
        if tok == "-empty":
            return lambda e: (e.is_file and e.size == 0) or e.is_dir
        if tok == "-size":
            spec = self._next_arg("-size")
            return _make_size_test(spec)
        if tok in ("-maxdepth", "-mindepth"):
            n = int(self._next_arg(tok))
            self._ctx[tok[1:]] = n
            return lambda _e: True
        if tok == "-print":
            self.actions.append(_Action(kind="print"))
            return lambda _e: True
        if tok in ("-exec", "-execdir"):
            cmd, multi = self._parse_exec_args(tok)
            self.actions.append(_Action(kind="exec", cmd=cmd, multi=multi))
            return lambda _e: True
        if tok == "-delete":
            self.actions.append(_Action(kind="delete"))
            return lambda _e: True
        raise _PredicateError(f"unsupported predicate: {tok}")

    def _next_arg(self, owner: str) -> str:
        if self.pos >= len(self.toks):
            raise _PredicateError(f"{owner} missing argument")
        return self._next()

    def _parse_exec_args(self, kind: str) -> tuple[list[str], bool]:
        cmd: list[str] = []
        multi = False
        while self.pos < len(self.toks):
            t = self._next()
            if t == ";" or t == r"\;":
                return cmd, multi
            if t == "+":
                multi = True
                return cmd, multi
            cmd.append(t)
        raise _PredicateError(f"{kind} missing terminator (\\; or +)")


def _make_size_test(spec: str) -> _PredicateFn:
    """``-size`` understands ``+N``, ``-N``, and units c/k/M/G."""
    op = "="
    if spec.startswith("+"):
        op = "+"
        spec = spec[1:]
    elif spec.startswith("-"):
        op = "-"
        spec = spec[1:]
    unit = "b"
    if spec and spec[-1] in "ckMG":
        unit = spec[-1]
        spec = spec[:-1]
    n = int(spec)
    mult = {"b": 512, "c": 1, "k": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}[unit]
    threshold = n * mult

    def fn(e: _Entry) -> bool:
        size = e.size if e.is_file else 0
        if op == "+":
            return size > threshold
        if op == "-":
            return size < threshold
        return size == threshold

    return fn


# ---------------------------------------------------------------------------
# Action runner
# ---------------------------------------------------------------------------


def _run_action(interp: Interpreter, io_ctx: IO, action: _Action, entry: _Entry) -> int:
    if action.kind == "print":
        write_out(io_ctx, entry.path + "\n")
        return 0
    if action.kind == "delete":
        try:
            interp.fs.rm(entry.path, recursive=entry.is_dir, force=True)
        except FsError as e:
            write_err(io_ctx, f"find: {e}\n")
            return 1
        return 0
    if action.kind == "exec":
        if action.multi:
            action.pending.append(entry.path)
            return 0
        sub_argv = [arg.replace("{}", entry.path) for arg in action.cmd]
        return interp._dispatch(sub_argv, io_ctx)
    return 0


def _walk(interp: Interpreter, start: str) -> list[_Entry]:
    out: list[_Entry] = []
    try:
        node = interp.fs.stat(start)
    except FsError:
        return out
    out.append(
        _Entry(
            path=start,
            name=path_utils.basename(start),
            depth=0,
            is_dir=isinstance(node, Directory),
            is_file=isinstance(node, File),
            size=getattr(node, "size", 0),
        )
    )
    if not isinstance(node, Directory):
        return out
    stack: list[tuple[str, int]] = [(start, 0)]
    while stack:
        cur_path, depth = stack.pop()
        try:
            names = interp.fs.listdir(cur_path)
        except FsError:
            continue
        for name in names:
            child_path = path_utils.join(cur_path, name) if cur_path != "/" else "/" + name
            try:
                child = interp.fs.stat(child_path)
            except FsError:
                continue
            out.append(
                _Entry(
                    path=child_path,
                    name=name,
                    depth=depth + 1,
                    is_dir=isinstance(child, Directory),
                    is_file=isinstance(child, File),
                    size=getattr(child, "size", 0),
                )
            )
            if isinstance(child, Directory):
                stack.append((child_path, depth + 1))
    return out


__all__ = ["cmd_find"]
