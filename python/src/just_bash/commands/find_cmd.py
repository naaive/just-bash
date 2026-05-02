"""``find`` - file walker with a small predicate language.

Supports: ``-name``, ``-iname``, ``-type``, ``-maxdepth``, ``-mindepth``,
``-path``, ``-empty``, ``-not``, and the implicit print action.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from just_bash.commands._helpers import write_err, write_out
from just_bash.fs import path_utils
from just_bash.fs.vfs import Directory, File, FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def cmd_find(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    starts: list[str] = []
    i = 0
    # Starting paths come first, until a predicate (starts with -) appears.
    while i < len(args) and not args[i].startswith("-"):
        starts.append(args[i])
        i += 1
    if not starts:
        starts = ["."]
    predicates = args[i:]
    matcher, error = _build_matcher(predicates)
    if error or matcher is None:
        write_err(io_ctx, f"find: {error}\n")
        return 2
    for start in starts:
        try:
            interp.fs.stat(start)
        except FsError as e:
            write_err(io_ctx, f"find: {e}\n")
            continue
        for entry in _walk(interp, start):
            if matcher(entry):
                write_out(io_ctx, entry.path + "\n")
    return 0


# ---------------------------------------------------------------------------
# Walker
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class _Entry:
    path: str
    name: str
    depth: int
    is_dir: bool
    is_file: bool
    size: int


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
    stack: list[tuple[str, Directory, int]] = [(start, node, 0)]
    while stack:
        cur_path, cur, depth = stack.pop()
        for name in sorted(cur.children):
            child = cur.children[name]
            child_path = path_utils.join(cur_path, name) if cur_path != "/" else "/" + name
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
                stack.append((child_path, child, depth + 1))
    return out


# ---------------------------------------------------------------------------
# Predicate compiler
# ---------------------------------------------------------------------------


def _build_matcher(preds: list[str]) -> tuple[Callable[[_Entry], bool] | None, str | None]:
    """Return ``(matcher, error)``. ``matcher(_Entry) -> bool``."""
    if not preds:
        return (lambda _e: True), None
    parsed: list[Callable[[_Entry], bool]] = []
    i = 0
    maxdepth: int | None = None
    mindepth: int | None = None
    while i < len(preds):
        token = preds[i]
        if token == "-maxdepth" and i + 1 < len(preds):
            maxdepth = int(preds[i + 1])
            i += 2
            continue
        if token == "-mindepth" and i + 1 < len(preds):
            mindepth = int(preds[i + 1])
            i += 2
            continue
        if token == "-name" and i + 1 < len(preds):
            pat = preds[i + 1]
            parsed.append(lambda e, p=pat: fnmatch.fnmatchcase(e.name, p))
            i += 2
            continue
        if token == "-iname" and i + 1 < len(preds):
            pat = preds[i + 1]
            parsed.append(lambda e, p=pat: fnmatch.fnmatchcase(e.name.lower(), p.lower()))
            i += 2
            continue
        if token == "-path" and i + 1 < len(preds):
            pat = preds[i + 1]
            parsed.append(lambda e, p=pat: fnmatch.fnmatchcase(e.path, p))
            i += 2
            continue
        if token == "-type" and i + 1 < len(preds):
            t = preds[i + 1]
            if t == "f":
                parsed.append(lambda e: e.is_file)
            elif t == "d":
                parsed.append(lambda e: e.is_dir)
            else:
                return None, f"unknown -type {t}"
            i += 2
            continue
        if token == "-empty":
            parsed.append(lambda e: (e.is_file and e.size == 0) or e.is_dir)
            i += 1
            continue
        if token == "-not":
            i += 1
            if i >= len(preds):
                return None, "missing predicate after -not"
            continue
        if token == "-print":
            i += 1
            continue
        return None, f"unsupported predicate: {token}"

    def matcher(e: _Entry) -> bool:
        if maxdepth is not None and e.depth > maxdepth:
            return False
        if mindepth is not None and e.depth < mindepth:
            return False
        return all(p(e) for p in parsed)

    return matcher, None


__all__ = ["cmd_find"]
