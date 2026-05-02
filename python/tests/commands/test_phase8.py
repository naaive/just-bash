"""Phase-8 command tests."""

from __future__ import annotations


def test_nproc(run) -> None:
    r = run("nproc")
    assert r.stdout.strip() == "4"


def test_timeout_dispatches(run) -> None:
    r = run("timeout 5 echo hi")
    assert r.stdout == "hi\n"


def test_rsync_stub(run) -> None:
    r = run("rsync src dst")
    assert "rsync requested" in r.stdout
    assert r.exit_code == 0


def test_ssh_stub(run) -> None:
    r = run("ssh host echo hi")
    assert r.exit_code == 255
    assert "ssh requested" in r.stdout


def test_chmod_octal(run, fs) -> None:
    fs.write_file("/x", "")
    r = run("chmod 755 /x")
    assert r.exit_code == 0
    assert fs.stat("/x").mode == 0o755


def test_chmod_recursive(run, fs) -> None:
    fs.mkdir("/d", parents=True)
    fs.write_file("/d/a", "")
    fs.write_file("/d/b", "")
    r = run("chmod -R 700 /d")
    assert r.exit_code == 0
    assert fs.stat("/d/a").mode == 0o700


def test_chown_succeeds(run, fs) -> None:
    fs.write_file("/x", "")
    r = run("chown user:group /x")
    assert r.exit_code == 0


def test_readlink_canonical(run, fs) -> None:
    fs.mkdir("/a/b", parents=True)
    fs.write_file("/a/b/file", "")
    r = run("cd /a; readlink b/file")
    assert r.stdout == "/a/b/file\n"


def test_sync(run) -> None:
    r = run("sync")
    assert r.exit_code == 0


def test_strings(run, fs) -> None:
    fs.write_file("/bin", b"\x00abcd\x00wxyz\x00\x01\x02")
    r = run("strings /bin")
    assert "abcd" in r.stdout
    assert "wxyz" in r.stdout


def test_command_v(run) -> None:
    r = run("command -v echo")
    # echo is a builtin.
    assert r.stdout.strip() == "echo"


def test_jot(run) -> None:
    r = run("jot 1 5")
    # ``jot`` is a thin BSD-style alias for our seq.
    assert r.stdout.startswith("1\n")


# ---------------------------------------------------------------------------
# select keyword
# ---------------------------------------------------------------------------


def test_select_iterates(run) -> None:
    r = run('select x in a b c; do echo "$x"; done')
    assert r.stdout == "a\nb\nc\n"


# ---------------------------------------------------------------------------
# ANSI-C $'...'
# ---------------------------------------------------------------------------


def test_ansi_c_newline(run) -> None:
    r = run("printf '%s\\n' $'a\\nb'")
    # ``a\nb`` in $'...' becomes a literal newline.
    assert r.stdout == "a\nb\n"


def test_ansi_c_tab(run) -> None:
    r = run("echo $'col1\\tcol2'")
    assert r.stdout == "col1\tcol2\n"


def test_ansi_c_hex(run) -> None:
    r = run("echo $'\\x41\\x42\\x43'")
    assert r.stdout == "ABC\n"
