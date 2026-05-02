"""Phase-13 command tests."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Networking inspection
# ---------------------------------------------------------------------------


def test_netstat_header(run) -> None:
    r = run("netstat")
    assert "Active Internet connections" in r.stdout
    assert r.exit_code == 0


def test_ss_header(run) -> None:
    r = run("ss")
    assert "Local Address" in r.stdout


def test_route_header(run) -> None:
    r = run("route")
    assert "Destination" in r.stdout


def test_arp_header(run) -> None:
    r = run("arp")
    assert "HWaddress" in r.stdout


# ---------------------------------------------------------------------------
# Network paths
# ---------------------------------------------------------------------------


def test_traceroute_canned(run) -> None:
    r = run("traceroute example.com")
    assert "traceroute to example.com" in r.stdout


def test_mtr_canned(run) -> None:
    r = run("mtr 10.0.0.1")
    assert "10.0.0.1" in r.stdout


# ---------------------------------------------------------------------------
# Connection tools
# ---------------------------------------------------------------------------


def test_nc_z_returns_zero(run) -> None:
    r = run("nc -z localhost 22")
    assert r.exit_code == 0


def test_telnet_refuses(run) -> None:
    r = run("telnet example.com 23")
    assert r.exit_code == 1


def test_ftp_not_connected(run) -> None:
    r = run("ftp")
    assert r.exit_code == 1


# ---------------------------------------------------------------------------
# Crypto / signing
# ---------------------------------------------------------------------------


def test_openssl_version(run) -> None:
    r = run("openssl version")
    assert "OpenSSL" in r.stdout


def test_openssl_rand_hex(run) -> None:
    r = run("openssl rand -hex 8")
    assert len(r.stdout.strip()) == 16


def test_openssl_dgst_sha256(run) -> None:
    r = run("openssl dgst -sha256", stdin=b"hello")
    assert "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824" in r.stdout


def test_gpg_version(run) -> None:
    r = run("gpg --version")
    assert "gpg" in r.stdout


def test_ssh_keygen_no_op(run) -> None:
    r = run("ssh-keygen -t rsa -N '' -f /tmp/key")
    assert r.exit_code == 0


def test_ssh_add_l_empty(run) -> None:
    r = run("ssh-add -l")
    assert "no identities" in r.stdout
    assert r.exit_code == 1


def test_ssh_agent_emits_exports(run) -> None:
    r = run("ssh-agent")
    assert "SSH_AUTH_SOCK" in r.stdout
    assert "SSH_AGENT_PID" in r.stdout


# ---------------------------------------------------------------------------
# Binary tools
# ---------------------------------------------------------------------------


def test_objdump_version(run) -> None:
    r = run("objdump -V")
    assert "objdump" in r.stdout


def test_nm_no_op(run) -> None:
    r = run("nm /tmp/x")
    assert r.exit_code == 0


def test_ldd_canned(run) -> None:
    r = run("ldd /bin/ls")
    assert "libc.so.6" in r.stdout


def test_ldconfig_print_cache(run) -> None:
    r = run("ldconfig -p")
    assert "libs found" in r.stdout


def test_ar_version(run) -> None:
    r = run("ar -V")
    assert "ar" in r.stdout


def test_addr2line_unknown(run) -> None:
    r = run("addr2line 0x1234")
    assert "??:0" in r.stdout


# ---------------------------------------------------------------------------
# Patch / diff3
# ---------------------------------------------------------------------------


def test_patch_version(run) -> None:
    r = run("patch -v")
    assert "patch" in r.stdout


def test_diff3_no_op(run) -> None:
    r = run("diff3 a b c")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# System tools
# ---------------------------------------------------------------------------


def test_logger_no_op(run) -> None:
    r = run("logger 'test message'")
    assert r.exit_code == 0


def test_systemctl_status_inactive(run) -> None:
    r = run("systemctl status nginx")
    assert "inactive" in r.stdout
    assert r.exit_code == 3


def test_systemctl_version(run) -> None:
    r = run("systemctl --version")
    assert "systemd" in r.stdout


def test_journalctl_no_op(run) -> None:
    r = run("journalctl -u sshd")
    assert r.exit_code == 0


# ---------------------------------------------------------------------------
# EPOCHSECONDS / EPOCHREALTIME / SRANDOM
# ---------------------------------------------------------------------------


def test_epochseconds_is_numeric(run) -> None:
    r = run('echo "$EPOCHSECONDS"')
    assert r.stdout.strip().isdigit()


def test_epochrealtime_has_dot(run) -> None:
    r = run('echo "$EPOCHREALTIME"')
    out = r.stdout.strip()
    assert "." in out
    assert all(c.isdigit() or c == "." for c in out)


def test_srandom_in_uint32(run) -> None:
    r = run('echo "$SRANDOM"')
    n = int(r.stdout.strip())
    assert 0 <= n < 2**32
