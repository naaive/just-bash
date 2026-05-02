"""Phase-12 commands: system / package-manager / scheduler stubs that scripts
commonly call but which would have no real effect inside the sandbox.

The stubs are deterministic: they accept their typical args, may print a
canned line on stderr explaining the no-op, and return a sensible exit code
so feature-detection scripts (``command -v X``, ``X --version``) succeed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from just_bash.commands._helpers import write_err, write_out

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


# ---------------------------------------------------------------------------
# Mail / messaging - all no-ops in a sandbox.
# ---------------------------------------------------------------------------


def cmd_mail(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_wall(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_mesg(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        write_out(io_ctx, b"is n\n")
        return 0
    return 0


def cmd_finger(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"Login    Name    Tty    Idle  Login Time   Office     Office Phone\n")
    return 0


# ---------------------------------------------------------------------------
# Scheduler stubs (at, atq, atrm, batch, crontab).
# ---------------------------------------------------------------------------


def cmd_at(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_atq(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_atrm(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_batch(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_crontab(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``crontab -l`` reports an empty crontab; other forms are no-ops."""
    args = argv[1:]
    if args and args[0] == "-l":
        write_err(io_ctx, b"no crontab for user\n")
        return 1
    return 0


# ---------------------------------------------------------------------------
# Printer queue stubs.
# ---------------------------------------------------------------------------


def cmd_lp(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"request id is print-1 (1 file(s))\n")
    return 0


def cmd_lpr(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_lpstat(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"no entries\n")
    return 0


# ---------------------------------------------------------------------------
# Process priority / lifecycle stubs.
# ---------------------------------------------------------------------------


def cmd_nice(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``nice [-n N] CMD ARGS...`` - drop the priority flag and run the rest."""
    args = argv[1:]
    if args and args[0] == "-n" and len(args) >= 2:
        args = args[2:]
    elif (args and args[0].startswith("-n")) or (args and args[0].startswith("-")):
        args = args[1:]
    if not args:
        write_out(io_ctx, b"0\n")
        return 0
    return interp._dispatch(args, io_ctx)


def cmd_renice(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_nohup(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    args = argv[1:]
    if not args:
        write_err(io_ctx, b"nohup: missing command\n")
        return 125
    return interp._dispatch(args, io_ctx)


# ---------------------------------------------------------------------------
# Package-manager stubs - feature-detection only, never actually install.
# ---------------------------------------------------------------------------


def _pkgmgr_stub(name: str, _argv: list[str], io_ctx: IO) -> int:
    """Generic package-manager stub: ``--version`` succeeds, anything else is
    treated as a no-op so installs in scripts don't blow up the sandbox."""
    args = _argv[1:]
    if args and args[0] in ("--version", "-V"):
        write_out(io_ctx, f"{name} (sandbox stub) 0.0.0\n")
        return 0
    if args and args[0] == "list":
        write_out(io_ctx, b"")
        return 0
    return 0


def cmd_apt(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("apt", argv, io_ctx)


def cmd_apt_get(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("apt-get", argv, io_ctx)


def cmd_dpkg(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("dpkg", argv, io_ctx)


def cmd_yum(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("yum", argv, io_ctx)


def cmd_dnf(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("dnf", argv, io_ctx)


def cmd_rpm(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("rpm", argv, io_ctx)


def cmd_pip(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("pip", argv, io_ctx)


def cmd_pip3(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("pip3", argv, io_ctx)


def cmd_npm(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("npm", argv, io_ctx)


def cmd_pnpm(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("pnpm", argv, io_ctx)


def cmd_yarn(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("yarn", argv, io_ctx)


def cmd_brew(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("brew", argv, io_ctx)


def cmd_cargo(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    return _pkgmgr_stub("cargo", argv, io_ctx)


# ---------------------------------------------------------------------------
# Multiplexer stubs (screen / tmux): respond to ``-V`` so feature checks
# succeed; everything else is a no-op.
# ---------------------------------------------------------------------------


def cmd_screen(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("-v", "-V", "--version"):
        write_out(io_ctx, b"Screen version 4.99.0 (sandbox stub)\n")
    return 0


def cmd_tmux(_interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    if len(argv) >= 2 and argv[1] in ("-v", "-V", "--version"):
        write_out(io_ctx, b"tmux 3.4 (sandbox stub)\n")
        return 0
    if len(argv) >= 2 and argv[1] == "ls":
        return 1
    return 0


# ---------------------------------------------------------------------------
# IPC tools (ipcs, ipcrm, ipcmk) - canned empty queues / shared-mem segments.
# ---------------------------------------------------------------------------


def cmd_ipcs(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    out = (
        "------ Message Queues --------\n"
        "key        msqid      owner      perms      used-bytes   messages\n"
        "\n"
        "------ Shared Memory Segments --------\n"
        "key        shmid      owner      perms      bytes        nattch     status\n"
        "\n"
        "------ Semaphore Arrays --------\n"
        "key        semid      owner      perms      nsems\n"
    )
    write_out(io_ctx, out)
    return 0


def cmd_ipcrm(_interp: Interpreter, _argv: list[str], _io: IO) -> int:
    return 0


def cmd_ipcmk(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"Message queue id: 0\n")
    return 0


# ---------------------------------------------------------------------------
# Misc small helpers.
# ---------------------------------------------------------------------------


def cmd_lastlog(_interp: Interpreter, _argv: list[str], io_ctx: IO) -> int:
    write_out(io_ctx, b"Username         Port     From             Latest\n")
    return 0


def cmd_runuser(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``runuser [-u USER] -- CMD ARGS...`` - the sandbox runs everything as
    the same user, so we just exec the inner command."""
    args = argv[1:]
    while args and (args[0] in ("-u", "--user") or args[0] == "--"):
        if args[0] == "--":
            args = args[1:]
            break
        if args[0] in ("-u", "--user"):
            args = args[2:] if len(args) >= 2 else []
            continue
    if not args:
        return 0
    return interp._dispatch(args, io_ctx)


def cmd_su(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``su [-c CMD]`` - run the supplied command, otherwise no-op."""
    args = argv[1:]
    if args and args[0] == "-c" and len(args) >= 2:
        from just_bash.parser.parser import parse

        sub = parse(args[1])
        for stmt in sub.statements:
            interp._run_statement(stmt, io_ctx)
        return interp.env.last_exit
    return 0


def cmd_sudo(interp: Interpreter, argv: list[str], io_ctx: IO) -> int:
    """``sudo CMD ARGS...`` - drop privilege flags and exec the inner cmd."""
    args = argv[1:]
    while args and args[0].startswith("-"):
        if args[0] in ("-u", "-g", "-h", "-p", "-r", "-t", "-U") and len(args) >= 2:
            args = args[2:]
            continue
        args = args[1:]
    if not args:
        return 0
    return interp._dispatch(args, io_ctx)


__all__ = [
    "cmd_apt",
    "cmd_apt_get",
    "cmd_at",
    "cmd_atq",
    "cmd_atrm",
    "cmd_batch",
    "cmd_brew",
    "cmd_cargo",
    "cmd_crontab",
    "cmd_dnf",
    "cmd_dpkg",
    "cmd_finger",
    "cmd_ipcmk",
    "cmd_ipcrm",
    "cmd_ipcs",
    "cmd_lastlog",
    "cmd_lp",
    "cmd_lpr",
    "cmd_lpstat",
    "cmd_mail",
    "cmd_mesg",
    "cmd_nice",
    "cmd_nohup",
    "cmd_npm",
    "cmd_pip",
    "cmd_pip3",
    "cmd_pnpm",
    "cmd_renice",
    "cmd_rpm",
    "cmd_runuser",
    "cmd_screen",
    "cmd_su",
    "cmd_sudo",
    "cmd_tmux",
    "cmd_wall",
    "cmd_yarn",
    "cmd_yum",
]
