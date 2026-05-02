"""Phase-11 command tests."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# tree
# ---------------------------------------------------------------------------


def test_tree_basic_layout(run, fs) -> None:
    fs.mkdir("/p", parents=True, exist_ok=True)
    fs.write_file("/p/a.txt", "")
    fs.mkdir("/p/sub", parents=True, exist_ok=True)
    fs.write_file("/p/sub/b.txt", "")
    r = run("tree /p")
    assert "a.txt" in r.stdout
    assert "sub" in r.stdout
    assert "b.txt" in r.stdout
    assert "1 directories, 2 files" in r.stdout


def test_tree_max_depth(run, fs) -> None:
    fs.mkdir("/p/sub/deep", parents=True, exist_ok=True)
    fs.write_file("/p/sub/deep/x", "")
    r = run("tree -L 1 /p")
    assert "sub" in r.stdout
    assert "deep" not in r.stdout


def test_tree_hidden_default_excluded(run, fs) -> None:
    fs.mkdir("/p", parents=True, exist_ok=True)
    fs.write_file("/p/.hidden", "")
    fs.write_file("/p/visible", "")
    r = run("tree /p")
    assert "visible" in r.stdout
    assert ".hidden" not in r.stdout


def test_tree_hidden_with_dash_a(run, fs) -> None:
    fs.mkdir("/p", parents=True, exist_ok=True)
    fs.write_file("/p/.hidden", "")
    r = run("tree -a /p")
    assert ".hidden" in r.stdout


# ---------------------------------------------------------------------------
# rg / ag (recursive grep aliases)
# ---------------------------------------------------------------------------


def test_rg_recursive_match(run, fs) -> None:
    fs.mkdir("/p/sub", parents=True, exist_ok=True)
    fs.write_file("/p/a", "alpha\n")
    fs.write_file("/p/sub/b", "beta\n")
    r = run("rg alpha /p")
    assert "alpha" in r.stdout


def test_ag_alias(run, fs) -> None:
    fs.mkdir("/p", parents=True, exist_ok=True)
    fs.write_file("/p/a", "needle here\n")
    r = run("ag needle /p")
    assert "needle" in r.stdout


# ---------------------------------------------------------------------------
# fd
# ---------------------------------------------------------------------------


def test_fd_finds_by_name(run, fs) -> None:
    fs.mkdir("/p/sub", parents=True, exist_ok=True)
    fs.write_file("/p/a.log", "")
    fs.write_file("/p/sub/b.log", "")
    fs.write_file("/p/c.txt", "")
    r = run("fd .log /p")
    assert "/p/a.log" in r.stdout
    assert "/p/sub/b.log" in r.stdout
    assert "/p/c.txt" not in r.stdout


def test_fdfind_alias(run, fs) -> None:
    fs.mkdir("/p", parents=True, exist_ok=True)
    fs.write_file("/p/file.txt", "")
    r = run("fdfind file /p")
    assert "/p/file.txt" in r.stdout


# ---------------------------------------------------------------------------
# bat
# ---------------------------------------------------------------------------


def test_bat_includes_line_numbers(run, fs) -> None:
    fs.write_file("/x", "alpha\nbeta\n")
    r = run("bat /x")
    assert "1" in r.stdout
    assert "alpha" in r.stdout
    assert "2" in r.stdout
    assert "beta" in r.stdout


# ---------------------------------------------------------------------------
# sd
# ---------------------------------------------------------------------------


def test_sd_stdin_replace(run) -> None:
    r = run("sd foo bar", stdin=b"foo and foo\n")
    assert r.stdout == "bar and bar\n"


def test_sd_in_place_file(run, fs) -> None:
    fs.write_file("/x", "hello world\n")
    r = run("sd world Earth /x")
    assert r.exit_code == 0
    assert fs.read_text("/x") == "hello Earth\n"


# ---------------------------------------------------------------------------
# fzf (deterministic stub)
# ---------------------------------------------------------------------------


def test_fzf_no_args_picks_first(run) -> None:
    r = run("fzf", stdin=b"alpha\nbeta\ngamma\n")
    assert r.stdout == "alpha\n"


def test_fzf_filter_matches(run) -> None:
    r = run("fzf -f am", stdin=b"alpha\nbeta\ngamma\n")
    assert "gamma" in r.stdout
    assert "beta" not in r.stdout


# ---------------------------------------------------------------------------
# hexyl
# ---------------------------------------------------------------------------


def test_hexyl_outputs_hex(run) -> None:
    r = run("hexyl", stdin=b"AB")
    # cmd_hexdump -C produces something containing "41 42" for "AB".
    assert "41" in r.stdout
    assert "42" in r.stdout


# ---------------------------------------------------------------------------
# CSV / TSV translators
# ---------------------------------------------------------------------------


def test_csv2tsv_basic(run) -> None:
    r = run("csv2tsv", stdin=b"a,b,c\n1,2,3\n")
    assert r.stdout == "a\tb\tc\n1\t2\t3\n"


def test_csv2tsv_quoted_field(run) -> None:
    r = run("csv2tsv", stdin=b'name,note\n"a,b","x ""y"""\n')
    assert r.stdout == 'name\tnote\na,b\tx "y"\n'


def test_tsv2csv_basic(run) -> None:
    r = run("tsv2csv", stdin=b"a\tb\tc\n1\t2\t3\n")
    assert r.stdout == "a,b,c\n1,2,3\n"


def test_tsv2csv_quotes_special_chars(run) -> None:
    r = run("tsv2csv", stdin=b"a\tb,c\n")
    assert r.stdout == 'a,"b,c"\n'


# ---------------------------------------------------------------------------
# getconf
# ---------------------------------------------------------------------------


def test_getconf_known_var(run) -> None:
    r = run("getconf PAGE_SIZE")
    assert r.stdout.strip() == "4096"


def test_getconf_unknown_var(run) -> None:
    r = run("getconf NOT_A_THING")
    assert r.exit_code == 1


# ---------------------------------------------------------------------------
# locale
# ---------------------------------------------------------------------------


def test_locale_no_args_shows_lang(run) -> None:
    r = run("locale")
    assert "LANG" in r.stdout
    assert "LC_CTYPE" in r.stdout


def test_locale_dash_a_lists_locales(run) -> None:
    r = run("locale -a")
    assert "C" in r.stdout
    assert "C.UTF-8" in r.stdout


# ---------------------------------------------------------------------------
# iconv
# ---------------------------------------------------------------------------


def test_iconv_utf8_passthrough(run) -> None:
    r = run("iconv -f utf-8 -t utf-8", stdin="café\n".encode())
    assert r.stdout == "café\n"


def test_iconv_utf8_to_ascii_replaces(run) -> None:
    r = run("iconv -f utf-8 -t ascii", stdin="café\n".encode())
    # `?` is the ascii replacement for `é`.
    assert "caf" in r.stdout


# ---------------------------------------------------------------------------
# yq
# ---------------------------------------------------------------------------


def test_yq_dot_passthrough(run) -> None:
    r = run("yq .", stdin=b"key: value\n")
    assert r.stdout == "key: value\n"


def test_yq_key_lookup(run) -> None:
    r = run("yq .name", stdin=b"name: alice\nage: 30\n")
    assert r.stdout == "alice\n"


def test_yq_missing_key(run) -> None:
    r = run("yq .nope", stdin=b"name: alice\n")
    assert r.stdout == "null\n"


# ---------------------------------------------------------------------------
# xargs0 alias
# ---------------------------------------------------------------------------


def test_xargs0_null_separator(run) -> None:
    r = run("xargs0 echo", stdin=b"alpha\x00beta\x00gamma")
    assert "alpha" in r.stdout
    assert "beta" in r.stdout
    assert "gamma" in r.stdout
