"""Overlay filesystem.

``OverlayFs`` implements a copy-on-write veneer over a real filesystem root:

* Reads fall through to the real FS unless the path was overlaid or deleted.
* Writes go to an in-memory overlay tree (the real FS is never modified).
* Deletions are tracked as "whiteouts" so a subsequent read returns ENOENT.
* Symlinks are denied by default (``allowSymlinks=False``); paths whose
  canonical form escapes the configured root are also rejected.

This is a security-sensitive component: callers route untrusted scripts
through ``OverlayFs`` to read project files without letting them mutate the
host. The default-deny symlink policy mirrors the TypeScript implementation
in ``packages/just-bash/src/fs/overlay-fs.ts``.
"""

from __future__ import annotations

import os
import stat as _stat
import time
from collections.abc import Iterator
from pathlib import Path

from just_bash.fs import path_utils
from just_bash.fs.vfs import Directory, File, FsError, FsNode


class OverlayFs:
    """Read-through real-FS root + in-memory write/delete overlay."""

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        allow_symlinks: bool = False,
        allow_writes: bool = True,
    ) -> None:
        root_path = Path(root).resolve()
        if not root_path.is_dir():
            raise FsError("ENOTDIR", str(root_path), "overlay root must be a directory")
        self._root = str(root_path)
        self._allow_symlinks = allow_symlinks
        self._allow_writes = allow_writes
        self._overlay = Directory(name="")  # in-memory overrides
        self._whiteouts: set[str] = set()  # paths marked as deleted
        self._cwd = "/"

    # ------------------------------------------------------------- properties
    @property
    def cwd(self) -> str:
        return self._cwd

    @property
    def root(self) -> str:
        return self._root

    def chdir(self, path: str) -> None:
        target = self._resolve(path)
        if not self.is_dir(target):
            raise FsError("ENOTDIR", target, "not a directory")
        self._cwd = target

    def _resolve(self, path: str) -> str:
        return path_utils.resolve(self._cwd, path)

    # ------------------------------------------------------ overlay lookups
    def _whiteout(self, path: str) -> bool:
        return path in self._whiteouts or any(
            path == w or path.startswith(w + "/") for w in self._whiteouts
        )

    def _overlay_lookup(self, path: str) -> FsNode | None:
        """Return the overlay node for ``path`` or ``None``."""
        if path == "/":
            return self._overlay
        cur: Directory = self._overlay
        for segment in path_utils.split_path(path):
            child = cur.children.get(segment)
            if child is None:
                return None
            if not isinstance(child, Directory):
                return child
            cur = child
        return cur

    def _ensure_overlay_dir(self, path: str) -> Directory:
        cur = self._overlay
        for segment in path_utils.split_path(path):
            child = cur.children.get(segment)
            if child is None:
                child = Directory(name=segment)
                cur.children[segment] = child
            elif not isinstance(child, Directory):
                raise FsError("ENOTDIR", path, f"not a directory: {segment}")
            cur = child
        return cur

    # ---------------------------------------------------- real-fs path safety
    def _real_path(self, path: str) -> str | None:
        """Return a sanitized real-FS path or ``None`` if the entry is hidden.

        Returns ``None`` when the path was whited-out or its real-FS canonical
        form escapes the overlay root (symlink traversal, ``..``, etc.).
        """
        if self._whiteout(path):
            return None
        candidate = self._root + path  # path is absolute, starts with /
        try:
            real = os.path.realpath(candidate, strict=False)
        except OSError:
            return None
        # Symlink default-deny: if the canonical path differs from the
        # naively-joined path, a symlink was traversed somewhere.
        if not self._allow_symlinks:
            naive = os.path.normpath(candidate)
            if real != naive:
                return None
        # Containment check: real must stay under root.
        if real != self._root and not real.startswith(self._root + os.sep):
            return None
        return candidate

    def _real_stat(self, path: str) -> os.stat_result | None:
        real = self._real_path(path)
        if real is None:
            return None
        try:
            if self._allow_symlinks:
                return os.stat(real)
            return os.lstat(real)
        except OSError:
            return None

    # -------------------------------------------------------------- queries
    def exists(self, path: str) -> bool:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            return False
        if self._overlay_lookup(absolute) is not None:
            return True
        return self._real_stat(absolute) is not None

    def is_file(self, path: str) -> bool:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            return False
        node = self._overlay_lookup(absolute)
        if node is not None:
            return isinstance(node, File)
        st = self._real_stat(absolute)
        return st is not None and _stat.S_ISREG(st.st_mode)

    def is_dir(self, path: str) -> bool:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            return False
        node = self._overlay_lookup(absolute)
        if node is not None:
            return isinstance(node, Directory)
        st = self._real_stat(absolute)
        return st is not None and _stat.S_ISDIR(st.st_mode)

    def stat(self, path: str) -> FsNode:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            raise FsError("ENOENT", absolute, "no such file or directory")
        node = self._overlay_lookup(absolute)
        if node is not None:
            return node
        st = self._real_stat(absolute)
        if st is None:
            raise FsError("ENOENT", absolute, "no such file or directory")
        if _stat.S_ISDIR(st.st_mode):
            return Directory(name=path_utils.basename(absolute), mode=_stat.S_IMODE(st.st_mode))
        try:
            content = self._read_real_file(absolute)
        except FsError:
            content = b""
        return File(
            name=path_utils.basename(absolute),
            mode=_stat.S_IMODE(st.st_mode),
            mtime=st.st_mtime,
            content=content,
        )

    def listdir(self, path: str) -> list[str]:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            raise FsError("ENOENT", absolute, "no such file or directory")
        names: set[str] = set()
        # Real entries.
        real = self._real_path(absolute)
        if real is not None:
            try:
                for entry in os.scandir(real):
                    full = path_utils.join(absolute, entry.name)
                    if self._whiteout(full):
                        continue
                    names.add(entry.name)
            except OSError:
                pass
        # Overlay entries.
        node = self._overlay_lookup(absolute)
        if isinstance(node, Directory):
            for n in node.children:
                full = path_utils.join(absolute, n)
                if not self._whiteout(full):
                    names.add(n)
        if not names and (real is None and node is None):
            raise FsError("ENOENT", absolute, "no such file or directory")
        return sorted(names)

    # -------------------------------------------------------------- reads
    def read_file(self, path: str) -> bytes:
        absolute = self._resolve(path)
        if self._whiteout(absolute):
            raise FsError("ENOENT", absolute, "no such file or directory")
        node = self._overlay_lookup(absolute)
        if isinstance(node, File):
            return node.content
        if isinstance(node, Directory):
            raise FsError("EISDIR", absolute, "is a directory")
        return self._read_real_file(absolute)

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_file(path).decode(encoding)

    def _read_real_file(self, path: str) -> bytes:
        real = self._real_path(path)
        if real is None:
            raise FsError("ENOENT", path, "no such file or directory")
        try:
            # ``O_NOFOLLOW`` prevents symlink-swap TOCTOU races.
            flags = os.O_RDONLY
            if not self._allow_symlinks and hasattr(os, "O_NOFOLLOW"):
                flags |= os.O_NOFOLLOW
            fd = os.open(real, flags)
        except OSError as e:
            raise FsError("ENOENT", path, str(e)) from e
        try:
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                chunks.append(chunk)
            return b"".join(chunks)
        finally:
            os.close(fd)

    # -------------------------------------------------------------- writes
    def _check_writes(self) -> None:
        if not self._allow_writes:
            raise FsError("EROFS", "/", "writes not allowed on this overlay")

    def mkdir(
        self,
        path: str,
        *,
        parents: bool = False,
        exist_ok: bool = False,
        mode: int = 0o755,
    ) -> None:
        self._check_writes()
        absolute = self._resolve(path)
        if absolute == "/":
            if exist_ok:
                return
            raise FsError("EEXIST", absolute, "file exists")
        parts = path_utils.split_path(absolute)
        cur = self._overlay
        for i, segment in enumerate(parts):
            child = cur.children.get(segment)
            full = "/" + "/".join(parts[: i + 1])
            is_last = i == len(parts) - 1
            if child is None:
                # Real-FS may already have it.
                if self._real_stat(full) is not None and not self._whiteout(full):
                    if not is_last:
                        # Materialize a dir entry on the overlay.
                        child = Directory(name=segment, mode=mode)
                        cur.children[segment] = child
                        cur = child
                        continue
                    if not parents and not exist_ok:
                        raise FsError("EEXIST", absolute, "file exists")
                    return
                if not is_last and not parents:
                    raise FsError("ENOENT", absolute, f"no such file or directory: {segment}")
                child = Directory(name=segment, mode=mode)
                cur.children[segment] = child
                self._whiteouts.discard(full)
                cur = child
                continue
            if not isinstance(child, Directory):
                raise FsError("ENOTDIR", absolute, f"not a directory: {segment}")
            if is_last and not parents and not exist_ok:
                raise FsError("EEXIST", absolute, "file exists")
            cur = child

    def write_file(self, path: str, data: bytes | str, *, mode: int = 0o644) -> None:
        self._check_writes()
        if isinstance(data, str):
            data = data.encode("utf-8")
        absolute = self._resolve(path)
        parent_path = path_utils.dirname(absolute)
        # Ensure the overlay parent dir exists (creating shadow dirs as we go).
        if parent_path and parent_path != "/":
            if not (self.is_dir(parent_path) or self._overlay_lookup(parent_path)):
                raise FsError("ENOENT", parent_path, "no such file or directory")
            parent = self._ensure_overlay_dir(parent_path)
        else:
            parent = self._overlay
        name = path_utils.basename(absolute)
        existing = parent.children.get(name)
        if isinstance(existing, Directory):
            raise FsError("EISDIR", absolute, "is a directory")
        parent.children[name] = File(name=name, content=data, mode=mode, mtime=time.time())
        self._whiteouts.discard(absolute)

    def append_file(self, path: str, data: bytes | str) -> None:
        try:
            existing = self.read_file(path)
        except FsError:
            existing = b""
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.write_file(path, existing + data)

    def touch(self, path: str) -> None:
        try:
            self.stat(path)
        except FsError:
            self.write_file(path, b"")

    def rm(self, path: str, *, recursive: bool = False, force: bool = False) -> None:
        self._check_writes()
        absolute = self._resolve(path)
        if not self.exists(absolute):
            if force:
                return
            raise FsError("ENOENT", absolute, "no such file or directory")
        if self.is_dir(absolute) and not recursive:
            raise FsError("EISDIR", absolute, "is a directory")
        # Remove from overlay if present, then mark whiteout for real-FS.
        parent = self._overlay_lookup(path_utils.dirname(absolute))
        if isinstance(parent, Directory):
            parent.children.pop(path_utils.basename(absolute), None)
        self._whiteouts.add(absolute)

    def rmdir(self, path: str) -> None:
        self._check_writes()
        absolute = self._resolve(path)
        if not self.is_dir(absolute):
            raise FsError("ENOTDIR", absolute, "not a directory")
        if self.listdir(absolute):
            raise FsError("ENOTEMPTY", absolute, "directory not empty")
        parent = self._overlay_lookup(path_utils.dirname(absolute))
        if isinstance(parent, Directory):
            parent.children.pop(path_utils.basename(absolute), None)
        self._whiteouts.add(absolute)

    def copy(self, src: str, dst: str, *, recursive: bool = False) -> None:
        self._check_writes()
        if self.is_dir(src):
            if not recursive:
                raise FsError("EISDIR", src, "is a directory")
            self.mkdir(dst, parents=True, exist_ok=True)
            for entry in self.listdir(src):
                self.copy(
                    path_utils.join(src, entry),
                    path_utils.join(dst, entry),
                    recursive=True,
                )
            return
        data = self.read_file(src)
        self.write_file(dst, data)

    def move(self, src: str, dst: str) -> None:
        self._check_writes()
        if self.is_dir(dst):
            dst = path_utils.join(dst, path_utils.basename(self._resolve(src)))
        if self.is_dir(src):
            self.copy(src, dst, recursive=True)
        else:
            self.write_file(dst, self.read_file(src))
        self.rm(src, recursive=True, force=True)

    # --------------------------------------------------------------- traversal
    def walk(self, path: str = ".") -> Iterator[tuple[str, list[str], list[str]]]:
        absolute = self._resolve(path)
        if not self.is_dir(absolute):
            raise FsError("ENOTDIR", absolute, "not a directory")
        stack: list[str] = [absolute]
        while stack:
            cur = stack.pop()
            entries = self.listdir(cur)
            dirs: list[str] = []
            files: list[str] = []
            for name in entries:
                full = path_utils.join(cur, name)
                if self.is_dir(full):
                    dirs.append(name)
                else:
                    files.append(name)
            yield cur, dirs, files
            for d in reversed(dirs):
                stack.append(path_utils.join(cur, d))

    def glob(self, pattern: str) -> list[str]:
        import fnmatch

        if not pattern:
            return []
        absolute = path_utils.is_absolute(pattern)
        base = "/" if absolute else self._cwd
        rel = pattern.lstrip("/") if absolute else pattern
        segments = rel.split("/")
        results: list[str] = []
        self._glob_walk(base, segments, results, fnmatch.fnmatchcase)
        return sorted(results)

    def _glob_walk(self, base: str, segments: list[str], out: list[str], match) -> None:  # type: ignore[no-untyped-def]
        if not segments:
            return
        head, *rest = segments
        if head == "**":
            self._glob_walk(base, rest, out, match)
            if not self.is_dir(base):
                return
            for name in self.listdir(base):
                child_path = path_utils.join(base, name)
                if self.is_dir(child_path):
                    self._glob_walk(child_path, ["**", *rest], out, match)
            return
        if not self.is_dir(base):
            return
        for name in self.listdir(base):
            if not match(name, head):
                continue
            child_path = path_utils.join(base, name)
            if rest:
                self._glob_walk(child_path, rest, out, match)
            else:
                out.append(child_path)


__all__ = ["OverlayFs"]
