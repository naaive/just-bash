"""Parser AST shape tests."""

from __future__ import annotations

from just_bash.ast.nodes import (
    ArithmeticCommand,
    Case,
    DoubleQuoted,
    For,
    FunctionDef,
    Group,
    If,
    Literal,
    ParameterExpansion,
    Pipeline,
    SimpleCommand,
    SingleQuoted,
    Subshell,
    While,
)
from just_bash.parser.parser import parse


def test_simple_command_parses() -> None:
    script = parse("echo hello")
    assert len(script.statements) == 1
    pipeline = script.statements[0].pipelines[0]
    assert isinstance(pipeline, Pipeline)
    cmd = pipeline.commands[0]
    assert isinstance(cmd, SimpleCommand)
    assert cmd.name is not None
    assert len(cmd.name.parts) == 1
    name_part = cmd.name.parts[0]
    assert isinstance(name_part, Literal)
    assert name_part.value == "echo"
    assert len(cmd.args) == 1


def test_pipeline_two_commands() -> None:
    script = parse("a | b")
    pipeline = script.statements[0].pipelines[0]
    assert len(pipeline.commands) == 2


def test_and_or_chain() -> None:
    script = parse("a && b || c")
    stmt = script.statements[0]
    assert len(stmt.pipelines) == 3
    assert stmt.operators == ["&&", "||"]


def test_if_then_else_fi() -> None:
    script = parse("if true; then echo a; else echo b; fi")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, If)
    assert len(cmd.clauses) == 1
    assert cmd.else_body is not None


def test_for_loop_with_words() -> None:
    script = parse("for x in 1 2 3; do echo $x; done")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, For)
    assert cmd.variable == "x"
    assert cmd.words is not None
    assert len(cmd.words) == 3


def test_while_loop() -> None:
    script = parse("while false; do echo hi; done")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, While)


def test_case_statement() -> None:
    script = parse("case foo in bar) echo b ;; foo) echo f ;; esac")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, Case)
    assert len(cmd.items) == 2


def test_function_definition_paren() -> None:
    script = parse("greet() { echo hi; }")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, FunctionDef)
    assert cmd.name == "greet"
    assert isinstance(cmd.body, Group)


def test_function_definition_keyword() -> None:
    script = parse("function greet { echo hi; }")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, FunctionDef)
    assert cmd.name == "greet"


def test_arithmetic_command() -> None:
    script = parse("(( x = 1 + 2 ))")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, ArithmeticCommand)


def test_subshell() -> None:
    script = parse("( cd /tmp; echo hi )")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, Subshell)


def test_assignments_before_command() -> None:
    script = parse("X=1 Y=2 echo hi")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, SimpleCommand)
    assert [a.name for a in cmd.assignments] == ["X", "Y"]


def test_word_with_double_quoted_param() -> None:
    script = parse('echo "hi $name"')
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, SimpleCommand)
    arg = cmd.args[0]
    assert isinstance(arg.parts[0], DoubleQuoted)
    inner = arg.parts[0].parts
    assert any(isinstance(p, ParameterExpansion) for p in inner)


def test_word_with_single_quoted() -> None:
    script = parse("echo 'hello world'")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, SimpleCommand)
    parts = cmd.args[0].parts
    assert isinstance(parts[0], SingleQuoted)
    assert parts[0].value == "hello world"


def test_redirection_to_file() -> None:
    script = parse("echo hi > /tmp/out")
    cmd = script.statements[0].pipelines[0].commands[0]
    assert isinstance(cmd, SimpleCommand)
    assert len(cmd.redirections) == 1
    assert cmd.redirections[0].operator == ">"


def test_negated_pipeline() -> None:
    script = parse("! true | false")
    pipeline = script.statements[0].pipelines[0]
    assert pipeline.negated is True
