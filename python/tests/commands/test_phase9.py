"""Phase-9 command tests."""

from __future__ import annotations


def test_kill_no_op(run) -> None:
    r = run("kill 9999")
    assert r.exit_code == 0


def test_kill_l_lists(run) -> None:
    r = run("kill -l")
    assert "TERM" in r.stdout


def test_pgrep_self(run) -> None:
    r = run("pgrep just-bash")
    assert r.stdout.strip() == "1"


def test_pgrep_unknown(run) -> None:
    r = run("pgrep this_does_not_exist")
    assert r.exit_code == 1


def test_who(run) -> None:
    r = run("who")
    assert "user" in r.stdout


def test_w(run) -> None:
    r = run("w")
    assert "user" in r.stdout
    assert "load average" in r.stdout


def test_last(run) -> None:
    r = run("last")
    assert "user" in r.stdout


def test_groups(run) -> None:
    r = run("groups")
    assert r.stdout.strip() == "user"


def test_logname(run) -> None:
    r = run("logname")
    assert r.stdout.strip() == "user"


def test_tty_not_a_tty(run) -> None:
    r = run("tty")
    assert r.exit_code == 1
    assert "not a tty" in r.stdout


def test_lscpu(run) -> None:
    r = run("lscpu")
    assert "Architecture" in r.stdout
    assert "CPU(s)" in r.stdout


def test_uptime(run) -> None:
    r = run("uptime")
    assert "load average" in r.stdout


def test_dmesg(run) -> None:
    r = run("dmesg")
    assert "sandbox" in r.stdout


def test_csplit_pattern(run, fs) -> None:
    fs.write_file("/in", "header\n--- section ---\nbody1\n--- section ---\nbody2\n")
    r = run("csplit /in '/^--- section ---$/'")
    assert r.exit_code == 0
    # We expect at least xx00 and xx01 to exist.
    assert fs.exists("/work/xx00") or fs.exists("xx00")


# ---------------------------------------------------------------------------
# read improvements
# ---------------------------------------------------------------------------


def test_read_n_chars(run) -> None:
    r = run('read -n 3 var <<< "abcdef"; echo "[$var]"')
    assert r.stdout == "[abc]\n"


def test_read_array(run) -> None:
    r = run('read -a parts <<< "alpha beta gamma"; echo "${parts[1]}"')
    assert r.stdout == "beta\n"


def test_read_p_writes_prompt_to_stderr(run) -> None:
    r = run('read -p "name? " name <<< "alice"; echo "$name"')
    assert "alice" in r.stdout
    assert "name?" in r.stderr
