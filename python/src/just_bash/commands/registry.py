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
    sed_cmd,
    text_utils,
)

if TYPE_CHECKING:
    from just_bash.interpreter.interpreter import IO, Interpreter


CommandImpl = Callable[["Interpreter", "list[str]", "IO"], int]


def default_registry() -> dict[str, CommandImpl]:
    """Return the builtin command -> implementation map."""
    return {
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


__all__ = ["CommandImpl", "default_registry"]
