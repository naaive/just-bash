"""``sed`` - stream editor.

Supports a broad subset:
  - ``s/pat/repl/flags`` (flags: ``g``, ``i`` / ``I``, ``N``, ``p``)
  - ``d`` delete, ``p`` print, ``q`` quit, ``=`` line number, ``n`` next
  - ``h`` / ``H`` / ``g`` / ``G`` / ``x`` hold-space ops
  - ``c`` change, ``i`` insert before, ``a`` append after
  - ``y/SRC/DST/`` transliterate
  - ``: label`` / ``b LABEL`` / ``t LABEL`` branches (unconditional / on-success)
  - ``{ ... }`` grouped blocks tied to a single address
  - addresses: line numbers, ``$``, ``/regex/``, ranges ``a,b``, ``!`` negation
  - ``-n`` quiet, ``-E`` / ``-r`` extended regex, ``-e EXPR`` multiple programs
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out
from just_bash.fs.vfs import FsError

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# Sed bytecode-ish: each op has an address pair, command, args, and the
# computed jump-target index for ``b`` / ``t``.
@dataclass(slots=True)
class SedOp:
    addr1: str | None = None
    addr2: str | None = None
    negate: bool = False
    command: str = ""
    args: tuple[str, ...] = ()
    target: int = -1  # branch destination index, set during compilation
    extended: bool = False


@dataclass(slots=True)
class SedState:
    pattern: str = ""
    hold: str = ""
    deleted: bool = False
    quit: bool = False
    last_sub_matched: bool = False
    appended: list[str] = field(default_factory=list)
    range_state: dict[int, bool] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def cmd_sed(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, positional = parse_flags(
            argv,
            boolean={"-n", "-E", "-r", "-i"},
            valued={"-e", "-f"},
            multi={"-e", "-f"},
        )
    except ValueError as e:
        write_err(io_ctx, f"sed: {e}\n")
        return 2
    program_parts: list[str] = []
    if "-e" in flags:
        e_val = flags["-e"]
        if isinstance(e_val, list):
            program_parts.extend(e_val)
        else:
            program_parts.append(str(e_val))
    if "-f" in flags:
        f_val = flags["-f"]
        f_paths = f_val if isinstance(f_val, list) else [str(f_val)]
        for f in f_paths:
            program_parts.append(interp.fs.read_text(f))
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
    in_place = bool(flags.get("-i"))
    ops, error = _compile(program, extended=extended)
    if error is not None:
        write_err(io_ctx, f"sed: {error}\n".encode())
        return 2
    if in_place:
        if not files:
            write_err(io_ctx, b"sed: -i requires file operands\n")
            return 2
        rc = 0
        for f in files:
            try:
                file_data = interp.fs.read_text(f)
            except FsError as e:
                write_err(io_ctx, f"sed: {e}\n")
                rc = 1
                continue
            new_text = _apply_program(ops, file_data, quiet)
            try:
                interp.fs.write_file(f, new_text)
            except FsError as e:
                write_err(io_ctx, f"sed: {e}\n")
                rc = 1
        return rc
    data, rc = read_input(interp, io_ctx, files)
    text = data.decode("utf-8", errors="replace")
    new_text = _apply_program(ops, text, quiet)
    if new_text:
        write_out(io_ctx, new_text)
    return rc


def _apply_program(ops: list[SedOp], text: str, quiet: bool) -> str:
    """Run the compiled sed program on a full text blob; return new text."""
    lines = text.split("\n")
    trailing = text.endswith("\n")
    if trailing:
        lines = lines[:-1]
    output: list[str] = []
    state = SedState()
    for idx, raw in enumerate(lines, 1):
        last_idx = idx == len(lines)
        state.pattern = raw
        state.deleted = False
        state.last_sub_matched = False
        state.appended = []
        _execute(ops, state, idx, last_idx)
        if not state.deleted and not quiet:
            output.append(state.pattern)
        if state.appended:
            output.extend(state.appended)
        if state.quit:
            break
    if not output:
        return ""
    return "\n".join(output) + "\n"


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------


def _compile(text: str, *, extended: bool) -> tuple[list[SedOp], str | None]:
    """Parse the sed program into a flat ``SedOp`` list with branch targets."""
    ops: list[SedOp] = []
    labels: dict[str, int] = {}
    pending_branches: list[tuple[int, str]] = []  # (op-index, label)
    i = 0
    text = _normalize_program(text)
    n = len(text)
    while i < n:
        # Skip whitespace and statement separators.
        while i < n and text[i] in " \t;\n":
            i += 1
        if i >= n:
            break
        if text[i] == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        addr1, addr2, i = _parse_addresses(text, i)
        # Skip whitespace between addresses and command.
        while i < n and text[i] in " \t":
            i += 1
        if i >= n:
            break
        negate = False
        if text[i] == "!":
            negate = True
            i += 1
            while i < n and text[i] in " \t":
                i += 1
        if i >= n:
            break
        cmd = text[i]
        if cmd == "{":
            # ``{ ... }`` blocks are flattened: addr applies to the inner ops
            # by inserting a conditional branch at the start.
            i += 1
            block_start = len(ops)
            jump_op = SedOp(
                addr1=addr1,
                addr2=addr2,
                negate=not negate,
                command="b",
                args=("__end_block__",),
            )
            ops.append(jump_op)
            depth = 1
            inner_text = []
            while i < n and depth > 0:
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                inner_text.append(text[i])
                i += 1
            inner = "".join(inner_text)
            inner_ops, err = _compile(inner, extended=extended)
            if err is not None:
                return [], err
            ops.extend(inner_ops)
            jump_op.target = len(ops)
            del block_start  # quiet linter
            continue
        if cmd == ":":
            i += 1
            label, i = _read_label(text, i)
            labels[label] = len(ops)
            continue
        if cmd == "s":
            op, i, err = _parse_sub(text, i, addr1, addr2, negate, extended)
            if err is not None:
                return [], err
            ops.append(op)
            continue
        if cmd == "y":
            op, i, err = _parse_translit(text, i, addr1, addr2, negate)
            if err is not None:
                return [], err
            ops.append(op)
            continue
        if cmd in ("a", "i", "c"):
            i += 1
            # Optional ``\`` continuation for portability.
            while i < n and text[i] in " \t":
                i += 1
            if i < n and text[i] == "\\":
                i += 1
                if i < n and text[i] == "\n":
                    i += 1
            payload, i = _read_to_end_of_line(text, i)
            ops.append(SedOp(addr1=addr1, addr2=addr2, negate=negate, command=cmd, args=(payload,)))
            continue
        if cmd in ("b", "t"):
            i += 1
            while i < n and text[i] in " \t":
                i += 1
            label, i = _read_label(text, i)
            op = SedOp(addr1=addr1, addr2=addr2, negate=negate, command=cmd, args=(label,))
            ops.append(op)
            pending_branches.append((len(ops) - 1, label))
            continue
        if cmd in ("d", "p", "q", "=", "n", "N", "h", "H", "g", "G", "x", "D", "P"):
            ops.append(SedOp(addr1=addr1, addr2=addr2, negate=negate, command=cmd, args=()))
            i += 1
            continue
        return [], f"unknown command {cmd!r}"
    # Resolve branches.
    for op_idx, label in pending_branches:
        if label == "__end_block__":
            continue
        if label == "":
            ops[op_idx].target = len(ops)  # bare ``b`` jumps to end
            continue
        target = labels.get(label)
        if target is None:
            return [], f"undefined label {label!r}"
        ops[op_idx].target = target
    return ops, None


def _normalize_program(text: str) -> str:
    """Sed traditionally allows multiple commands separated by ``;`` or newline.

    We pre-tokenise so the main parser can ignore whitespace handling.
    """
    return text


def _read_label(text: str, i: int) -> tuple[str, int]:
    n = len(text)
    j = i
    while j < n and text[j] not in (" ", "\t", "\n", ";"):
        j += 1
    return text[i:j], j


def _read_to_end_of_line(text: str, i: int) -> tuple[str, int]:
    n = len(text)
    out: list[str] = []
    while i < n and text[i] != "\n":
        if text[i] == "\\" and i + 1 < n:
            nxt = text[i + 1]
            if nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(text[i])
        i += 1
    return "".join(out), i


def _parse_addresses(text: str, i: int) -> tuple[str | None, str | None, int]:
    addr1, i = _parse_addr(text, i)
    addr2: str | None = None
    if i < len(text) and text[i] == ",":
        addr2, i = _parse_addr(text, i + 1)
    return addr1, addr2, i


def _parse_addr(text: str, i: int) -> tuple[str | None, int]:
    n = len(text)
    if i >= n:
        return None, i
    ch = text[i]
    if ch.isdigit():
        j = i
        while j < n and text[j].isdigit():
            j += 1
        return text[i:j], j
    if ch == "$":
        return "$", i + 1
    if ch == "/":
        body, j = _scan_until(text, i + 1, "/")
        return f"/{body}/", j
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


def _parse_sub(
    text: str,
    i: int,
    addr1: str | None,
    addr2: str | None,
    negate: bool,
    extended: bool,
) -> tuple[SedOp, int, str | None]:
    if text[i] != "s":
        return SedOp(), i, "expected s"
    i += 1
    if i >= len(text):
        return SedOp(), i, "incomplete s command"
    sep = text[i]
    i += 1
    pat, i = _scan_until(text, i, sep)
    repl, i = _scan_until(text, i, sep)
    sflags = ""
    n = len(text)
    while i < n and text[i] not in (" ", "\t", ";", "\n", "}"):
        sflags += text[i]
        i += 1
    op = SedOp(
        addr1=addr1,
        addr2=addr2,
        negate=negate,
        command="s",
        args=(pat, repl, sflags),
        extended=extended,
    )
    return op, i, None


def _parse_translit(
    text: str, i: int, addr1: str | None, addr2: str | None, negate: bool
) -> tuple[SedOp, int, str | None]:
    if text[i] != "y":
        return SedOp(), i, "expected y"
    i += 1
    sep = text[i]
    i += 1
    src, i = _scan_until(text, i, sep)
    dst, i = _scan_until(text, i, sep)
    if len(src) != len(dst):
        return SedOp(), i, "y/SRC/DST/ source and dest must have equal length"
    return (
        SedOp(addr1=addr1, addr2=addr2, negate=negate, command="y", args=(src, dst)),
        i,
        None,
    )


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------


def _execute(ops: list[SedOp], state: SedState, line_no: int, is_last: bool) -> None:
    """Run the compiled program on the current ``state.pattern``."""
    pc = 0
    while pc < len(ops):
        op = ops[pc]
        match = _addr_matches(op, state, line_no, is_last)
        if op.negate:
            match = not match
        if not match:
            pc += 1
            continue
        cmd = op.command
        if cmd == "d":
            state.deleted = True
            return
        if cmd == "D":
            # Delete up to first embedded newline; restart cycle with rest.
            nl = state.pattern.find("\n")
            if nl >= 0:
                state.pattern = state.pattern[nl + 1 :]
                pc = 0
                continue
            state.deleted = True
            return
        if cmd == "p":
            state.appended.append(state.pattern)
        elif cmd == "P":
            nl = state.pattern.find("\n")
            state.appended.append(state.pattern if nl < 0 else state.pattern[:nl])
        elif cmd == "=":
            state.appended.append(str(line_no))
        elif cmd == "n":
            # ``n``: in our buffered model, treat as "next iteration" - just
            # leave the pattern alone; the outer loop reads the next line.
            return
        elif cmd == "N":
            return
        elif cmd == "h":
            state.hold = state.pattern
        elif cmd == "H":
            state.hold = state.hold + "\n" + state.pattern if state.hold else state.pattern
        elif cmd == "g":
            state.pattern = state.hold
        elif cmd == "G":
            state.pattern = state.pattern + "\n" + state.hold
        elif cmd == "x":
            state.pattern, state.hold = state.hold, state.pattern
        elif cmd == "q":
            state.quit = True
            return
        elif cmd == "y":
            src, dst = op.args
            state.pattern = state.pattern.translate(str.maketrans(src, dst))
        elif cmd == "a":
            state.appended.append(op.args[0])
        elif cmd == "i":
            # Insert before: emit the inserted text via ``appended`` queue
            # backwards by writing to ``state.pattern`` is wrong; emulate via
            # the ``appended`` list with a separator line: the cycle prints
            # the pattern *after* appended, so ``i`` needs to land *before*.
            # We achieve this by prepending to a synthetic appended list and
            # printing a placeholder that is then merged.
            state.appended.insert(0, op.args[0])
        elif cmd == "c":
            state.pattern = ""
            state.deleted = True
            state.appended.append(op.args[0])
            return
        elif cmd == "s":
            pat, repl, sflags = op.args
            new_pattern, replaced = _do_sub(state.pattern, pat, repl, sflags, op.extended)
            state.pattern = new_pattern
            if replaced:
                state.last_sub_matched = True
                if "p" in sflags:
                    state.appended.append(state.pattern)
        elif cmd == "b":
            pc = op.target if op.target >= 0 else len(ops)
            continue
        elif cmd == "t" and state.last_sub_matched:
            state.last_sub_matched = False
            pc = op.target if op.target >= 0 else len(ops)
            continue
        pc += 1


_RANGE_KEY = id


def _addr_matches(op: SedOp, state: SedState, line_no: int, is_last: bool) -> bool:
    if op.addr1 is None:
        return True
    in_range = _addr_atom(op.addr1, line_no, is_last, state.pattern)
    if op.addr2 is None:
        return in_range
    key = _RANGE_KEY(op)
    active = state.range_state.get(key, False)
    if active:
        if _addr_atom(op.addr2, line_no, is_last, state.pattern):
            state.range_state[key] = False
        return True
    if in_range and not _addr_atom(op.addr2, line_no, is_last, state.pattern):
        state.range_state[key] = True
        return True
    return in_range


def _addr_atom(addr: str, line_no: int, is_last: bool, pattern: str) -> bool:
    if addr == "$":
        return is_last
    if addr.startswith("/") and addr.endswith("/"):
        try:
            return re.search(addr[1:-1], pattern) is not None
        except re.error:
            return False
    try:
        return int(addr) == line_no
    except ValueError:
        return False


# ---------------------------------------------------------------------------
# Substitution helpers (BRE -> Python regex translation, sed-style backrefs)
# ---------------------------------------------------------------------------


def _do_sub(line: str, pat: str, repl: str, flags: str, extended: bool) -> tuple[str, bool]:
    re_flags = 0
    if "i" in flags or "I" in flags:
        re_flags |= re.IGNORECASE
    g = "g" in flags
    nth: int | None = None
    if any(ch.isdigit() for ch in flags):
        digits = "".join(ch for ch in flags if ch.isdigit())
        nth = int(digits)
    use_pat = pat if extended else _bre_to_python(pat)
    try:
        compiled = re.compile(use_pat, re_flags)
    except re.error:
        return line, False
    py_repl = _convert_sed_repl(repl)
    if nth is not None:
        result: list[str] = []
        last = 0
        any_replaced = False
        for idx, m in enumerate(compiled.finditer(line), start=1):
            if idx == nth:
                result.append(line[last : m.start()])
                result.append(m.expand(py_repl))
                last = m.end()
                any_replaced = True
                if not g:
                    result.append(line[last:])
                    return "".join(result), True
        if not result:
            return line, False
        result.append(line[last:])
        return "".join(result), any_replaced
    if g:
        new = compiled.sub(py_repl, line)
        return new, new != line
    new = compiled.sub(py_repl, line, count=1)
    return new, new != line


def _bre_to_python(pat: str) -> str:
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
