"""Heredoc redirection tests."""

from __future__ import annotations


def test_basic_heredoc(run) -> None:
    r = run("cat <<EOF\nhello\nworld\nEOF\n")
    assert r.stdout == "hello\nworld\n"


def test_heredoc_with_expansion(run) -> None:
    r = run("name=alice\ncat <<EOF\nhi $name\nEOF\n")
    assert r.stdout == "hi alice\n"


def test_heredoc_quoted_delimiter_no_expansion(run) -> None:
    # Single-quoted delimiter prevents expansion of the body.
    r = run("name=alice\ncat <<'EOF'\nhi $name\nEOF\n")
    assert r.stdout == "hi $name\n"


def test_heredoc_strip_tabs(run) -> None:
    r = run("cat <<-EOF\n\there\n\tthere\n\tEOF\n")
    assert r.stdout == "here\nthere\n"


def test_heredoc_with_command_substitution(run) -> None:
    r = run("cat <<EOF\ndate is $(echo today)\nEOF\n")
    assert r.stdout == "date is today\n"


def test_heredoc_then_redirect(run, fs) -> None:
    fs.mkdir("/tmp", parents=True, exist_ok=True)
    r = run("cat <<EOF > /tmp/out\nhello\nEOF\n")
    assert r.exit_code == 0
    assert fs.read_text("/tmp/out") == "hello\n"


def test_heredoc_in_function(run) -> None:
    r = run("""
greet() {
  cat <<EOF
hi $1
EOF
}
greet world
""")
    assert r.stdout == "hi world\n"


def test_here_string(run) -> None:
    r = run('cat <<< "hello world"')
    assert r.stdout == "hello world\n"
