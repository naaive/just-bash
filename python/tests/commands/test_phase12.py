"""Phase-12 command tests."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Mail / messaging
# ---------------------------------------------------------------------------


def test_mail_silent_success(run) -> None:
    r = run("mail -s 'hi' nobody")
    assert r.exit_code == 0


def test_wall_silent_success(run) -> None:
    r = run("echo hello | wall")
    assert r.exit_code == 0


def test_mesg_default_n(run) -> None:
    r = run("mesg")
    assert r.stdout.strip() == "is n"


def test_mesg_set_returns_zero(run) -> None:
    r = run("mesg n")
    assert r.exit_code == 0


def test_finger_header(run) -> None:
    r = run("finger")
    assert "Login" in r.stdout


# ---------------------------------------------------------------------------
# Scheduler stubs
# ---------------------------------------------------------------------------


def test_at_no_op(run) -> None:
    r = run("at now + 1 minute")
    assert r.exit_code == 0


def test_crontab_l_empty(run) -> None:
    r = run("crontab -l")
    assert r.exit_code == 1
    assert "no crontab" in r.stderr


def test_crontab_other_no_op(run) -> None:
    r = run("crontab /tmp/missing")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Printer
# ---------------------------------------------------------------------------


def test_lp_canned_request_id(run) -> None:
    r = run("lp /tmp/file")
    assert "request id" in r.stdout


def test_lpstat_no_entries(run) -> None:
    r = run("lpstat")
    assert "no entries" in r.stdout


# ---------------------------------------------------------------------------
# Process priority / lifecycle
# ---------------------------------------------------------------------------


def test_nice_runs_inner(run) -> None:
    r = run("nice -n 10 echo hello")
    assert r.stdout == "hello\n"


def test_nohup_runs_inner(run) -> None:
    r = run("nohup echo hi")
    assert r.stdout == "hi\n"


def test_renice_no_op(run) -> None:
    r = run("renice 5 1234")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Package manager stubs
# ---------------------------------------------------------------------------


def test_apt_get_install_no_op(run) -> None:
    r = run("apt-get install -y foo")
    assert r.exit_code == 0


def test_apt_get_version(run) -> None:
    r = run("apt-get --version")
    assert "apt-get" in r.stdout
    assert "0.0.0" in r.stdout


def test_pip_install_no_op(run) -> None:
    r = run("pip install requests")
    assert r.exit_code == 0


def test_npm_install_no_op(run) -> None:
    r = run("npm install lodash")
    assert r.exit_code == 0


def test_cargo_build_no_op(run) -> None:
    r = run("cargo build --release")
    assert r.exit_code == 0


def test_brew_install_no_op(run) -> None:
    r = run("brew install jq")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Multiplexer stubs
# ---------------------------------------------------------------------------


def test_screen_version(run) -> None:
    r = run("screen -v")
    assert "Screen version" in r.stdout


def test_tmux_version(run) -> None:
    r = run("tmux -V")
    assert "tmux" in r.stdout


def test_tmux_ls_returns_one(run) -> None:
    r = run("tmux ls")
    assert r.exit_code == 1


# ---------------------------------------------------------------------------
# IPC tools
# ---------------------------------------------------------------------------


def test_ipcs_canned_sections(run) -> None:
    r = run("ipcs")
    assert "Message Queues" in r.stdout
    assert "Shared Memory Segments" in r.stdout


def test_ipcrm_no_op(run) -> None:
    r = run("ipcrm -m 1234")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# Lastlog
# ---------------------------------------------------------------------------


def test_lastlog_header(run) -> None:
    r = run("lastlog")
    assert "Username" in r.stdout


# ---------------------------------------------------------------------------
# sudo / su / runuser unwrap and dispatch
# ---------------------------------------------------------------------------


def test_sudo_runs_inner(run) -> None:
    r = run("sudo echo hi")
    assert r.stdout == "hi\n"


def test_sudo_drops_user_flag(run) -> None:
    r = run("sudo -u root echo there")
    assert r.stdout == "there\n"


def test_runuser_dispatches(run) -> None:
    r = run("runuser -u root -- echo ok")
    assert r.stdout == "ok\n"


def test_su_c_runs_inner(run) -> None:
    r = run('su -c "echo hello"')
    assert r.stdout == "hello\n"


def test_su_no_args_no_op(run) -> None:
    r = run("su")
    assert r.exit_code == 0
