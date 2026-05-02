"""Advanced sed: hold space, branches, transliteration, change/insert/append."""

from __future__ import annotations


def test_hold_space_h_g(run) -> None:
    # h saves to hold, G appends hold to pattern -> doubled output.
    r = run("printf '1\\n2\\n3\\n' | sed -n 'h; G; p'")
    assert r.stdout == "1\n1\n2\n2\n3\n3\n"


def test_hold_space_x(run) -> None:
    r = run("printf 'a\\nb\\n' | sed 'x'")
    # x swaps hold and pattern. Hold starts empty, so:
    # line 1: pattern="a" hold="", swap -> pattern="" hold="a", print ""
    # line 2: pattern="b" hold="a", swap -> pattern="a" hold="b", print "a"
    assert r.stdout == "\na\n"


def test_y_transliterate(run) -> None:
    r = run("echo hello | sed 'y/aeiou/AEIOU/'")
    assert r.stdout == "hEllO\n"


def test_branch_unconditional(run) -> None:
    r = run("printf '1\\n2\\n3\\n' | sed -n '/2/b end; p; :end'")
    assert r.stdout == "1\n3\n"


def test_branch_conditional_t(run) -> None:
    r = run("printf 'foo\\nbar\\n' | sed 's/foo/REPL/; t end; p; :end'")
    # foo→REPL: t branches over p, so prints "REPL" only once.
    # bar: no sub, p prints "bar", final auto-print also "bar".
    assert r.stdout == "REPL\nbar\nbar\n"


def test_append_a_command(run) -> None:
    r = run("printf 'a\\nb\\n' | sed '1a\\\nINSERTED'")
    # ``1a TEXT`` appends after line 1.
    assert "INSERTED" in r.stdout
    assert r.stdout.startswith("a\nINSERTED")


def test_change_c_command(run) -> None:
    r = run("printf 'a\\nb\\nc\\n' | sed '2c\\\nCHANGED'")
    # Replaces line 2 with "CHANGED".
    assert "CHANGED" in r.stdout


def test_negated_address(run) -> None:
    r = run("printf '1\\n2\\n3\\n' | sed -n '2!p'")
    # Print all lines except line 2.
    assert r.stdout == "1\n3\n"


def test_grouped_block(run) -> None:
    r = run("printf 'a\\nb\\nc\\n' | sed '2,3{s/.*/X/}'")
    assert r.stdout == "a\nX\nX\n"


def test_substitute_with_p_flag(run) -> None:
    # ``-n`` quiet, ``s/.../.../p`` prints only when the substitution matched.
    r = run("printf 'foo\\nbar\\n' | sed -n 's/foo/baz/p'")
    assert r.stdout == "baz\n"


def test_extended_regex(run) -> None:
    r = run('echo "abc123" | sed -E "s/([a-z]+)([0-9]+)/\\\\2-\\\\1/"')
    assert r.stdout == "123-abc\n"


def test_double_address_range(run) -> None:
    r = run("printf '1\\n2\\n3\\n4\\n5\\n' | sed -n '2,4p'")
    assert r.stdout == "2\n3\n4\n"
