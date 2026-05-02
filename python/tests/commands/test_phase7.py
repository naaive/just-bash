"""Phase-7 command tests: getopts, printf -v, BASH_*, sort -k/-V/-h, factor,
install, truncate, shasum, sleep units, env -i, realpath -e."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# getopts
# ---------------------------------------------------------------------------


def test_getopts_basic(run) -> None:
    r = run("""
set -- -a -b val rest
while getopts "ab:c" opt; do
  case $opt in
    a) echo "got -a";;
    b) echo "got -b $OPTARG";;
    c) echo "got -c";;
  esac
done
shift $((OPTIND - 1))
echo "remaining: $@"
""")
    assert r.stdout == "got -a\ngot -b val\nremaining: rest\n"


def test_getopts_glued_argument(run) -> None:
    r = run("""
set -- -bvalue
while getopts "ab:c" opt; do
  echo "$opt=$OPTARG"
done
""")
    assert "b=value" in r.stdout


def test_getopts_unknown_silent(run) -> None:
    r = run("""
set -- -z
while getopts ":a" opt; do
  echo "$opt:$OPTARG"
done
""")
    assert "?:z" in r.stdout


# ---------------------------------------------------------------------------
# printf -v
# ---------------------------------------------------------------------------


def test_printf_v_writes_var(run) -> None:
    r = run('printf -v out "hi %s" world; echo "[$out]"')
    assert r.stdout == "[hi world]\n"


def test_printf_v_repeated_format(run) -> None:
    r = run('printf -v out "%s|" a b c; echo "[$out]"')
    assert r.stdout == "[a|b|c|]\n"


# ---------------------------------------------------------------------------
# BASH_* introspection
# ---------------------------------------------------------------------------


def test_bash_version_set(run) -> None:
    r = run('echo "$BASH_VERSION"')
    assert "just-bash-py" in r.stdout


def test_pipestatus(run) -> None:
    r = run('true | false | true; echo "${PIPESTATUS[@]}"')
    assert r.stdout == "0 1 0\n"


def test_seconds(run) -> None:
    # SECONDS should be a non-negative integer.
    r = run('echo "$SECONDS"')
    assert r.stdout.strip().isdigit()


def test_random_is_numeric(run) -> None:
    r = run('echo "$RANDOM"')
    assert r.stdout.strip().isdigit()


def test_hostname_var(run) -> None:
    r = run('echo "$HOSTNAME"')
    assert r.stdout.strip() == "sandbox"


# ---------------------------------------------------------------------------
# sort improvements
# ---------------------------------------------------------------------------


def test_sort_key_field(run) -> None:
    r = run("printf '3 c\\n1 a\\n2 b\\n' | sort -k1n")
    assert r.stdout == "1 a\n2 b\n3 c\n"


def test_sort_version(run) -> None:
    r = run("printf 'v1.2\\nv1.10\\nv1.3\\n' | sort -V")
    assert r.stdout == "v1.2\nv1.3\nv1.10\n"


def test_sort_human(run) -> None:
    r = run("printf '1K\\n5M\\n100\\n2G\\n' | sort -h")
    assert r.stdout == "100\n1K\n5M\n2G\n"


def test_sort_with_delim(run) -> None:
    r = run("printf 'b,2\\na,1\\nc,3\\n' | sort -t, -k1")
    assert r.stdout == "a,1\nb,2\nc,3\n"


# ---------------------------------------------------------------------------
# factor / install / truncate / shasum
# ---------------------------------------------------------------------------


def test_factor(run) -> None:
    r = run("factor 60")
    assert r.stdout.strip() == "60: 2 2 3 5"


def test_install_creates_file(run, fs) -> None:
    fs.write_file("/src", "data\n")
    r = run("install /src /dst")
    assert r.exit_code == 0
    assert fs.read_text("/dst") == "data\n"


def test_install_directory(run, fs) -> None:
    r = run("install -d /a/b/c")
    assert r.exit_code == 0
    assert fs.is_dir("/a/b/c")


def test_truncate_extends(run, fs) -> None:
    fs.write_file("/x", "hi")
    r = run("truncate -s 5 /x")
    assert r.exit_code == 0
    assert fs.read_file("/x") == b"hi\x00\x00\x00"


def test_truncate_shrinks(run, fs) -> None:
    fs.write_file("/x", "abcdef")
    r = run("truncate -s 3 /x")
    assert r.exit_code == 0
    assert fs.read_file("/x") == b"abc"


def test_shasum_default_sha1(run) -> None:
    r = run("shasum", stdin=b"abc")
    # SHA1("abc") = a9993e364706816aba3e25717850c26c9cd0d89d
    assert r.stdout.split()[0] == "a9993e364706816aba3e25717850c26c9cd0d89d"


def test_shasum_256(run) -> None:
    r = run("shasum -a 256", stdin=b"abc")
    assert r.stdout.split()[0] == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )


# ---------------------------------------------------------------------------
# sleep / basename / dirname / env -i / realpath -e
# ---------------------------------------------------------------------------


def test_sleep_minutes(run) -> None:
    r = run("sleep 0.5m; echo done")
    assert r.stdout == "done\n"


def test_basename_with_suffix(run) -> None:
    r = run("basename /a/b/foo.txt .txt")
    assert r.stdout == "foo\n"


def test_basename_multi(run) -> None:
    r = run("basename -a /a/b /c/d")
    assert r.stdout == "b\nd\n"


def test_dirname_multi(run) -> None:
    r = run("dirname /a/b /c/d/e")
    assert r.stdout == "/a\n/c/d\n"


def test_env_ignore(run) -> None:
    r = run("export FOO=bar; env -i echo done")
    assert r.stdout == "done\n"


def test_realpath_e_missing(run) -> None:
    r = run("realpath -e /nope")
    assert r.exit_code == 1


def test_realpath_q_silent(run) -> None:
    r = run("realpath -e -q /nope")
    assert r.exit_code == 1
    assert r.stderr == ""


# ---------------------------------------------------------------------------
# select / coproc are no-op stubs - confirm they don't error.
# ---------------------------------------------------------------------------


def test_coproc_dispatched(run) -> None:
    # ``coproc`` is registered as a no-op builtin; the script should exit
    # cleanly without erroring out at parse time.
    r = run("coproc echo hi; echo done")
    assert r.exit_code == 0
    assert "done" in r.stdout
