"""Phase-15 comparison fixtures."""

from __future__ import annotations

from tests.comparison.harness import compare

# ---------------------------------------------------------------------------
# POSIX char classes
# ---------------------------------------------------------------------------


def test_case_posix_classes() -> None:
    compare(
        "case_posix_classes",
        """
for v in 5 a Z ' ' '!' .; do
  case "$v" in
    [[:digit:]]) echo "$v -> digit" ;;
    [[:alpha:]]) echo "$v -> alpha" ;;
    [[:space:]]) echo "$v -> space" ;;
    [[:punct:]]) echo "$v -> punct" ;;
    *) echo "$v -> other" ;;
  esac
done
""".strip(),
    )


def test_double_brackets_posix_glob() -> None:
    compare(
        "double_brackets_posix_glob",
        """
v=hello123
[[ "$v" == *[[:digit:]]* ]] && echo "has digit"
[[ "abc" == *[[:digit:]]* ]] || echo "no digit"
""".strip(),
    )


def test_posix_xdigit_filter() -> None:
    compare(
        "posix_xdigit_filter",
        """
for ch in 9 a F z; do
  case "$ch" in
    [[:xdigit:]]) echo "$ch hex" ;;
    *) echo "$ch no" ;;
  esac
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# Regex capture groups (BASH_REMATCH)
# ---------------------------------------------------------------------------


def test_regex_version_capture() -> None:
    compare(
        "regex_version_capture",
        r"""
if [[ "version=1.2.3" =~ version=([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
  echo "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  echo "full=${BASH_REMATCH[0]}"
fi
""".strip(),
    )


def test_regex_no_match_clears_rematch_p15() -> None:
    compare(
        "regex_no_match_clears_rematch_p15",
        r"""
[[ "abc" =~ ^x([0-9]+)y$ ]]
echo "rc=$?"
echo "len=${#BASH_REMATCH[@]}"
""".strip(),
    )


def test_regex_alternation_capture() -> None:
    compare(
        "regex_alternation_capture",
        r"""
for s in apple banana cherry; do
  if [[ "$s" =~ ^(apple|cherry)$ ]]; then
    echo "$s: hit (${BASH_REMATCH[1]})"
  else
    echo "$s: miss"
  fi
done
""".strip(),
    )


# ---------------------------------------------------------------------------
# function-keyword forms
# ---------------------------------------------------------------------------


def test_function_keyword_no_parens_p15() -> None:
    compare(
        "function_keyword_no_parens_p15",
        """
function greet {
  echo "hi $1"
}
greet alice
""".strip(),
    )


def test_function_keyword_with_parens_p15() -> None:
    compare(
        "function_keyword_with_parens_p15",
        """
function bye() {
  echo "bye $1"
}
bye bob
""".strip(),
    )


# ---------------------------------------------------------------------------
# FUNCNAME stack
# ---------------------------------------------------------------------------


def test_funcname_stack_chain() -> None:
    compare(
        "funcname_stack_chain",
        """
inner() {
  echo "FUNCNAME=${FUNCNAME[*]}"
  echo "depth=${#FUNCNAME[@]}"
}
middle() { inner; }
outer() { middle; }
outer
echo "top depth=${#FUNCNAME[@]}"
""".strip(),
    )


def test_funcname_self() -> None:
    compare(
        "funcname_self",
        """
me() { echo "I am ${FUNCNAME[0]}"; }
me
""".strip(),
    )


# ---------------------------------------------------------------------------
# ${var@Q} round-trip
# ---------------------------------------------------------------------------


def test_at_q_plain_p15() -> None:
    compare(
        "at_q_plain_p15",
        """x=hello; echo "${x@Q}" """,
    )


def test_at_q_with_space_p15() -> None:
    compare(
        "at_q_with_space_p15",
        """x="hello world"; echo "${x@Q}" """,
    )


def test_at_q_with_quote_p15() -> None:
    compare(
        "at_q_with_quote_p15",
        """x="don't"; echo "${x@Q}" """,
    )


def test_at_q_round_trip_p15() -> None:
    compare(
        "at_q_round_trip_p15",
        """
for original in "alpha" "beta gamma" "with ; punct"; do
  q=${original@Q}
  eval "echoed=$q"
  [[ "$echoed" == "$original" ]] && echo "ok: [$original] -> $q"
done
""".strip(),
    )


def test_at_u_at_l() -> None:
    compare(
        "at_u_at_l",
        """
x="hello world"
echo "${x@U}"
echo "${x@L}"
echo "${x@u}"
""".strip(),
    )


# ---------------------------------------------------------------------------
# Real-world: regex + POSIX class combined
# ---------------------------------------------------------------------------


def test_strip_non_alnum() -> None:
    compare(
        "strip_non_alnum",
        """
for s in "hello-world" "abc123" "a b c"; do
  out=${s//[^[:alnum:]]/}
  echo "[$out]"
done
""".strip(),
    )


def test_classify_input_lines() -> None:
    compare(
        "classify_input_lines",
        """
for line in "42" "hello" "a1b2" ""; do
  if [[ "$line" =~ ^[[:digit:]]+$ ]]; then
    echo "$line -> integer"
  elif [[ "$line" =~ ^[[:alpha:]]+$ ]]; then
    echo "$line -> word"
  elif [[ -z "$line" ]]; then
    echo "$line -> empty"
  else
    echo "$line -> mixed"
  fi
done
""".strip(),
    )


def test_extract_first_number() -> None:
    compare(
        "extract_first_number",
        r"""
s="error code 1234 in module 5"
if [[ "$s" =~ ([0-9]+) ]]; then
  echo "first=${BASH_REMATCH[1]}"
fi
""".strip(),
    )


def test_caller_aware_logger() -> None:
    compare(
        "caller_aware_logger",
        """
log() {
  local caller=${FUNCNAME[1]:-main}
  echo "[$caller] $*"
}
worker() {
  log "doing work"
}
worker
log "from top level"
""".strip(),
    )
