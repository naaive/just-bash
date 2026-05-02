"""Phase-13 commands: network / crypto / binary-tool stubs.

These are deterministic sandbox stubs: feature-detection succeeds,
``--version`` returns a canned string, and operations either succeed
silently or return an empty result. Real network and crypto operations
are NOT performed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import read_input, write_err, write_out

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# Networking inspection (netstat, ss, route, arp).
# ---------------------------------------------------------------------------


def cmd_netstat(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"Active Internet connections (servers and established)\n"
        b"Proto Recv-Q Send-Q Local Address           Foreign Address         State\n",
    )
    return 0


def cmd_ss(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"Netid  State   Recv-Q  Send-Q  Local Address:Port  Peer Address:Port\n")
    return 0


def cmd_route(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"Kernel IP routing table\n"
        b"Destination     Gateway         Genmask         Flags Metric Ref    Use Iface\n",
    )
    return 0


def cmd_arp(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"Address                  HWtype  HWaddress           Flags Mask  Iface\n")
    return 0


# ---------------------------------------------------------------------------
# Network paths (traceroute, mtr).
# ---------------------------------------------------------------------------


def cmd_traceroute(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[1] if len(argv) > 1 else "destination"
    write_out(
        io_ctx,
        f"traceroute to {target}, 30 hops max, 60 byte packets\n"
        f" 1  gateway (10.0.0.1)  0.500 ms  0.400 ms  0.350 ms\n".encode(),
    )
    return 0


def cmd_mtr(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[1] if len(argv) > 1 else "destination"
    write_out(
        io_ctx, f"HOST: sandbox -> {target}  Loss%   Snt   Last   Avg  Best  Wrst StDev\n".encode()
    )
    return 0


# ---------------------------------------------------------------------------
# Connection tools (nc, ncat, socat, telnet, ftp).
# ---------------------------------------------------------------------------


def cmd_nc(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``nc -l ...`` / ``nc HOST PORT`` no-op stub. ``-z`` (port-scan) succeeds
    so feature checks pass."""
    if len(argv) >= 2 and argv[1] == "-z":
        return 0
    return 0


def cmd_ncat(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return cmd_nc(interp, argv, io_ctx)


def cmd_socat(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_telnet(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    write_err(io_ctx, b"telnet: connection refused (sandbox)\n")
    return 1


def cmd_ftp(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_err(io_ctx, b"ftp: not connected (sandbox)\n")
    return 1


# ---------------------------------------------------------------------------
# Crypto / signing (openssl, gpg, ssh-keygen, ssh-add, ssh-agent).
# ---------------------------------------------------------------------------


def cmd_openssl(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``openssl version`` and ``openssl rand -hex N`` are useful enough to
    serve canned answers; everything else is a silent no-op."""
    args = argv[1:]
    if args and args[0] == "version":
        write_out(io_ctx, b"OpenSSL 3.0.0 (sandbox stub)\n")
        return 0
    if len(args) >= 3 and args[0] == "rand" and args[1] == "-hex":
        try:
            n = int(args[2])
        except ValueError:
            return 2
        write_out(io_ctx, ("0" * (n * 2)) + "\n")
        return 0
    if len(args) >= 1 and args[0] == "dgst":
        # ``openssl dgst -sha256``: emit a deterministic digest of stdin.
        import hashlib

        algo = "sha256"
        for tok in args[1:]:
            if tok.startswith("-") and tok[1:] in hashlib.algorithms_available:
                algo = tok[1:]
                break
        h = hashlib.new(algo, io_ctx.stdin)
        write_out(io_ctx, f"(stdin)= {h.hexdigest()}\n")
        return 0
    return 0


def cmd_gpg(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] == "--version":
        write_out(io_ctx, b"gpg (GnuPG sandbox stub) 2.4.0\n")
        return 0
    if args and args[0] == "--list-keys":
        return 0
    return 0


def cmd_ssh_keygen(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] == "-V":
        write_out(io_ctx, b"OpenSSH sandbox stub\n")
        return 0
    return 0


def cmd_ssh_add(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] == "-l":
        write_out(io_ctx, b"The agent has no identities.\n")
        return 1
    return 0


def cmd_ssh_agent(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(
        io_ctx,
        b"SSH_AUTH_SOCK=/tmp/ssh-agent.sock; export SSH_AUTH_SOCK;\n"
        b"SSH_AGENT_PID=1; export SSH_AGENT_PID;\n"
        b"echo Agent pid 1;\n",
    )
    return 0


# ---------------------------------------------------------------------------
# Binary tools (objdump, nm, strip, ldd, ldconfig, addr2line, c++filt, ar).
# ---------------------------------------------------------------------------


def cmd_objdump(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("-V", "--version"):
        write_out(io_ctx, b"GNU objdump (sandbox stub)\n")
    return 0


def cmd_nm(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("-V", "--version"):
        write_out(io_ctx, b"GNU nm (sandbox stub)\n")
    return 0


def cmd_strip(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_ldd(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    target = argv[1] if len(argv) > 1 else "(none)"
    write_out(
        io_ctx,
        f"\tlinux-vdso.so.1 (0x00007ffe00000000)\n"
        f"\tlibc.so.6 => /lib/x86_64-linux-gnu/libc.so.6 (0x00007f0000000000)\n"
        f"\t/lib64/ld-linux-x86-64.so.2 (0x00007f0000200000)\n"
        f"# linked: {target}\n".encode(),
    )
    return 0


def cmd_ldconfig(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("-p", "--print-cache"):
        write_out(io_ctx, b"0 libs found in cache `/etc/ld.so.cache'\n")
    return 0


def cmd_addr2line(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"??:0\n")
    return 0


def cmd_cppfilt(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``c++filt`` demangles C++ symbols. We pass mangled-looking input
    through unchanged (real demangling is out of scope)."""
    args = argv[1:]
    if not args:
        data, rc = read_input(interp, io_ctx, [])
        write_out(io_ctx, data)
        return rc
    write_out(io_ctx, " ".join(args) + "\n")
    return 0


def cmd_ar(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("--version", "-V"):
        write_out(io_ctx, b"GNU ar (sandbox stub)\n")
    return 0


# ---------------------------------------------------------------------------
# Patch / diff3 - minimal patch handling.
# ---------------------------------------------------------------------------


def cmd_patch(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if args and args[0] in ("-v", "--version"):
        write_out(io_ctx, b"GNU patch (sandbox stub) 2.7.6\n")
        return 0
    write_out(io_ctx, b"patching\n")
    return 0


def cmd_diff3(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


# ---------------------------------------------------------------------------
# Misc system tools (logger, last on phase9, etc.).
# ---------------------------------------------------------------------------


def cmd_logger(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_systemctl(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``systemctl status SVC`` returns 'inactive (dead)' for any service in
    the sandbox; ``systemctl --version`` returns a canned line."""
    args = argv[1:]
    if args and args[0] in ("--version", "-v"):
        write_out(io_ctx, b"systemd 254 (sandbox stub)\n")
        return 0
    if args and args[0] == "status":
        svc = args[1] if len(args) > 1 else "(none)"
        write_out(
            io_ctx,
            f"○ {svc}\n     Loaded: not-found\n     Active: inactive (dead)\n".encode(),
        )
        return 3
    return 0


def cmd_journalctl(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_service(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"\n")
    return 0


__all__ = [
    "cmd_addr2line",
    "cmd_ar",
    "cmd_arp",
    "cmd_cppfilt",
    "cmd_diff3",
    "cmd_ftp",
    "cmd_gpg",
    "cmd_journalctl",
    "cmd_ldconfig",
    "cmd_ldd",
    "cmd_logger",
    "cmd_mtr",
    "cmd_nc",
    "cmd_ncat",
    "cmd_netstat",
    "cmd_nm",
    "cmd_objdump",
    "cmd_openssl",
    "cmd_patch",
    "cmd_route",
    "cmd_service",
    "cmd_socat",
    "cmd_ss",
    "cmd_ssh_add",
    "cmd_ssh_agent",
    "cmd_ssh_keygen",
    "cmd_strip",
    "cmd_systemctl",
    "cmd_telnet",
    "cmd_traceroute",
]
