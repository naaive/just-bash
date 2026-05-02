"""Default command registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from just_bash.commands import (
    awk_cmd,
    basic,
    cp_mv_rm,
    extra,
    find_cmd,
    grep_cmd,
    more,
    phase4,
    phase6,
    phase7,
    phase8,
    phase9,
    phase10,
    phase11,
    phase12,
    phase13,
    sed_cmd,
    text_utils,
)

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


CommandImpl = Callable[["Interpreter", "list[str]", "IO"], int]


def default_registry() -> dict[str, CommandImpl]:
    """Return the builtin command -> implementation map.

    Later phases may register the same name as an earlier phase to ship a
    more complete implementation. We build the dict in stages so the final
    pass wins; ``ruff`` would otherwise flag the duplicate keys.
    """
    base: dict[str, CommandImpl] = {
        # I/O
        "cat": basic.cmd_cat,
        "ls": basic.cmd_ls,
        "mkdir": basic.cmd_mkdir,
        "rmdir": basic.cmd_rmdir,
        "touch": basic.cmd_touch,
        "head": basic.cmd_head,
        "tail": basic.cmd_tail,
        "wc": basic.cmd_wc,
        "tee": basic.cmd_tee,
        "basename": basic.cmd_basename,
        "dirname": basic.cmd_dirname,
        "env": basic.cmd_env,
        "which": basic.cmd_which,
        "yes": basic.cmd_yes,
        # text munging
        "sort": text_utils.cmd_sort,
        "uniq": text_utils.cmd_uniq,
        "tr": text_utils.cmd_tr,
        "cut": text_utils.cmd_cut,
        "rev": text_utils.cmd_rev,
        "nl": text_utils.cmd_nl,
        # grep / sed / awk / find
        "grep": grep_cmd.cmd_grep,
        "sed": sed_cmd.cmd_sed,
        "awk": awk_cmd.cmd_awk,
        "find": find_cmd.cmd_find,
        # cp / mv / rm
        "cp": cp_mv_rm.cmd_cp,
        "mv": cp_mv_rm.cmd_mv,
        "rm": cp_mv_rm.cmd_rm,
        "ln": cp_mv_rm.cmd_ln,
        # phase-2 extras
        "seq": extra.cmd_seq,
        "expr": extra.cmd_expr,
        "sleep": extra.cmd_sleep,
        "date": extra.cmd_date,
        "paste": extra.cmd_paste,
        "comm": extra.cmd_comm,
        "diff": extra.cmd_diff,
        "md5sum": extra.cmd_md5sum,
        "sha1sum": extra.cmd_sha1sum,
        "sha256sum": extra.cmd_sha256sum,
        "realpath": extra.cmd_realpath,
        "stat": extra.cmd_stat,
        "xargs": extra.cmd_xargs,
        # phase-3 extras
        "base64": more.cmd_base64,
        "hexdump": more.cmd_hexdump,
        "xxd": more.cmd_xxd,
        "column": more.cmd_column,
        "shuf": more.cmd_shuf,
        "tac": more.cmd_tac,
        "split": more.cmd_split,
        "join": more.cmd_join,
        "hostname": more.cmd_hostname,
        "whoami": more.cmd_whoami,
        "id": more.cmd_id,
        "uname": more.cmd_uname,
        "getent": more.cmd_getent,
        "file": more.cmd_file,
        "jq": more.cmd_jq,
        # phase-4 extras
        "cmp": phase4.cmd_cmp,
        "fold": phase4.cmd_fold,
        "expand": phase4.cmd_expand,
        "unexpand": phase4.cmd_unexpand,
        "mktemp": phase4.cmd_mktemp,
        "getopt": phase4.cmd_getopt,
        "dd": phase4.cmd_dd,
        "cksum": phase4.cmd_cksum,
        "crc32": phase4.cmd_crc32,
        # phase-6 stubs and helpers
        "tar": phase6.cmd_tar,
        "zip": phase6.cmd_zip,
        "unzip": phase6.cmd_unzip,
        "curl": phase6.cmd_curl,
        "wget": phase6.cmd_wget,
        "ping": phase6.cmd_ping,
        "host": phase6.cmd_host,
        "dig": phase6.cmd_dig,
        "nslookup": phase6.cmd_nslookup,
        "ip": phase6.cmd_ip,
        "ifconfig": phase6.cmd_ifconfig,
        "lsof": phase6.cmd_lsof,
        "ps": phase6.cmd_ps,
        "top": phase6.cmd_top,
        "watch": phase6.cmd_watch,
        "du": phase6.cmd_du,
        "df": phase6.cmd_df,
        "free": phase6.cmd_free,
        "pr": phase6.cmd_pr,
        "fmt": phase6.cmd_fmt,
        "look": phase6.cmd_look,
        "tsort": phase6.cmd_tsort,
        "clear": phase6.cmd_clear,
        "reset": phase6.cmd_reset,
        "tput": phase6.cmd_tput,
        "stty": phase6.cmd_stty,
    }
    # Phase-7 supersedes earlier basename/dirname/sleep/env/realpath impls.
    base.update(
        {
            "factor": phase7.cmd_factor,
            "install": phase7.cmd_install,
            "truncate": phase7.cmd_truncate,
            "shasum": phase7.cmd_shasum,
            "basename": phase7.cmd_basename,
            "dirname": phase7.cmd_dirname,
            "sleep": phase7.cmd_sleep,
            "env": phase7.cmd_env,
            "realpath": phase7.cmd_realpath_e,
        }
    )
    # Phase 8: networking/IO stubs and admin helpers.
    base.update(
        {
            "nproc": phase8.cmd_nproc,
            "timeout": phase8.cmd_timeout,
            "rsync": phase8.cmd_rsync,
            "ssh": phase8.cmd_ssh,
            "scp": phase8.cmd_scp,
            "chmod": phase8.cmd_chmod,
            "chown": phase8.cmd_chown,
            "chgrp": phase8.cmd_chgrp,
            "readlink": phase8.cmd_readlink,
            "sync": phase8.cmd_sync,
            "mountpoint": phase8.cmd_mountpoint,
            "strings": phase8.cmd_strings,
            "jot": phase8.cmd_seq_alias,
        }
    )
    # Phase 9: process / system / hardware stubs.
    base.update(
        {
            "kill": phase9.cmd_kill,
            "killall": phase9.cmd_killall,
            "pgrep": phase9.cmd_pgrep,
            "pkill": phase9.cmd_pkill,
            "fuser": phase9.cmd_fuser,
            "pwait": phase9.cmd_pwait,
            "who": phase9.cmd_who,
            "w": phase9.cmd_w,
            "last": phase9.cmd_last,
            "logname": phase9.cmd_logname,
            "groups": phase9.cmd_groups,
            "tty": phase9.cmd_tty,
            "lscpu": phase9.cmd_lscpu,
            "lsmem": phase9.cmd_lsmem,
            "dmesg": phase9.cmd_dmesg,
            "uptime": phase9.cmd_uptime,
            "csplit": phase9.cmd_csplit,
        }
    )
    # Phase 10: pagers, hex, encoding, BLAKE3, archive helpers.
    base.update(
        {
            "more": phase10.cmd_more,
            "less": phase10.cmd_less,
            "pager": phase10.cmd_pager,
            "col": phase10.cmd_col,
            "b3sum": phase10.cmd_b3sum,
            "od": phase10.cmd_od,
            "units": phase10.cmd_units,
            "setaf": phase10.cmd_setaf,
            "md5": phase10.cmd_md5,
            "zcat": phase10.cmd_zcat,
            "gzip": phase10.cmd_gzip,
            "gunzip": phase10.cmd_gunzip,
        }
    )
    # Phase 11: directory tree, modern aliases (rg/fd/bat/sd/ag/fzf/hexyl),
    # CSV/TSV translators, system-info helpers.
    base.update(
        {
            "tree": phase11.cmd_tree,
            "rg": phase11.cmd_rg,
            "ag": phase11.cmd_ag,
            "fd": phase11.cmd_fd,
            "fdfind": phase11.cmd_fdfind,
            "bat": phase11.cmd_bat,
            "sd": phase11.cmd_sd,
            "fzf": phase11.cmd_fzf,
            "hexyl": phase11.cmd_hexyl,
            "csv2tsv": phase11.cmd_csv2tsv,
            "tsv2csv": phase11.cmd_tsv2csv,
            "xargs0": phase11.cmd_xargs0,
            "getconf": phase11.cmd_getconf,
            "locale": phase11.cmd_locale,
            "iconv": phase11.cmd_iconv,
            "yq": phase11.cmd_yq,
        }
    )
    # Phase 12: system / package-manager / scheduler stubs.
    base.update(
        {
            "mail": phase12.cmd_mail,
            "wall": phase12.cmd_wall,
            "mesg": phase12.cmd_mesg,
            "finger": phase12.cmd_finger,
            "at": phase12.cmd_at,
            "atq": phase12.cmd_atq,
            "atrm": phase12.cmd_atrm,
            "batch": phase12.cmd_batch,
            "crontab": phase12.cmd_crontab,
            "lp": phase12.cmd_lp,
            "lpr": phase12.cmd_lpr,
            "lpstat": phase12.cmd_lpstat,
            "nice": phase12.cmd_nice,
            "renice": phase12.cmd_renice,
            "nohup": phase12.cmd_nohup,
            "apt": phase12.cmd_apt,
            "apt-get": phase12.cmd_apt_get,
            "dpkg": phase12.cmd_dpkg,
            "yum": phase12.cmd_yum,
            "dnf": phase12.cmd_dnf,
            "rpm": phase12.cmd_rpm,
            "pip": phase12.cmd_pip,
            "pip3": phase12.cmd_pip3,
            "npm": phase12.cmd_npm,
            "pnpm": phase12.cmd_pnpm,
            "yarn": phase12.cmd_yarn,
            "brew": phase12.cmd_brew,
            "cargo": phase12.cmd_cargo,
            "screen": phase12.cmd_screen,
            "tmux": phase12.cmd_tmux,
            "ipcs": phase12.cmd_ipcs,
            "ipcrm": phase12.cmd_ipcrm,
            "ipcmk": phase12.cmd_ipcmk,
            "lastlog": phase12.cmd_lastlog,
            "runuser": phase12.cmd_runuser,
            "su": phase12.cmd_su,
            "sudo": phase12.cmd_sudo,
        }
    )
    # Phase 13: network / crypto / binary-tool stubs.
    base.update(
        {
            "netstat": phase13.cmd_netstat,
            "ss": phase13.cmd_ss,
            "route": phase13.cmd_route,
            "arp": phase13.cmd_arp,
            "traceroute": phase13.cmd_traceroute,
            "mtr": phase13.cmd_mtr,
            "nc": phase13.cmd_nc,
            "ncat": phase13.cmd_ncat,
            "socat": phase13.cmd_socat,
            "telnet": phase13.cmd_telnet,
            "ftp": phase13.cmd_ftp,
            "openssl": phase13.cmd_openssl,
            "gpg": phase13.cmd_gpg,
            "ssh-keygen": phase13.cmd_ssh_keygen,
            "ssh-add": phase13.cmd_ssh_add,
            "ssh-agent": phase13.cmd_ssh_agent,
            "objdump": phase13.cmd_objdump,
            "nm": phase13.cmd_nm,
            "strip": phase13.cmd_strip,
            "ldd": phase13.cmd_ldd,
            "ldconfig": phase13.cmd_ldconfig,
            "addr2line": phase13.cmd_addr2line,
            "c++filt": phase13.cmd_cppfilt,
            "cppfilt": phase13.cmd_cppfilt,
            "ar": phase13.cmd_ar,
            "patch": phase13.cmd_patch,
            "diff3": phase13.cmd_diff3,
            "logger": phase13.cmd_logger,
            "systemctl": phase13.cmd_systemctl,
            "journalctl": phase13.cmd_journalctl,
            "service": phase13.cmd_service,
        }
    )
    return base


__all__ = ["CommandImpl", "default_registry"]
