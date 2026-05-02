"""Phase-10 command tests."""

from __future__ import annotations


def test_more_passes_through(run, fs) -> None:
    fs.write_file("/x", "hello\nworld\n")
    r = run("more /x")
    assert r.stdout == "hello\nworld\n"


def test_less_alias(run, fs) -> None:
    fs.write_file("/x", "abc\n")
    r = run("less /x")
    assert r.stdout == "abc\n"


def test_b3sum_known_input(run) -> None:
    r = run("b3sum", stdin=b"abc")
    parts = r.stdout.split()
    assert len(parts[0]) == 64  # 32-byte digest hex


def test_od_octal(run) -> None:
    r = run("od", stdin=b"AB")
    # Two ASCII chars - little-endian 16-bit value 0x4241 = 041101 octal.
    assert "041101" in r.stdout


def test_od_char(run) -> None:
    r = run("od -c", stdin=b"hi\n")
    assert "h" in r.stdout
    assert "i" in r.stdout
    assert "\\n" in r.stdout


def test_units_bytes(run) -> None:
    r = run("units 1024 B KB")
    assert r.stdout.strip() == "1.024"


def test_units_seconds(run) -> None:
    r = run("units 90 s min")
    assert r.stdout.strip() == "1.5"


def test_md5_string(run) -> None:
    r = run("md5 -s hello")
    assert "5d41402abc4b2a76b9719d911017c592" in r.stdout


def test_gzip_round_trip(run, fs) -> None:
    fs.write_file("/x", "hello world\n")
    r = run("gzip -k /x")
    assert r.exit_code == 0
    assert fs.exists("/x.gz")
    fs.rm("/x")
    r = run("gunzip /x.gz")
    assert r.exit_code == 0
    assert fs.read_text("/x") == "hello world\n"


def test_zcat_passes_through_uncompressed(run, fs) -> None:
    fs.write_file("/x", b"plain bytes")
    r = run("zcat /x")
    assert r.stdout == "plain bytes"


# ---------------------------------------------------------------------------
# extglob tests
# ---------------------------------------------------------------------------


def test_case_extglob_at(run) -> None:
    r = run("case alpha in @(alpha|beta)) echo match;; *) echo no;; esac")
    assert r.stdout == "match\n"


def test_case_extglob_negate(run) -> None:
    r = run("case foo.md in !(*.txt)) echo not-txt;; *) echo txt;; esac")
    assert r.stdout == "not-txt\n"


def test_case_extglob_star(run) -> None:
    r = run("case ababa in *(a|b)) echo all-ab;; *) echo no;; esac")
    assert r.stdout == "all-ab\n"


def test_case_extglob_plus(run) -> None:
    r = run("case ddd in +(d)) echo dees;; *) echo no;; esac")
    assert r.stdout == "dees\n"


def test_case_extglob_question(run) -> None:
    r = run('case "" in ?(x)) echo zero;; *) echo no;; esac')
    assert r.stdout == "zero\n"


# ---------------------------------------------------------------------------
# Arithmetic array element
# ---------------------------------------------------------------------------


def test_arith_assoc_subscript(run) -> None:
    r = run("""
declare -A m
m[a]=10
m[b]=20
total=0
for k in a b; do
  ((total += m[$k]))
done
echo "$total"
""")
    assert r.stdout == "30\n"


def test_arith_indexed_subscript(run) -> None:
    r = run('arr=(10 20 30); ((sum = arr[0] + arr[1] + arr[2])); echo "$sum"')
    assert r.stdout == "60\n"
