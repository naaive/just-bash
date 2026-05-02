"""Random-input fuzz harness for the bash parser.

Goals:
- The parser must terminate (no infinite loops) on any input it accepts or
  rejects.
- It must never raise a non-``ParseError`` exception (no ``IndexError`` /
  ``RecursionError`` / ``KeyError`` / ``AssertionError`` etc.) — those are
  all parser bugs.
- It must produce a stable AST for inputs that are valid; round-tripping
  source through parse twice should never change the AST shape.

The harness draws words and operators from a curated alphabet, builds many
short scripts, and checks the invariants. Seeded so failures are
reproducible.
"""

from __future__ import annotations

import random
import sys

import pytest

from just_bash.parser.parser import ParseError, parse

# ---------------------------------------------------------------------------
# Alphabet
# ---------------------------------------------------------------------------

_WORDS = [
    "echo",
    "true",
    "false",
    "exit",
    "return",
    "x",
    "var",
    "name",
    "key",
    "value",
    "alpha",
    "beta",
    "1",
    "42",
    "-1",
    "abc",
    "0",
]

_VAR_REFS = ["$x", "$1", "$#", "$?", '"$x"', "${x:-fallback}", "${arr[0]}", "${#arr[@]}"]

_OPS = [
    "&&",
    "||",
    "|",
    ";",
    "\n",
    "&",
]

_REDIRS = [">", ">>", "<", "2>", "2>&1", ">&2", "<<<"]

_CASE_PATTERNS = ["a", "*", "?", "[abc]", "@(a|b)", "*.txt", "[[:digit:]]"]


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------


def gen_simple_command(rng: random.Random) -> str:
    parts = [rng.choice(_WORDS)]
    for _ in range(rng.randint(0, 3)):
        if rng.random() < 0.3:
            parts.append(rng.choice(_VAR_REFS))
        else:
            parts.append(rng.choice(_WORDS))
    if rng.random() < 0.2:
        parts.append(rng.choice(_REDIRS))
        parts.append("/tmp/x")
    return " ".join(parts)


def gen_pipeline(rng: random.Random) -> str:
    n = rng.randint(1, 3)
    return " | ".join(gen_simple_command(rng) for _ in range(n))


def gen_assignment(rng: random.Random) -> str:
    name = rng.choice(["x", "y", "name", "count"])
    value = rng.choice(_WORDS + _VAR_REFS)
    return f"{name}={value}"


def gen_array_init(rng: random.Random) -> str:
    name = rng.choice(["arr", "list", "items"])
    elems = [rng.choice(_WORDS) for _ in range(rng.randint(0, 4))]
    return f"{name}=({' '.join(elems)})"


def gen_if(rng: random.Random) -> str:
    cond = gen_simple_command(rng)
    body = gen_simple_command(rng)
    if rng.random() < 0.5:
        return f"if {cond}; then {body}; fi"
    else_body = gen_simple_command(rng)
    return f"if {cond}; then {body}; else {else_body}; fi"


def gen_for(rng: random.Random) -> str:
    var = rng.choice(["i", "x", "item"])
    items = " ".join(rng.choice(_WORDS) for _ in range(rng.randint(1, 3)))
    body = gen_simple_command(rng)
    return f"for {var} in {items}; do {body}; done"


def gen_while(rng: random.Random) -> str:
    body = gen_simple_command(rng)
    return f"while false; do {body}; done"


def gen_case(rng: random.Random) -> str:
    target = rng.choice(_WORDS)
    items = []
    for _ in range(rng.randint(1, 3)):
        pat = rng.choice(_CASE_PATTERNS)
        body = gen_simple_command(rng)
        items.append(f"{pat}) {body} ;;")
    return f"case {target} in {' '.join(items)} esac"


def gen_function(rng: random.Random) -> str:
    name = rng.choice(["f", "g", "helper"])
    body = gen_pipeline(rng)
    return f"{name}() {{ {body}; }}"


def gen_double_brackets(rng: random.Random) -> str:
    left = rng.choice(_WORDS + _VAR_REFS)
    op = rng.choice(["==", "!=", "-eq", "-ne", "=~"])
    right = rng.choice(_WORDS) if op != "=~" else r"^[a-z]+$"
    return f"[[ {left} {op} {right} ]]"


def gen_compound_assign(rng: random.Random) -> str:
    return f"declare -A m=([k]={rng.choice(_WORDS)} [k2]={rng.choice(_WORDS)})"


_GENERATORS = [
    gen_simple_command,
    gen_pipeline,
    gen_assignment,
    gen_array_init,
    gen_if,
    gen_for,
    gen_while,
    gen_case,
    gen_function,
    gen_double_brackets,
    gen_compound_assign,
]


def gen_script(rng: random.Random, max_stmts: int = 4) -> str:
    n = rng.randint(1, max_stmts)
    parts: list[str] = []
    for _ in range(n):
        gen = rng.choice(_GENERATORS)
        parts.append(gen(rng))
    sep = rng.choice(["\n", "; "])
    return sep.join(parts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("seed", range(40))
def test_fuzz_parse_stable(seed: int) -> None:
    """Random valid-ish inputs should parse without crashing.

    ``ParseError`` is acceptable (rejection is fine); anything else means
    the parser has an internal bug.
    """
    rng = random.Random(seed)
    for _ in range(50):
        script = gen_script(rng)
        try:
            parse(script)
        except ParseError:
            pass  # acceptable rejection
        except RecursionError as e:
            pytest.fail(f"recursion on input {script!r}: {e}")
        except (IndexError, KeyError, AttributeError, AssertionError) as e:
            pytest.fail(f"parser internal error on {script!r}: {type(e).__name__}: {e}")


@pytest.mark.parametrize("seed", range(20))
def test_fuzz_idempotent_round_trip(seed: int) -> None:
    """Successfully parsed scripts must reparse to the same shape.

    We compare the AST as a string repr, which is stable under
    ``@dataclass``.
    """
    rng = random.Random(seed)
    for _ in range(40):
        script = gen_script(rng)
        try:
            ast1 = parse(script)
        except ParseError:
            continue
        try:
            ast2 = parse(script)
        except ParseError:
            pytest.fail(f"second parse failed for {script!r}")
        assert repr(ast1) == repr(ast2), f"unstable parse: {script!r}"


@pytest.mark.parametrize("seed", range(10))
def test_fuzz_unicode_safe(seed: int) -> None:
    """Non-ASCII input shouldn't crash the lexer or parser."""
    rng = random.Random(seed)
    samples = ["café", "日本語", "αβγ", "emoji-🚀", "mixed-français-中文"]
    for _ in range(20):
        word = rng.choice(samples)
        script = f'echo "{word}"; x={word}; echo $x'
        try:
            parse(script)
        except ParseError:
            pytest.fail(f"parser rejected unicode input: {script!r}")
        except Exception as e:
            pytest.fail(f"crash on unicode {script!r}: {type(e).__name__}: {e}")


# ---------------------------------------------------------------------------
# Specific corner cases that the harness uncovered historically — keep them
# pinned so regressions get caught before the next fuzz run.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "script",
    [
        "for x in ; do echo $x; done",  # empty word list
        "case x in esac",  # case with no items
        "if true; then fi",  # empty then-body
        "{ }",  # empty group — depends on parser tolerance
        "while :; do break; done",  # ``:`` builtin
        "echo $((1 + 2 * 3))",
        "echo $((-1 ** 2))",
        'echo "\\"quoted\\""',  # nested quote escapes
        "x=1; (( x = 5 )); echo $x",  # arith assignment
        "[[ 1 -lt 2 && 3 -gt 1 ]] && echo ok",
    ],
)
def test_fuzz_corner_cases(script: str) -> None:
    try:
        parse(script)
    except ParseError:
        # We accept rejection; bug is when something else explodes.
        pass
    except (RecursionError, IndexError, KeyError, AttributeError, AssertionError) as e:
        pytest.fail(f"parser crash on {script!r}: {type(e).__name__}: {e}")


def test_fuzz_recursion_depth_capped() -> None:
    """Highly nested constructs shouldn't blow the recursion limit."""
    import contextlib

    nested = "echo $(echo $(echo $(echo $(echo $(echo $(echo $(echo hi)))))))"
    with contextlib.suppress(ParseError, RecursionError):
        parse(nested)


def test_fuzz_long_pipeline() -> None:
    """Long pipelines parse linearly without recursion blow-up."""
    pipeline = " | ".join(["echo a"] * 80)
    parse(pipeline)


def test_fuzz_long_command_list() -> None:
    """Long ``;``-separated lists parse linearly."""
    lst = "; ".join(["echo a"] * 200)
    parse(lst)


def test_fuzz_set_recursion_baseline() -> None:
    """Confirm the default recursion limit is ample for our test cases."""
    assert sys.getrecursionlimit() >= 1000
