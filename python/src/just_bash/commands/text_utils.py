"""Text processing utilities: sort, uniq, tr, cut, rev, nl."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from just_bash.commands._helpers import parse_flags, read_input, write_err, write_out

_HUMAN_RE = re.compile(r"^([+-]?[\d.]+)([KMGT])?")

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


def cmd_sort(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(
            argv,
            boolean={"-r", "-u", "-n", "-f", "-b", "-h", "-V", "-R"},
            valued={"-t", "-k"},
            multi={"-k"},
        )
    except ValueError as e:
        write_err(io_ctx, f"sort: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    delim: str | None = None
    if "-t" in flags:
        delim = str(flags["-t"])
    fold = bool(flags.get("-f"))
    skip_blanks = bool(flags.get("-b"))
    numeric = bool(flags.get("-n"))
    human = bool(flags.get("-h"))
    version = bool(flags.get("-V"))
    random_order = bool(flags.get("-R"))

    def field(line: str, spec: str) -> str:
        """Extract the field selected by spec (e.g. ``2``, ``2,3``, ``2.3``)."""
        # bash sort key spec: F[.C][OPTS][,F[.C][OPTS]]
        start_part, _, end_part = spec.partition(",")
        sf, _, _ = start_part.partition(".")
        try:
            start = max(int(sf) - 1, 0)
        except ValueError:
            return line
        if delim is None:
            parts = line.split()
        else:
            parts = line.split(delim)
        if start >= len(parts):
            return ""
        if not end_part:
            return delim.join(parts[start:]) if delim else " ".join(parts[start:])
        ef, _, _ = end_part.partition(".")
        try:
            end = int(ef)
        except ValueError:
            end = start + 1
        return (delim or " ").join(parts[start:end])

    keys = flags.get("-k")
    key_specs: list[str] = (keys if isinstance(keys, list) else [keys]) if keys else []

    def base_key(line: str) -> str:
        if not key_specs:
            return line
        out_parts = [field(line, k) for k in key_specs]
        return "\x00".join(out_parts)

    def transform(s: str) -> str:
        if skip_blanks:
            s = s.lstrip()
        if fold:
            s = s.lower()
        return s

    def numkey(line: str) -> tuple[float, str]:
        s = transform(base_key(line)).lstrip()
        sign = 1
        i = 0
        if s[i : i + 1] == "-":
            sign = -1
            i += 1
        elif s[i : i + 1] == "+":
            i += 1
        # Allow ``,`` thousands separators and decimals.
        digits: list[str] = []
        seen_dot = False
        while i < len(s):
            ch = s[i]
            if ch.isdigit():
                digits.append(ch)
            elif ch == "." and not seen_dot:
                digits.append(".")
                seen_dot = True
            elif ch == ",":
                pass  # ignored separator
            else:
                break
            i += 1
        try:
            num = sign * float("".join(digits)) if digits else 0.0
        except ValueError:
            num = 0.0
        return (num, line)

    def humankey(line: str) -> tuple[float, str]:
        s = transform(base_key(line)).lstrip()
        m = _HUMAN_RE.match(s)
        if m is None:
            return (0.0, line)
        n = float(m.group(1))
        suffix = (m.group(2) or "").upper()
        mult = {"": 1, "K": 1024, "M": 1024**2, "G": 1024**3, "T": 1024**4}.get(suffix, 1)
        return (n * mult, line)

    def versionkey(line: str) -> list[object]:
        s = transform(base_key(line))
        # Split on runs of digits vs non-digits; compare numerically piece by piece.
        out: list[object] = []
        i = 0
        while i < len(s):
            if s[i].isdigit():
                j = i
                while j < len(s) and s[j].isdigit():
                    j += 1
                out.append((1, int(s[i:j])))
                i = j
            else:
                j = i
                while j < len(s) and not s[j].isdigit():
                    j += 1
                out.append((0, s[i:j]))
                i = j
        return out

    if random_order:
        import random as _r

        rng = _r.Random()
        rng.shuffle(lines)
    elif numeric:
        lines.sort(key=numkey, reverse=bool(flags.get("-r")))
    elif human:
        lines.sort(key=humankey, reverse=bool(flags.get("-r")))
    elif version:
        lines.sort(key=versionkey, reverse=bool(flags.get("-r")))
    else:
        lines.sort(key=lambda s: transform(base_key(s)), reverse=bool(flags.get("-r")))

    if flags.get("-u"):
        seen: set[str] = set()
        deduped: list[str] = []
        for ln in lines:
            k = transform(base_key(ln))
            if k in seen:
                continue
            seen.add(k)
            deduped.append(ln)
        lines = deduped
    out = "\n".join(lines) + ("\n" if lines else "")
    write_out(io_ctx, out)
    return rc




def cmd_uniq(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean={"-c", "-d", "-u", "-i"})
    except ValueError as e:
        write_err(io_ctx, f"uniq: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    norm = (lambda s: s.lower()) if flags.get("-i") else (lambda s: s)
    out: list[str] = []
    if not lines:
        return rc
    runs: list[tuple[str, int, str]] = []  # (norm_key, count, original_first)
    cur_key = norm(lines[0])
    cur_count = 1
    cur_first = lines[0]
    for line in lines[1:]:
        k = norm(line)
        if k == cur_key:
            cur_count += 1
        else:
            runs.append((cur_key, cur_count, cur_first))
            cur_key, cur_count, cur_first = k, 1, line
    runs.append((cur_key, cur_count, cur_first))
    for _, count, first in runs:
        if flags.get("-d") and count == 1:
            continue
        if flags.get("-u") and count > 1:
            continue
        if flags.get("-c"):
            out.append(f"{count:>7} {first}")
        else:
            out.append(first)
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return rc


def cmd_tr(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, sets = parse_flags(argv, boolean={"-d", "-s", "-c"})
    except ValueError as e:
        write_err(io_ctx, f"tr: {e}\n")
        return 2
    if not sets:
        write_err(io_ctx, b"tr: missing operand\n")
        return 1
    set1 = _expand_tr_set(sets[0])
    delete = bool(flags.get("-d"))
    squeeze = bool(flags.get("-s"))
    complement = bool(flags.get("-c"))
    set2 = _expand_tr_set(sets[1]) if len(sets) > 1 else ""
    data = io_ctx.stdin.decode("utf-8", errors="replace")
    if delete:
        if complement:
            data = "".join(c for c in data if c in set1)
        else:
            data = "".join(c for c in data if c not in set1)
    else:
        # Build translation table - missing set2 is fine when ``-s`` is set
        # (we only squeeze, no translation).
        if not set2 and not delete and not squeeze:
            write_err(io_ctx, b"tr: missing operand\n")
            return 1
        if set2 and len(set2) < len(set1):
            set2 += set2[-1] * (len(set1) - len(set2))
        if complement:
            mapping: dict[str, str] = {}
            target = set2[0] if set2 else ""
            data = "".join(target if c not in set1 else c for c in data)
        elif set2:
            mapping = dict(zip(set1, set2, strict=False))
            data = "".join(mapping.get(c, c) for c in data)
    if squeeze:
        squeeze_set = set2 if set2 else set1
        out: list[str] = []
        prev = ""
        for ch in data:
            if ch == prev and ch in squeeze_set:
                continue
            out.append(ch)
            prev = ch
        data = "".join(out)
    write_out(io_ctx, data)
    return 0


def _expand_tr_set(s: str) -> str:
    """Expand ``a-z``, ``[:lower:]`` etc."""
    classes = {
        "[:lower:]": "abcdefghijklmnopqrstuvwxyz",
        "[:upper:]": "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        "[:digit:]": "0123456789",
        "[:alpha:]": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz",
        "[:alnum:]": "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "[:space:]": " \t\n\r\v\f",
        "[:punct:]": "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~",
    }
    for cls, rep in classes.items():
        s = s.replace(cls, rep)
    out: list[str] = []
    i = 0
    while i < len(s):
        if i + 2 < len(s) and s[i + 1] == "-":
            a, b = s[i], s[i + 2]
            if ord(a) <= ord(b):
                out.extend(chr(c) for c in range(ord(a), ord(b) + 1))
                i += 3
                continue
        if s[i] == "\\" and i + 1 < len(s):
            esc = {"n": "\n", "t": "\t", "r": "\r", "\\": "\\"}.get(s[i + 1], s[i + 1])
            out.append(esc)
            i += 2
            continue
        out.append(s[i])
        i += 1
    return "".join(out)


def cmd_cut(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    try:
        flags, paths = parse_flags(argv, boolean=set(), valued={"-d", "-f", "-c", "-b"})
    except ValueError as e:
        write_err(io_ctx, f"cut: {e}\n")
        return 2
    data, rc = read_input(interp, io_ctx, paths)
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    delim = str(flags.get("-d", "\t"))
    fields = _parse_ranges(str(flags.get("-f", ""))) if "-f" in flags else None
    chars = (
        _parse_ranges(str(flags.get("-c", flags.get("-b", ""))))
        if ("-c" in flags or "-b" in flags)
        else None
    )
    out: list[str] = []
    for line in lines:
        if fields is not None:
            parts = line.split(delim)
            picked = [parts[i - 1] for i in fields if 0 < i <= len(parts)]
            out.append(delim.join(picked))
            continue
        if chars is not None:
            picked_c = "".join(line[i - 1] for i in chars if 0 < i <= len(line))
            out.append(picked_c)
            continue
        out.append(line)
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return rc


def _parse_ranges(spec: str) -> list[int]:
    """Parse ``cut`` field/char specs like ``1,3-5,7``."""
    out: list[int] = []
    seen: set[int] = set()
    for part in spec.split(","):
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            start = int(a) if a else 1
            end = int(b) if b else 1024
            for i in range(start, end + 1):
                if i not in seen:
                    out.append(i)
                    seen.add(i)
        else:
            i = int(part)
            if i not in seen:
                out.append(i)
                seen.add(i)
    return sorted(out)


def cmd_rev(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    out = "\n".join(line[::-1] for line in lines) + ("\n" if lines else "")
    write_out(io_ctx, out)
    return rc


def cmd_nl(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    data, rc = read_input(interp, io_ctx, argv[1:])
    text = data.decode("utf-8", errors="replace")
    lines = text.split("\n")
    trailing_nl = text.endswith("\n")
    if trailing_nl:
        lines = lines[:-1]
    out: list[str] = []
    n = 1
    for line in lines:
        if line == "":
            out.append("       ")
        else:
            out.append(f"{n:>6}\t{line}")
            n += 1
    write_out(io_ctx, "\n".join(out) + ("\n" if out else ""))
    return rc


__all__ = [
    "cmd_cut",
    "cmd_nl",
    "cmd_rev",
    "cmd_sort",
    "cmd_tr",
    "cmd_uniq",
]
