"""just-bash-py: a sandboxed bash interpreter with an in-memory virtual filesystem."""

from just_bash.interpreter.interpreter import ExecResult, Interpreter, run
from just_bash.parser.parser import parse

__all__ = ["ExecResult", "Interpreter", "parse", "run"]
__version__ = "0.1.0"
