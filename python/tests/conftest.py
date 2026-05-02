"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

from just_bash.fs.vfs import VirtualFs
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.interpreter import ExecResult, Interpreter
from just_bash.parser.parser import parse


@pytest.fixture()
def fs() -> VirtualFs:
    f = VirtualFs()
    f.mkdir("/home/user/project", parents=True, exist_ok=True)
    f.chdir("/home/user/project")
    return f


@pytest.fixture()
def env() -> Environment:
    return Environment(initial_env={"PATH": "/usr/bin:/bin", "HOME": "/root", "IFS": " \t\n"})


@pytest.fixture()
def interp(fs: VirtualFs, env: Environment) -> Interpreter:
    return Interpreter(fs=fs, env=env)


def run_script(interp: Interpreter, source: str, *, stdin: bytes = b"") -> ExecResult:
    script = parse(source)
    return interp.run_script_capture(script, stdin=stdin)


@pytest.fixture()
def run(interp: Interpreter):
    """Returns a callable: ``run(source, stdin=b"") -> ExecResult``."""

    def _run(source: str, *, stdin: bytes = b"") -> ExecResult:
        return run_script(interp, source, stdin=stdin)

    return _run
