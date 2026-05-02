"""``sed`` - stream editor.

Supports:
  - ``s/pat/repl/flags``       (flags: ``g``, ``i``, ``N``)
  - ``d`` (delete), ``p`` (print), ``q`` (quit)
  - addresses: line numbers, ``$``, ``/regex/``, ranges ``a,b``
  - ``-n`` quiet (suppress automatic print)
  - ``-E`` / ``-r`` extended regex
  - multiple ``-e EXPR`` / single inline expression
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


@dataclass(slots=True)
class SedOp:
    addr1: str | None  # None = no address
    addr2: str | None  # None = single address; otherwise range end
    command: str  # 's', 'd', 'p', 'q', '='
    args: tuple[str, ...]


def cmd_sed(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, positional = parse_flags(
            argv,
            boolean={"-n", "-E", "-r", "-i"},
            valued={"-e", "-f"},
        )
    except ValueError as e:
        write_err(io_ctx, f"sed: {e}\n")
        return 2
    program_parts: list[str] = []
    if "-e" in flags:
        program_parts.append(str(flags["-e"]))
    if "-f" in flags:
        program_parts.append(interp.fs.read_text(str(flags["-f"])))
    files: list[str]
    if program_parts:
        files = positional
    else:
        if not positional:
            write_err(io_ctx, b"sed: missing script\n")
            return 2
        program_parts.append(positional[0])
        files = positional[1:]
    program = "\n".join(program_parts)
    quiet = bool(flags.get("-n"))
    extended = bool(flags.get("-E") or flags.get("-r"))
    ops = _parse_program(program)
    data, rc = read_input(interp, io_ctx, files)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    out_lines: list[str] = []
    for idx, raw in enumerate(lines, 1):
        line = raw
        printed = False
        deleted = False
        last_idx = idx == len(lines)
        for op in ops:
            if not _addr_matches(op, idx, last_idx, line):
                continue
            if op.command == "d":
                deleted = True
                break
            if op.command == "p":
                out_lines.append(line)
                continue
            if op.command == "q":
                if not quiet:
                    out_lines.append(line)
                    printed = True
                _flush(io_ctx, out_lines)
                return rc
            if op.command == "s":
                pat, repl, sflags = op.args
                if extended:
                    sflags = sflags + "E"
                line = _do_sub(line, pat, repl, sflags)
                continue
            if op.command == "=":
                out_lines.append(str(idx))
                continue
        if deleted:
            continue
        if not quiet and not printed:
            out_lines.append(line)
    _flush(io_ctx, out_lines)
    return rc


def _flush(io_ctx: IO, lines: list[str]) -> None:
    if lines:
        write_out(io_ctx, "\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _parse_program(text: str) -> list[SedOp]:
    ops: list[SedOp] = []
    for raw in text.split("\n"):
        stmt = raw.strip()
        if not stmt or stmt.startswith("#"):
            continue
        ops.extend(_parse_statement(stmt))
    return ops


def _parse_statement(stmt: str) -> list[SedOp]:
    out: list[SedOp] = []
    i = 0
    n = len(stmt)
    while i < n:
        # Skip whitespace and command separators.
        while i < n and stmt[i] in " \t;":
            i += 1
        if i >= n:
            break
        addr1, addr2, i = _parse_addresses(stmt, i)
        # Skip whitespace between addresses and command.
        while i < n and stmt[i] in " \t":
            i += 1
        if i >= n:
            break
        cmd = stmt[i]
        if cmd == "s":
            i += 1
            sep = stmt[i]
            i += 1
            # pattern, then replacement, both terminated by sep, with backslash escapes.
            pat, i = _scan_until(stmt, i, sep)
            repl, i = _scan_until(stmt, i, sep)
            sflags = ""
            while i < n and stmt[i] not in " \t;":
                sflags += stmt[i]
                i += 1
            out.append(SedOp(addr1, addr2, "s", (pat, repl, sflags)))
            continue
        if cmd in ("d", "p", "q", "=", "n"):
            out.append(SedOp(addr1, addr2, cmd, ()))
            i += 1
            continue
        # Unknown command - skip to next ;
        while i < n and stmt[i] != ";":
            i += 1
    return out


def _parse_addresses(stmt: str, i: int) -> tuple[str | None, str | None, int]:
    n = len(stmt)
    addr1, i = _parse_addr(stmt, i)
    addr2: str | None = None
    if i < n and stmt[i] == ",":
        addr2, i = _parse_addr(stmt, i + 1)
    return addr1, addr2, i


def _parse_addr(stmt: str, i: int) -> tuple[str | None, int]:
    n = len(stmt)
    if i >= n:
        return None, i
    ch = stmt[i]
    if ch.isdigit():
        j = i
        while j < n and stmt[j].isdigit():
            j += 1
        return stmt[i:j], j
    if ch == "$":
        return "$", i + 1
    if ch == "/":
        end, _ = _scan_until(stmt, i + 1, "/")
        return f"/{end}/", _ if end is not None else i + 1
    return None, i


def _scan_until(stmt: str, i: int, sep: str) -> tuple[str, int]:
    out: list[str] = []
    n = len(stmt)
    while i < n:
        ch = stmt[i]
        if ch == "\\" and i + 1 < n:
            out.append(ch)
            out.append(stmt[i + 1])
            i += 2
            continue
        if ch == sep:
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    return "".join(out), i


# ---------------------------------------------------------------------------
# Address evaluation
# ---------------------------------------------------------------------------


_RANGE_STATE: dict[int, bool] = {}  # tracks whether we're inside an active range


def _addr_matches(op: SedOp, line_no: int, is_last: bool, line: str) -> bool:
    if op.addr1 is None:
        return True
    in_range = _addr_atom(op.addr1, line_no, is_last, line)
    if op.addr2 is None:
        return in_range
    key = id(op)
    state = _RANGE_STATE.get(key, False)
    if state:
        if _addr_atom(op.addr2, line_no, is_last, line):
            _RANGE_STATE[key] = False
        return True
    if in_range:
        # Activate unless addr2 already matches on the same line.
        if not _addr_atom(op.addr2, line_no, is_last, line):
            _RANGE_STATE[key] = True
        return True
    return False


def _addr_atom(addr: str, line_no: int, is_last: bool, line: str) -> bool:
    if addr == "$":
        return is_last
    if addr.startswith("/") and addr.endswith("/"):
        try:
            return re.search(addr[1:-1], line) is not None
        except re.error:
            return False
    try:
        return int(addr) == line_no
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# s/pat/repl/flags
# ---------------------------------------------------------------------------


def _do_sub(line: str, pat: str, repl: str, flags: str) -> str:
    re_flags = 0
    if "i" in flags or "I" in flags:
        re_flags |= re.IGNORECASE
    g = "g" in flags
    nth: int | None = None
    if any(ch.isdigit() for ch in flags):
        digits = "".join(ch for ch in flags if ch.isdigit())
        nth = int(digits)
    use_pat = pat if "E" in flags else _bre_to_python(pat)
    try:
        compiled = re.compile(use_pat, re_flags)
    except re.error:
        return line
    py_repl = _convert_sed_repl(repl)
    if nth is not None:
        # Replace the Nth match only.
        result: list[str] = []
        last = 0
        for idx, m in enumerate(compiled.finditer(line), start=1):
            if idx == nth:
                result.append(line[last : m.start()])
                result.append(m.expand(py_repl))
                last = m.end()
                if not g:
                    result.append(line[last:])
                    return "".join(result)
        if not result:
            return line
        result.append(line[last:])
        return "".join(result)
    if g:
        return compiled.sub(py_repl, line)
    return compiled.sub(py_repl, line, count=1)


def _bre_to_python(pat: str) -> str:
    """Translate sed BRE syntax to Python regex.

    In BRE, ``(``/``)``/``{``/``}``/``|``/``+``/``?`` are literal and the
    backslash-prefixed versions are metacharacters. Python's regex flips this.
    """
    out: list[str] = []
    i = 0
    while i < len(pat):
        ch = pat[i]
        if ch == "\\" and i + 1 < len(pat):
            nxt = pat[i + 1]
            if nxt in "(){}|+?":
                out.append(nxt)
                i += 2
                continue
            if nxt.isdigit():
                # Back-reference - keep as-is.
                out.append(ch)
                out.append(nxt)
                i += 2
                continue
            out.append(ch)
            out.append(nxt)
            i += 2
            continue
        if ch in "(){}|+?":
            out.append("\\" + ch)
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _convert_sed_repl(repl: str) -> str:
    """Convert sed back-references (``\\1``) into Python ones (``\\g<1>``)."""
    out: list[str] = []
    i = 0
    while i < len(repl):
        ch = repl[i]
        if ch == "\\" and i + 1 < len(repl):
            nxt = repl[i + 1]
            if nxt.isdigit():
                out.append(rf"\g<{nxt}>")
                i += 2
                continue
            if nxt == "&":
                out.append("&")
                i += 2
                continue
            if nxt == "\\":
                out.append("\\\\")
                i += 2
                continue
            if nxt == "n":
                out.append("\n")
                i += 2
                continue
            if nxt == "t":
                out.append("\t")
                i += 2
                continue
            out.append(nxt)
            i += 2
            continue
        if ch == "&":
            out.append(r"\g<0>")
            i += 1
            continue
        out.append(ch)
        i += 1
    return "".join(out)


__all__ = ["cmd_sed"]
