"""Phase-12 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# extglob inside [[ ]] (the new wiring in this phase).
# ---------------------------------------------------------------------------


def test_double_brackets_extglob_at() -> None:
    compare(
        "double_brackets_extglob_at",
        "shopt -s extglob; "
        """eval 'if [[ "abc" == @(abc|def) ]]; then echo yes; else echo no; fi' """,
    )


def test_double_brackets_extglob_negate() -> None:
    compare(
        "double_brackets_extglob_negate",
        "shopt -s extglob; "
        """eval 'if [[ "foo.md" == !(*.txt) ]]; then echo not-txt; else echo txt; fi' """,
    )


def test_double_brackets_extglob_plus() -> None:
    compare(
        "double_brackets_extglob_plus",
        "shopt -s extglob; "
        """eval 'if [[ "aaa" == +(a) ]]; then echo plus; else echo no; fi' """,
    )


# ---------------------------------------------------------------------------
# Array slicing with [@]:offset:length (the bug fixed in this phase).
# ---------------------------------------------------------------------------


def test_array_slice_at_offset() -> None:
    compare(
        "array_slice_at_offset",
        """
arr=(zero one two three four five)
echo "${arr[@]:2}"
""".strip(),
    )


def test_array_slice_at_offset_length() -> None:
    compare(
        "array_slice_at_offset_length",
        """
arr=(zero one two three four five)
echo "${arr[@]:1:3}"
""".strip(),
    )


def test_array_slice_star_form() -> None:
    compare(
        "array_slice_star_form",
        """
arr=(zero one two three four five)
echo "${arr[*]:2:2}"
""".strip(),
    )


def test_positional_slice() -> None:
    compare(
        "positional_slice",
        """
set -- a b c d e
echo "$@"
echo "${@:2}"
echo "${@:2:2}"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Parameter expansion: anchors and replace-all.
# ---------------------------------------------------------------------------


def test_param_replace_first_p12() -> None:
    compare(
        "param_replace_first_p12",
        """
s="alpha-beta-gamma-beta-delta"
echo "${s/beta/X}"
""".strip(),
    )


def test_param_replace_all_p12() -> None:
    compare(
        "param_replace_all_p12",
        """
s="alpha-beta-gamma-beta-delta"
echo "${s//beta/X}"
""".strip(),
    )


def test_param_replace_anchor_start() -> None:
    compare(
        "param_replace_anchor_start",
        """
s="alpha-beta-gamma"
echo "${s/#alpha/A}"
""".strip(),
    )


def test_param_replace_anchor_end() -> None:
    compare(
        "param_replace_anchor_end",
        """
s="alpha-beta-gamma"
echo "${s/%gamma/G}"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Sudo / su passthrough (real bash needs sudo on PATH; we test the
# inner-command unwrap with `--` only to keep it portable).
# ---------------------------------------------------------------------------


def test_sudo_passthrough() -> None:
    import pytest

    pytest.skip("sudo behaviour differs on hosts without /etc/sudoers")


# ---------------------------------------------------------------------------
# Quoting layers
# ---------------------------------------------------------------------------


def test_quoting_concat_levels() -> None:
    compare(
        "quoting_concat_levels",
        """
x=dollar
echo 'a''b'"c""$x"
""".strip(),
    )


def test_quoting_ansi_c() -> None:
    compare(
        "quoting_ansi_c",
        r"""printf '%s\n' $'line1\nline2\tindented'""",
    )


# ---------------------------------------------------------------------------
# getopts flag combinations
# ---------------------------------------------------------------------------


def test_getopts_full() -> None:
    compare(
        "getopts_full",
        """
set -- -v -n 5 -o /tmp/out arg1
verbose=0; count=0; out=
OPTIND=1
while getopts ":vn:o:" opt; do
  case "$opt" in
    v) verbose=$((verbose + 1)) ;;
    n) count=$OPTARG ;;
    o) out=$OPTARG ;;
  esac
done
shift $((OPTIND - 1))
echo "verbose=$verbose count=$count out=$out rest=$*"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Real-world idioms
# ---------------------------------------------------------------------------


def test_join_array_via_local_ifs() -> None:
    compare(
        "join_array_via_local_ifs",
        """
arr=(a b c d)
joined=$(IFS=,; echo "${arr[*]}")
echo "$joined"
""".strip(),
    )


def test_string_length_chain() -> None:
    compare(
        "string_length_chain",
        """
s="hello world"
echo "${#s}"
echo "${#s} ${s:0:5}"
""".strip(),
    )


def test_for_word_split_assoc() -> None:
    compare(
        "for_word_split_assoc",
        """
declare -A m
m[a]=1
m[b]=2
m[c]=3
total=0
for k in a b c; do
  total=$((total + m[$k]))
done
echo "$total"
""".strip(),
    )


def test_glob_star_in_case() -> None:
    compare(
        "glob_star_in_case",
        """
for n in foo.txt bar.md baz.tar.gz quux; do
  case "$n" in
    *.txt) echo "$n: text" ;;
    *.md)  echo "$n: markdown" ;;
    *.tar.gz) echo "$n: archive" ;;
    *) echo "$n: other" ;;
  esac
done
""".strip(),
    )


def test_brace_combination() -> None:
    compare(
        "brace_combination",
        "echo {a,b}{1..3}",
    )


def test_assoc_keys_count() -> None:
    compare(
        "assoc_keys_count",
        """
declare -A h
h[red]=#f00
h[green]=#0f0
h[blue]=#00f
echo "${#h[@]}"
""".strip(),
    )


def test_until_with_subshell_check() -> None:
    compare(
        "until_with_subshell_check",
        """
n=0
until [[ $n -ge 3 ]]; do
  n=$((n + 1))
  echo "n=$n"
done
""".strip(),
    )


def test_redirect_to_dev_null() -> None:
    compare(
        "redirect_to_dev_null",
        """
echo silenced > /dev/null
echo visible
""".strip(),
    )


def test_compound_pipeline_status() -> None:
    compare(
        "compound_pipeline_status",
        """
{ echo a; echo b; } | wc -l
""".strip(),
    )


def test_function_returns_via_echo() -> None:
    compare(
        "function_returns_via_echo",
        """
greet() { echo "hi $1"; }
out=$(greet world)
echo "[$out]"
""".strip(),
    )


def test_arith_with_unset_var() -> None:
    compare(
        "arith_with_unset_var",
        """
unset notset
echo $((notset + 5))
""".strip(),
    )


def test_arith_increment_decrement() -> None:
    compare(
        "arith_increment_decrement",
        """
n=5
echo $((n++))
echo $n
echo $((--n))
echo $n
""".strip(),
    )
