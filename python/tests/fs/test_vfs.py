"""In-memory filesystem behavior."""

from __future__ import annotations

import pytest

from just_bash.fs.vfs import FsError, VirtualFs


@pytest.fixture()
def fs() -> VirtualFs:
    return VirtualFs()


def test_initial_root_exists(fs: VirtualFs) -> None:
    assert fs.is_dir("/")


def test_mkdir_and_listdir(fs: VirtualFs) -> None:
    fs.mkdir("/a")
    fs.mkdir("/a/b")
    fs.mkdir("/a/c")
    assert fs.listdir("/a") == ["b", "c"]


def test_mkdir_parents(fs: VirtualFs) -> None:
    fs.mkdir("/x/y/z", parents=True)
    assert fs.is_dir("/x/y/z")


def test_mkdir_existing_without_parents_raises(fs: VirtualFs) -> None:
    fs.mkdir("/a")
    with pytest.raises(FsError):
        fs.mkdir("/a")


def test_write_and_read(fs: VirtualFs) -> None:
    fs.write_file("/file.txt", "hello")
    assert fs.read_text("/file.txt") == "hello"


def test_append(fs: VirtualFs) -> None:
    fs.write_file("/log", "a\n")
    fs.append_file("/log", "b\n")
    assert fs.read_text("/log") == "a\nb\n"


def test_rm(fs: VirtualFs) -> None:
    fs.write_file("/x", b"hi")
    fs.rm("/x")
    assert not fs.exists("/x")


def test_rm_dir_requires_recursive(fs: VirtualFs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/x", b"")
    with pytest.raises(FsError):
        fs.rm("/d")
    fs.rm("/d", recursive=True)
    assert not fs.exists("/d")


def test_rmdir_nonempty_fails(fs: VirtualFs) -> None:
    fs.mkdir("/d")
    fs.write_file("/d/x", b"")
    with pytest.raises(FsError):
        fs.rmdir("/d")


def test_touch_creates_empty(fs: VirtualFs) -> None:
    fs.touch("/empty")
    assert fs.read_file("/empty") == b""


def test_chdir_and_cwd(fs: VirtualFs) -> None:
    fs.mkdir("/sub", parents=True)
    fs.chdir("/sub")
    assert fs.cwd == "/sub"


def test_relative_path_resolution(fs: VirtualFs) -> None:
    fs.mkdir("/work", parents=True)
    fs.chdir("/work")
    fs.write_file("./hello.txt", "x")
    assert fs.read_text("/work/hello.txt") == "x"


def test_copy_file(fs: VirtualFs) -> None:
    fs.write_file("/a", "abc")
    fs.copy("/a", "/b")
    assert fs.read_text("/b") == "abc"


def test_copy_dir_recursive(fs: VirtualFs) -> None:
    fs.mkdir("/src/inner", parents=True)
    fs.write_file("/src/inner/file", "x")
    fs.copy("/src", "/dst", recursive=True)
    assert fs.read_text("/dst/inner/file") == "x"


def test_move(fs: VirtualFs) -> None:
    fs.write_file("/a", "x")
    fs.move("/a", "/b")
    assert fs.read_text("/b") == "x"
    assert not fs.exists("/a")


def test_glob_star(fs: VirtualFs) -> None:
    fs.mkdir("/g", parents=True)
    fs.write_file("/g/a.txt", "")
    fs.write_file("/g/b.txt", "")
    fs.write_file("/g/c.md", "")
    assert sorted(fs.glob("/g/*.txt")) == ["/g/a.txt", "/g/b.txt"]


def test_walk(fs: VirtualFs) -> None:
    fs.mkdir("/r/sub", parents=True)
    fs.write_file("/r/a", "")
    fs.write_file("/r/sub/b", "")
    visited = list(fs.walk("/r"))
    paths = {p for p, _, _ in visited}
    assert "/r" in paths
    assert "/r/sub" in paths
