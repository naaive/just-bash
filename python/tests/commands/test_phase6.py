"""Phase-6 command tests: tar, zip/unzip, network stubs, du, fmt, look, tsort."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# tar
# ---------------------------------------------------------------------------


def test_tar_create_and_list(run, fs) -> None:
    fs.mkdir("/work", parents=True, exist_ok=True)
    fs.write_file("/work/a.txt", "alpha")
    fs.write_file("/work/b.txt", "beta")
    r = run("tar -cf /out.tar /work")
    assert r.exit_code == 0
    r = run("tar -tf /out.tar")
    assert r.exit_code == 0
    assert "work/a.txt" in r.stdout
    assert "work/b.txt" in r.stdout


def test_tar_extract_round_trip(run, fs) -> None:
    fs.mkdir("/src", parents=True, exist_ok=True)
    fs.write_file("/src/hello.txt", "world\n")
    run("tar -cf /backup.tar /src")
    fs.rm("/src", recursive=True, force=True)
    r = run("tar -xf /backup.tar")
    assert r.exit_code == 0
    assert fs.read_text("/src/hello.txt") == "world\n"


# ---------------------------------------------------------------------------
# zip / unzip
# ---------------------------------------------------------------------------


def test_zip_round_trip(run, fs) -> None:
    fs.write_file("/a.txt", "alpha\n")
    fs.write_file("/b.txt", "beta\n")
    r = run("zip /out.zip /a.txt /b.txt")
    assert r.exit_code == 0
    fs.rm("/a.txt")
    r = run("unzip /out.zip")
    assert r.exit_code == 0
    assert fs.read_text("/a.txt") == "alpha\n"


def test_unzip_listing(run, fs) -> None:
    fs.write_file("/x.txt", "x")
    run("zip /a.zip /x.txt")
    r = run("unzip -l /a.zip")
    assert "x.txt" in r.stdout


# ---------------------------------------------------------------------------
# Network stubs
# ---------------------------------------------------------------------------


def test_curl_returns_error_in_sandbox(run) -> None:
    r = run("curl https://example.com")
    assert r.exit_code != 0
    assert "sandbox stub" in r.stderr


def test_ping(run) -> None:
    r = run("ping example.com")
    assert "0% packet loss" in r.stdout
    assert r.exit_code == 0


def test_host_stub(run) -> None:
    r = run("host example.com")
    assert "127.0.0.1" in r.stdout


def test_dig_stub(run) -> None:
    r = run("dig example.com")
    assert "ANSWER SECTION" in r.stdout


def test_ip_addr(run) -> None:
    r = run("ip addr")
    assert "127.0.0.1" in r.stdout


# ---------------------------------------------------------------------------
# du / df / free
# ---------------------------------------------------------------------------


def test_du_simple(run, fs) -> None:
    fs.mkdir("/d", parents=True)
    fs.write_file("/d/big", b"x" * 4096)
    r = run("du /d")
    assert r.exit_code == 0
    assert "/d" in r.stdout


def test_df_stub(run) -> None:
    r = run("df")
    assert "Filesystem" in r.stdout


def test_free_stub(run) -> None:
    r = run("free")
    assert "Mem:" in r.stdout


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def test_fmt_wraps(run) -> None:
    text = "a b c d e f g h i j"
    r = run("fmt -w 5", stdin=text.encode() + b"\n")
    # Each output line should be at most 5 chars wide.
    for line in r.stdout.splitlines():
        assert len(line) <= 5


def test_look_prefix(run) -> None:
    r = run("look ba", stdin=b"apple\nbanana\nbar\nblue\n")
    assert "banana" in r.stdout
    assert "bar" in r.stdout
    assert "apple" not in r.stdout


def test_tsort(run) -> None:
    r = run("tsort", stdin=b"a b\nb c\nc d\n")
    out = r.stdout.split()
    # ``a`` must come before ``d``.
    assert out.index("a") < out.index("d")


# ---------------------------------------------------------------------------
# Display stubs
# ---------------------------------------------------------------------------


def test_tput_cols(run) -> None:
    r = run("tput cols")
    assert r.stdout.strip() == "80"


def test_clear(run) -> None:
    r = run("clear")
    assert r.exit_code == 0
    assert "\x1b[" in r.stdout


# ---------------------------------------------------------------------------
# watch dispatches
# ---------------------------------------------------------------------------


def test_watch_runs_command(run) -> None:
    r = run("watch echo hi")
    assert r.stdout == "hi\n"
    assert r.exit_code == 0


def test_watch_skips_flags(run) -> None:
    r = run("watch -n 1 echo hello")
    assert r.stdout == "hello\n"


# ---------------------------------------------------------------------------
# ps / top / lsof
# ---------------------------------------------------------------------------


def test_ps(run) -> None:
    r = run("ps")
    assert "just-bash" in r.stdout


def test_top(run) -> None:
    r = run("top")
    assert "sandbox" in r.stdout
