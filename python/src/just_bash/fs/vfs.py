"""In-memory virtual filesystem.

Provides a tree of ``Directory`` and ``File`` nodes accessed via POSIX-style
paths. Supports the operations needed by the interpreter and the commands we
ship in the MVP - read/write, directory listing, mkdir/rmdir, copy, move,
glob, recursive walk.

Permissions and timestamps exist on each node but are not enforced (cheap to
implement and matches bash's "if you can read the FS you own it" model in a
sandbox).
"""

from __future__ import annotations

import fnmatch
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from just_bash.fs import path_utils


class FsError(OSError):
    """Raised by VFS operations. ``errno`` mirrors ``errno.ENOENT`` etc."""

    def __init__(self, code: str, path: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.path = path

    def __str__(self) -> str:
        return f"{self.code}: {self.path}: {self.args[0]}"


@dataclass(slots=True)
class FsNode:
    name: str
    mode: int = 0o644
    mtime: float = field(default_factory=time.time)


@dataclass(slots=True)
class File(FsNode):
    content: bytes = b""

    @property
    def size(self) -> int:
        return len(self.content)


@dataclass(slots=True)
class Directory(FsNode):
    children: dict[str, FsNode] = field(default_factory=dict)
    mode: int = 0o755


class VirtualFs:
    """Mutable, in-memory POSIX-style filesystem rooted at ``/``."""

    def __init__(self) -> None:
        self.root = Directory(name="")
        self._cwd = "/"

    # --------------------------------------------------------------- cwd / pwd
    @property
    def cwd(self) -> str:
        return self._cwd

    def chdir(self, path: str) -> None:
        target = self._resolve(path)
        node = self._lookup(target)
        if not isinstance(node, Directory):
            raise FsError("ENOTDIR", target, "not a directory")
        self._cwd = target

    def _resolve(self, path: str) -> str:
        return path_utils.resolve(self._cwd, path)

    # ------------------------------------------------------------- node access
    def _walk(self, path: str, *, follow: bool = True) -> tuple[Directory, str, FsNode | None]:
        """Return (parent_dir, leaf_name, node_or_none) for the given path.

        Used internally by mutators. Raises ``FsError`` if a parent component
        is missing or non-directory.
        """
        del follow  # Symlinks aren't supported in MVP.
        absolute = self._resolve(path)
        if absolute == "/":
            return self.root, "", self.root
        parts = path_utils.split_path(absolute)
        cur = self.root
        for segment in parts[:-1]:
            child = cur.children.get(segment)
            if child is None:
                raise FsError("ENOENT", absolute, f"no such file or directory: {segment}")
            if not isinstance(child, Directory):
                raise FsError("ENOTDIR", absolute, f"not a directory: {segment}")
            cur = child
        leaf = parts[-1]
        node = cur.children.get(leaf)
        return cur, leaf, node

    def _lookup(self, path: str) -> FsNode:
        _, _, node = self._walk(path)
        if node is None:
            raise FsError("ENOENT", path, "no such file or directory")
        return node

    # ----------------------------------------------------------------- queries
    def exists(self, path: str) -> bool:
        try:
            self._lookup(path)
        except FsError:
            return False
        return True

    def is_file(self, path: str) -> bool:
        try:
            return isinstance(self._lookup(path), File)
        except FsError:
            return False

    def is_dir(self, path: str) -> bool:
        try:
            return isinstance(self._lookup(path), Directory)
        except FsError:
            return False

    def stat(self, path: str) -> FsNode:
        return self._lookup(path)

    def listdir(self, path: str) -> list[str]:
        node = self._lookup(path)
        if not isinstance(node, Directory):
            raise FsError("ENOTDIR", path, "not a directory")
        return sorted(node.children.keys())

    # --------------------------------------------------------------- mutators
    def mkdir(
        self, path: str, *, parents: bool = False, exist_ok: bool = False, mode: int = 0o755
    ) -> None:
        absolute = self._resolve(path)
        if absolute == "/":
            if exist_ok:
                return
            raise FsError("EEXIST", absolute, "file exists")
        parts = path_utils.split_path(absolute)
        cur: Directory = self.root
        for i, segment in enumerate(parts):
            child = cur.children.get(segment)
            is_last = i == len(parts) - 1
            if child is None:
                if not is_last and not parents:
                    raise FsError("ENOENT", absolute, f"no such file or directory: {segment}")
                new = Directory(name=segment, mode=mode)
                cur.children[segment] = new
                cur = new
                continue
            if not isinstance(child, Directory):
                raise FsError("ENOTDIR", absolute, f"not a directory: {segment}")
            if is_last and not parents and not exist_ok:
                raise FsError("EEXIST", absolute, "file exists")
            cur = child

    def rmdir(self, path: str) -> None:
        parent, name, node = self._walk(path)
        if node is None:
            raise FsError("ENOENT", path, "no such file or directory")
        if not isinstance(node, Directory):
            raise FsError("ENOTDIR", path, "not a directory")
        if node.children:
            raise FsError("ENOTEMPTY", path, "directory not empty")
        del parent.children[name]

    def rm(self, path: str, *, recursive: bool = False, force: bool = False) -> None:
        try:
            parent, name, node = self._walk(path)
        except FsError:
            if force:
                return
            raise
        if node is None:
            if force:
                return
            raise FsError("ENOENT", path, "no such file or directory")
        if isinstance(node, Directory):
            if not recursive:
                raise FsError("EISDIR", path, "is a directory")
            node.children.clear()
        del parent.children[name]

    def write_file(self, path: str, data: bytes | str, *, mode: int = 0o644) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        parent, name, node = self._walk(path)
        if node is None:
            parent.children[name] = File(name=name, content=data, mode=mode)
        elif isinstance(node, File):
            node.content = data
            node.mtime = time.time()
        else:
            raise FsError("EISDIR", path, "is a directory")

    def append_file(self, path: str, data: bytes | str) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        parent, name, node = self._walk(path)
        if node is None:
            parent.children[name] = File(name=name, content=data)
        elif isinstance(node, File):
            node.content += data
            node.mtime = time.time()
        else:
            raise FsError("EISDIR", path, "is a directory")

    def read_file(self, path: str) -> bytes:
        node = self._lookup(path)
        if not isinstance(node, File):
            raise FsError("EISDIR", path, "is a directory")
        return node.content

    def read_text(self, path: str, encoding: str = "utf-8") -> str:
        return self.read_file(path).decode(encoding)

    def touch(self, path: str) -> None:
        try:
            node = self._lookup(path)
            node.mtime = time.time()
        except FsError as e:
            if e.code != "ENOENT":
                raise
            self.write_file(path, b"")

    def copy(self, src: str, dst: str, *, recursive: bool = False) -> None:
        node = self._lookup(src)
        if isinstance(node, Directory):
            if not recursive:
                raise FsError("EISDIR", src, "is a directory")
            target = self._copy_target(src, dst, is_dir=True)
            self.mkdir(target, parents=False, exist_ok=True, mode=node.mode)
            for child_name in list(node.children):
                self.copy(
                    path_utils.join(src, child_name),
                    path_utils.join(target, child_name),
                    recursive=True,
                )
            return
        target = self._copy_target(src, dst, is_dir=False)
        assert isinstance(node, File)
        self.write_file(target, node.content, mode=node.mode)

    def move(self, src: str, dst: str) -> None:
        src_abs = self._resolve(src)
        dst_abs = self._resolve(dst)
        if self.is_dir(dst_abs):
            dst_abs = path_utils.join(dst_abs, path_utils.basename(src_abs))
        node = self._lookup(src_abs)
        src_parent, src_name, _ = self._walk(src_abs)
        dst_parent, dst_name, _ = self._walk(dst_abs)
        if dst_name == "":
            raise FsError("EINVAL", dst_abs, "invalid move target")
        node.name = dst_name
        dst_parent.children[dst_name] = node
        if src_parent is not dst_parent or src_name != dst_name:
            del src_parent.children[src_name]

    def _copy_target(self, src: str, dst: str, *, is_dir: bool) -> str:
        dst_abs = self._resolve(dst)
        if self.is_dir(dst_abs):
            return path_utils.join(dst_abs, path_utils.basename(self._resolve(src)))
        del is_dir
        return dst_abs

    # --------------------------------------------------------------- traversal
    def walk(self, path: str = ".") -> Iterator[tuple[str, list[str], list[str]]]:
        """Yield ``(dirpath, dirnames, filenames)`` like ``os.walk``."""
        absolute = self._resolve(path)
        node = self._lookup(absolute)
        if not isinstance(node, Directory):
            raise FsError("ENOTDIR", absolute, "not a directory")
        stack: list[tuple[str, Directory]] = [(absolute, node)]
        while stack:
            cur_path, cur = stack.pop()
            dirs: list[str] = []
            files: list[str] = []
            for child_name, child in sorted(cur.children.items()):
                if isinstance(child, Directory):
                    dirs.append(child_name)
                else:
                    files.append(child_name)
            yield cur_path, dirs, files
            for d in reversed(dirs):
                stack.append((path_utils.join(cur_path, d), cur.children[d]))  # type: ignore[arg-type]

    def glob(self, pattern: str) -> list[str]:
        """POSIX-style globbing. Supports ``*``, ``?``, ``[abc]``, and ``**``."""
        if not pattern:
            return []
        absolute = path_utils.is_absolute(pattern)
        base = "/" if absolute else self._cwd
        rel = pattern.lstrip("/") if absolute else pattern
        segments = rel.split("/")
        results: list[str] = []
        self._glob_walk(base, segments, results)
        return sorted(results)

    def _glob_walk(self, base: str, segments: list[str], out: list[str]) -> None:
        if not segments:
            return
        head, *rest = segments
        if head == "**":
            # Match zero or more directory levels.
            self._glob_walk(base, rest, out)
            try:
                node = self._lookup(base)
            except FsError:
                return
            if not isinstance(node, Directory):
                return
            for name, child in node.children.items():
                child_path = path_utils.join(base, name)
                if isinstance(child, Directory):
                    self._glob_walk(child_path, ["**", *rest], out)
            return
        try:
            node = self._lookup(base)
        except FsError:
            return
        if not isinstance(node, Directory):
            return
        for name in node.children:
            if not fnmatch.fnmatchcase(name, head):
                continue
            child_path = path_utils.join(base, name)
            if rest:
                self._glob_walk(child_path, rest, out)
            else:
                out.append(child_path)


__all__ = ["Directory", "File", "FsError", "FsNode", "VirtualFs"]
