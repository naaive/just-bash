"""Default command registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from just_bash.commands import (
    awk_cmd,
    basic,
    cp_mv_rm,
    find_cmd,
    grep_cmd,
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
    }


__all__ = ["CommandImpl", "default_registry"]
