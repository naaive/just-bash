"""POSIX-style path helpers used by the in-memory filesystem.

We deliberately reimplement these instead of using ``os.path`` so behaviour is
identical across operating systems (Windows vs POSIX). All paths are normalized
with forward slashes.
"""

from __future__ import annotations


def is_absolute(path: str) -> bool:
    return path.startswith("/")


def split_path(path: str) -> list[str]:
    """Split a path into its non-empty segments. Removes ``"."`` and resolves ``".."``."""
    parts: list[str] = []
    for segment in path.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return parts


def normalize(path: str) -> str:
    """Collapse ``"."`` / ``".."`` and double slashes; preserve absoluteness."""
    absolute = is_absolute(path)
    parts = split_path(path)
    out = "/" + "/".join(parts) if absolute else "/".join(parts) or "."
    return out


def resolve(cwd: str, path: str) -> str:
    """Resolve ``path`` against ``cwd`` (absolute by convention)."""
    if is_absolute(path):
        return normalize(path)
    if not is_absolute(cwd):
        cwd = "/" + cwd
    return normalize(cwd.rstrip("/") + "/" + path)


def join(*parts: str) -> str:
    """``os.path.join``-like, but always with forward slashes."""
    if not parts:
        return ""
    out = parts[0]
    for p in parts[1:]:
        if not p:
            continue
        if p.startswith("/"):
            out = p
        else:
            out = out.rstrip("/") + "/" + p
    return out


def dirname(path: str) -> str:
    n = normalize(path)
    if n in ("/", ""):
        return n or "/"
    idx = n.rfind("/")
    if idx <= 0:
        return "/" if n.startswith("/") else "."
    return n[:idx]


def basename(path: str) -> str:
    n = normalize(path)
    if n == "/":
        return ""
    return n.rsplit("/", 1)[-1]


__all__ = [
    "basename",
    "dirname",
    "is_absolute",
    "join",
    "normalize",
    "resolve",
    "split_path",
]
