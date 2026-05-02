"""Tests for the phase-3 commands."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# base64
# ---------------------------------------------------------------------------


def test_base64_encode(run) -> None:
    r = run("printf hello | base64")
    assert r.stdout == "aGVsbG8=\n"


def test_base64_decode(run) -> None:
    r = run("echo aGVsbG8= | base64 -d")
    assert r.stdout == "hello"


# ---------------------------------------------------------------------------
# hexdump / xxd
# ---------------------------------------------------------------------------


def test_hexdump_canonical(run) -> None:
    r = run("printf hi | hexdump -C")
    assert r.stdout.startswith("00000000  68 69")
    assert "|hi|" in r.stdout


def test_xxd(run) -> None:
    r = run("printf hi | xxd")
    assert "6869" in r.stdout
    assert r.stdout.startswith("00000000:")


def test_xxd_p_plain(run) -> None:
    r = run("printf abc | xxd -p")
    assert r.stdout.strip() == "616263"


def test_xxd_revert(run) -> None:
    r = run("echo 68656c6c6f | xxd -r -p")
    assert r.stdout == "hello"


# ---------------------------------------------------------------------------
# column
# ---------------------------------------------------------------------------


def test_column_aligns(run) -> None:
    r = run("printf 'a b\\ncc d\\n' | column -t")
    assert "a   b" in r.stdout or "a  b" in r.stdout
    assert "cc  d" in r.stdout


# ---------------------------------------------------------------------------
# shuf / tac
# ---------------------------------------------------------------------------


def test_shuf_returns_all_lines(run) -> None:
    r = run("printf '1\\n2\\n3\\n' | shuf")
    assert sorted(r.stdout.split()) == ["1", "2", "3"]


def test_tac_reverses(run) -> None:
    r = run("printf 'a\\nb\\nc\\n' | tac")
    assert r.stdout == "c\nb\na\n"


# ---------------------------------------------------------------------------
# split
# ---------------------------------------------------------------------------


def test_split_two_lines_per_chunk(run, fs) -> None:
    fs.mkdir("/work", parents=True, exist_ok=True)
    fs.chdir("/work")
    fs.write_file("/work/in", "a\nb\nc\nd\ne\n")
    r = run("split -l 2 in part_")
    assert r.exit_code == 0
    assert fs.read_text("/work/part_aa") == "a\nb\n"
    assert fs.read_text("/work/part_ab") == "c\nd\n"


# ---------------------------------------------------------------------------
# join
# ---------------------------------------------------------------------------


def test_join_basic(run, fs) -> None:
    fs.write_file("/a", "1 alpha\n2 beta\n3 gamma\n")
    fs.write_file("/b", "1 one\n2 two\n3 three\n")
    r = run("join /a /b")
    assert r.stdout == "1 alpha one\n2 beta two\n3 gamma three\n"


# ---------------------------------------------------------------------------
# system info
# ---------------------------------------------------------------------------


def test_hostname(run) -> None:
    r = run("hostname")
    assert r.stdout.strip() == "sandbox"


def test_whoami_default(run) -> None:
    r = run("whoami")
    assert r.stdout.strip() == "user"


def test_id_default(run) -> None:
    r = run("id")
    assert "uid=1000" in r.stdout


def test_uname(run) -> None:
    r = run("uname")
    assert r.stdout.strip() == "Linux"


def test_uname_a(run) -> None:
    r = run("uname -a")
    assert "Linux" in r.stdout
    assert "x86_64" in r.stdout


def test_getent_passwd(run) -> None:
    r = run("getent passwd")
    assert "user:" in r.stdout


# ---------------------------------------------------------------------------
# file
# ---------------------------------------------------------------------------


def test_file_text(run, fs) -> None:
    fs.write_file("/x.txt", "hello\n")
    r = run("file /x.txt")
    assert "text" in r.stdout


def test_file_data(run, fs) -> None:
    fs.write_file("/x.bin", b"\x00\x01\x02")
    r = run("file /x.bin")
    assert "data" in r.stdout


# ---------------------------------------------------------------------------
# jq
# ---------------------------------------------------------------------------


def test_jq_identity(run) -> None:
    r = run("echo '{\"a\":1}' | jq .")
    assert "1" in r.stdout


def test_jq_field(run) -> None:
    r = run('echo \'{"name":"alice"}\' | jq -r .name')
    assert r.stdout == "alice\n"


def test_jq_nested(run) -> None:
    r = run('echo \'{"a":{"b":42}}\' | jq .a.b')
    assert r.stdout.strip() == "42"


def test_jq_array_index(run) -> None:
    r = run("echo '[10, 20, 30]' | jq '.[1]'")
    assert r.stdout.strip() == "20"


def test_jq_length(run) -> None:
    r = run("echo '[1,2,3,4]' | jq length")
    assert r.stdout.strip() == "4"
