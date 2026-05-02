"""OverlayFs behaviour tests including default-deny-symlink security."""

from __future__ import annotations

from pathlib import Path

import pytest

from just_bash.fs.overlay_fs import OverlayFs
from just_bash.fs.vfs import FsError


@pytest.fixture()
def real_root(tmp_path: Path) -> Path:
    """A populated real-FS directory the overlay can read from."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text('print("hello")\n')
    (tmp_path / "src" / "lib").mkdir()
    (tmp_path / "src" / "lib" / "util.py").write_text("# util\n")
    (tmp_path / "README.md").write_text("# readme\n")
    return tmp_path


def test_reads_real_files(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    assert fs.exists("/README.md")
    assert fs.read_text("/README.md") == "# readme\n"
    assert fs.is_dir("/src")
    assert fs.is_file("/src/main.py")


def test_listdir_combines_real_and_overlay(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.write_file("/src/extra.py", "x")
    entries = fs.listdir("/src")
    assert "main.py" in entries
    assert "extra.py" in entries
    assert "lib" in entries


def test_writes_go_to_overlay_only(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.write_file("/new.txt", "from overlay")
    assert fs.read_text("/new.txt") == "from overlay"
    # Real FS untouched.
    assert not (real_root / "new.txt").exists()


def test_overlay_shadows_real_file(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.write_file("/README.md", "shadowed")
    assert fs.read_text("/README.md") == "shadowed"
    # Real file still has its original content.
    assert (real_root / "README.md").read_text() == "# readme\n"


def test_rm_creates_whiteout(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.rm("/src/main.py")
    assert not fs.exists("/src/main.py")
    # Real file still on disk.
    assert (real_root / "src" / "main.py").exists()


def test_rm_recursive_dir(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.rm("/src", recursive=True)
    assert not fs.exists("/src")
    assert not fs.exists("/src/main.py")


def test_listdir_skips_whiteouts(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.rm("/README.md")
    assert "README.md" not in fs.listdir("/")


def test_walk_visits_real_and_overlay(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.write_file("/src/extra.py", "x")
    seen: set[str] = set()
    for dirpath, _dirs, files in fs.walk("/"):
        for f in files:
            seen.add(dirpath.rstrip("/") + "/" + f)
    assert "/src/main.py" in seen
    assert "/src/extra.py" in seen
    assert "/README.md" in seen


def test_symlink_traversal_blocked_by_default(tmp_path: Path) -> None:
    # Layout: /work/inside.txt and a symlink /work/escape -> /etc/passwd.
    work = tmp_path / "work"
    work.mkdir()
    (work / "inside.txt").write_text("ok")
    (work / "escape").symlink_to("/etc/passwd")
    fs = OverlayFs(work)
    assert fs.exists("/inside.txt")
    # Path through the symlink is hidden by the default-deny policy.
    assert fs.read_text("/inside.txt") == "ok"
    with pytest.raises(FsError):
        fs.read_text("/escape")


def test_symlink_explicit_allow(tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / "target").write_text("hi")
    (work / "link").symlink_to("target")
    fs = OverlayFs(work, allow_symlinks=True)
    assert fs.read_text("/link") == "hi"


def test_dotdot_escape_blocked(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    # ``../etc/passwd`` should normalize within root and not escape.
    with pytest.raises(FsError):
        fs.read_text("/../etc/passwd")


def test_glob_across_layers(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.write_file("/src/extra.py", "x")
    matches = fs.glob("/src/*.py")
    assert sorted(matches) == ["/src/extra.py", "/src/main.py"]


def test_readonly_overlay_rejects_writes(real_root: Path) -> None:
    fs = OverlayFs(real_root, allow_writes=False)
    with pytest.raises(FsError):
        fs.write_file("/should_fail", "x")


def test_chdir_and_relative_read(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.chdir("/src")
    assert fs.read_text("main.py") == 'print("hello")\n'


def test_root_must_be_directory(tmp_path: Path) -> None:
    bad = tmp_path / "not-a-dir"
    bad.write_text("file")
    with pytest.raises(FsError):
        OverlayFs(bad)


def test_overlay_after_dir_shadowed_real_dir(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.mkdir("/src/new_subdir")
    assert fs.is_dir("/src/new_subdir")
    fs.write_file("/src/new_subdir/inside", "yes")
    assert fs.read_text("/src/new_subdir/inside") == "yes"
    # Original entries still visible.
    assert "main.py" in fs.listdir("/src")


def test_recreate_after_rm(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    fs.rm("/README.md")
    assert not fs.exists("/README.md")
    fs.write_file("/README.md", "fresh")
    assert fs.read_text("/README.md") == "fresh"


def test_real_root_is_canonicalised(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    (nested / "x").write_text("y")
    fs = OverlayFs(nested)
    assert fs.read_text("/x") == "y"


def test_write_to_path_with_missing_parent_fails(real_root: Path) -> None:
    fs = OverlayFs(real_root)
    with pytest.raises(FsError):
        fs.write_file("/no/such/dir/file", "x")
