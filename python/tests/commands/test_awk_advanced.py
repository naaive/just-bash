"""Advanced awk: control flow, UDFs, builtin functions."""

from __future__ import annotations


def test_user_defined_function(run) -> None:
    r = run("""
awk '
function double(x) {
  return x * 2
}
{ print double($1) }' <<EOF
3
5
10
EOF
""")
    assert r.stdout == "6\n10\n20\n"


def test_function_with_local_array(run) -> None:
    r = run("""
awk '
function count_words(line, n, parts) {
  n = split(line, parts, " ")
  return n
}
{ print count_words($0) }' <<EOF
a b c
hello world
EOF
""")
    assert r.stdout == "3\n2\n"


def test_if_else_in_action(run) -> None:
    r = run("""
awk '{
  if ($1 % 2 == 0) print "even", $1
  else print "odd", $1
}' <<EOF
1
2
3
4
EOF
""")
    assert r.stdout == "odd 1\neven 2\nodd 3\neven 4\n"


def test_while_loop(run) -> None:
    r = run("awk 'BEGIN { i = 0; while (i < 5) { print i; i++ } }'", stdin=b"")
    assert r.stdout == "0\n1\n2\n3\n4\n"


def test_c_style_for_loop(run) -> None:
    r = run("awk 'BEGIN { for (i = 0; i < 3; i++) print i }'", stdin=b"")
    assert r.stdout == "0\n1\n2\n"


def test_for_in_array(run) -> None:
    r = run("""
awk 'BEGIN {
  a["one"] = 1
  a["two"] = 2
  a["three"] = 3
  total = 0
  for (k in a) total += a[k]
  print total
}'
""")
    assert r.stdout == "6\n"


def test_break_and_continue(run) -> None:
    r = run("""
awk 'BEGIN {
  for (i = 0; i < 10; i++) {
    if (i == 3) continue
    if (i == 6) break
    print i
  }
}'
""")
    assert r.stdout == "0\n1\n2\n4\n5\n"


def test_next_skips_rest_of_rules(run) -> None:
    r = run("""
awk '
/^skip/ { next }
{ print "kept:", $0 }' <<EOF
keep me
skip this
keep me too
EOF
""")
    assert r.stdout == "kept: keep me\nkept: keep me too\n"


def test_substr_index_length(run) -> None:
    r = run(
        'awk \'BEGIN { s = "hello world"; print substr(s, 7); print index(s, "wor"); print length(s) }\''
    )
    assert r.stdout == "world\n7\n11\n"


def test_split_into_array(run) -> None:
    r = run("""
awk 'BEGIN {
  n = split("alpha,beta,gamma", a, ",")
  print n, a[1], a[2], a[3]
}'
""")
    assert r.stdout == "3 alpha beta gamma\n"


def test_gsub(run) -> None:
    r = run("awk '{ gsub(/o/, \"0\"); print }'", stdin=b"hello world\nfoo bar\n")
    assert r.stdout == "hell0 w0rld\nf00 bar\n"


def test_toupper_tolower(run) -> None:
    r = run('awk \'BEGIN { print toupper("hi"); print tolower("HI") }\'')
    assert r.stdout == "HI\nhi\n"


def test_sprintf(run) -> None:
    r = run("awk 'BEGIN { print sprintf(\"%05d\", 42) }'")
    assert r.stdout == "00042\n"


def test_printf_field(run) -> None:
    r = run("awk '{ printf \"[%-10s]\\n\", $1 }'", stdin=b"hi\nhello\n")
    assert r.stdout == "[hi        ]\n[hello     ]\n"


def test_regex_match_operator(run) -> None:
    r = run("awk '$0 ~ /foo/ { print \"match:\", $0 }'", stdin=b"foo\nbar\nfoobar\n")
    assert r.stdout == "match: foo\nmatch: foobar\n"


def test_associative_array_membership(run) -> None:
    r = run("""
awk 'BEGIN {
  a["x"] = 1
  a["y"] = 2
  if ("x" in a) print "yes"
  if (!("z" in a)) print "no"
}'
""")
    assert r.stdout == "yes\nno\n"


def test_nested_functions(run) -> None:
    r = run("""
awk '
function add(a, b) { return a + b }
function double(x) { return add(x, x) }
BEGIN { print double(7) }
'
""")
    assert r.stdout == "14\n"


def test_recursion(run) -> None:
    r = run("""
awk '
function fact(n) {
  if (n <= 1) return 1
  return n * fact(n - 1)
}
BEGIN { print fact(5) }
'
""")
    assert r.stdout == "120\n"


def test_exit_with_code(run) -> None:
    r = run("""
awk 'BEGIN { print "hi"; exit 3 }; { print "never" }' <<EOF
ignored
EOF
""")
    assert r.stdout == "hi\n"
    assert r.exit_code == 3
