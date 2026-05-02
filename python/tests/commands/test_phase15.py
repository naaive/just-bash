"""Phase-15 language tests: POSIX char classes, regex captures, FUNCNAME stack,
${var@Q} quoting, function-keyword definitions."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# POSIX character classes in case patterns
# ---------------------------------------------------------------------------


def test_case_posix_digit(run) -> None:
    r = run("""
case 7 in
  [[:digit:]]) echo digit ;;
  *) echo other ;;
esac
""")
    assert r.stdout == "digit\n"


def test_case_posix_alpha(run) -> None:
    r = run("""
case Z in
  [[:alpha:]]) echo alpha ;;
  *) echo other ;;
esac
""")
    assert r.stdout == "alpha\n"


def test_case_posix_space(run) -> None:
    r = run("""
case ' ' in
  [[:space:]]) echo space ;;
  *) echo other ;;
esac
""")
    assert r.stdout == "space\n"


def test_case_posix_punct(run) -> None:
    r = run("""
case '!' in
  [[:punct:]]) echo punct ;;
  *) echo other ;;
esac
""")
    assert r.stdout == "punct\n"


def test_case_posix_xdigit(run) -> None:
    r = run("""
for ch in 9 a F z; do
  case "$ch" in
    [[:xdigit:]]) echo "$ch hex" ;;
    *) echo "$ch no" ;;
  esac
done
""")
    assert r.stdout == "9 hex\na hex\nF hex\nz no\n"


# ---------------------------------------------------------------------------
# POSIX class in [[ ]] conditional
# ---------------------------------------------------------------------------


def test_double_brackets_posix_digit(run) -> None:
    r = run("""
v=42
if [[ "$v" == *[[:digit:]]* ]]; then echo numeric; else echo no; fi
""")
    assert r.stdout == "numeric\n"


# ---------------------------------------------------------------------------
# Regex with capture groups + BASH_REMATCH
# ---------------------------------------------------------------------------


def test_regex_capture_groups(run) -> None:
    r = run(r"""
if [[ "version=1.2.3" =~ version=([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
  echo "${BASH_REMATCH[1]}.${BASH_REMATCH[2]}.${BASH_REMATCH[3]}"
  echo "full=${BASH_REMATCH[0]}"
fi
""")
    assert r.stdout == "1.2.3\nfull=version=1.2.3\n"


def test_regex_no_match_clears_rematch(run) -> None:
    r = run(r"""
[[ "abc" =~ ^x([0-9]+)y$ ]]
echo "rc=$?"
echo "len=${#BASH_REMATCH[@]}"
""")
    assert r.stdout == "rc=1\nlen=0\n"


def test_regex_alternation(run) -> None:
    r = run(r"""
for s in apple banana cherry; do
  if [[ "$s" =~ ^(apple|cherry)$ ]]; then
    echo "$s: hit (${BASH_REMATCH[1]})"
  else
    echo "$s: miss"
  fi
done
""")
    assert r.stdout == "apple: hit (apple)\nbanana: miss\ncherry: hit (cherry)\n"


# ---------------------------------------------------------------------------
# function NAME { ... } / function NAME() { ... } definitions
# ---------------------------------------------------------------------------


def test_function_keyword_no_parens(run) -> None:
    r = run("""
function greet {
  echo "hi $1"
}
greet alice
""")
    assert r.stdout == "hi alice\n"


def test_function_keyword_with_parens(run) -> None:
    r = run("""
function bye() {
  echo "bye $1"
}
bye bob
""")
    assert r.stdout == "bye bob\n"


# ---------------------------------------------------------------------------
# FUNCNAME / BASH_SOURCE / BASH_LINENO arrays
# ---------------------------------------------------------------------------


def test_funcname_inside_function(run) -> None:
    r = run("""
inner() {
  echo "${FUNCNAME[0]}"
}
inner
""")
    assert r.stdout == "inner\n"


def test_funcname_call_chain(run) -> None:
    r = run("""
inner() {
  echo "${FUNCNAME[0]} <- ${FUNCNAME[1]}"
  echo "depth=${#FUNCNAME[@]}"
}
outer() {
  inner
}
outer
""")
    # ``bash -c`` (our harness) gives depth = inner + outer = 2.
    assert r.stdout == "inner <- outer\ndepth=2\n"


def test_funcname_top_level_empty(run) -> None:
    r = run('echo "depth=${#FUNCNAME[@]}"')
    assert r.stdout == "depth=0\n"


def test_bash_source_in_function(run) -> None:
    r = run("""
inner() {
  echo "${BASH_SOURCE[0]}"
}
inner
""")
    assert r.stdout == "main\n"


# ---------------------------------------------------------------------------
# ${var@Q} / @U / @L / @E
# ---------------------------------------------------------------------------


def test_at_q_plain(run) -> None:
    r = run('x=hello; echo "${x@Q}"')
    assert r.stdout == "'hello'\n"


def test_at_q_with_space(run) -> None:
    r = run("""x="hello world"; echo "${x@Q}" """)
    assert r.stdout == "'hello world'\n"


def test_at_q_with_quote(run) -> None:
    r = run("""x="don't"; echo "${x@Q}" """)
    assert r.stdout == "'don'\\''t'\n"


def test_at_u_uppercase(run) -> None:
    r = run("""x="hello"; echo "${x@U}" """)
    assert r.stdout == "HELLO\n"


def test_at_l_lowercase(run) -> None:
    r = run("""x="HELLO"; echo "${x@L}" """)
    assert r.stdout == "hello\n"


def test_at_u_capitalize_first(run) -> None:
    r = run("""x="hello"; echo "${x@u}" """)
    assert r.stdout == "Hello\n"


def test_at_e_interprets_escapes(run) -> None:
    r = run(r"""x='a\tb\nc'; printf '%s' "${x@E}" """)
    assert r.stdout == "a\tb\nc"
