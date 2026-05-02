"""Control-flow exceptions and the public ``InterpreterError`` type.

Why exceptions for control flow: ``break`` / ``continue`` / ``return`` /
``exit`` need to unwind multiple loop / function frames cleanly, and Python's
exception machinery is the simplest way to do that without threading a return
value through every interpreter method.
"""

from __future__ import annotations


class InterpreterError(Exception):
    """Raised for shell errors that should be reported to stderr."""

    def __init__(self, message: str, exit_code: int = 1) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class BreakException(Exception):
    """``break N`` - unwind ``levels`` enclosing loops."""

    def __init__(self, levels: int = 1) -> None:
        super().__init__("break")
        self.levels = levels


class ContinueException(Exception):
    """``continue N`` - skip to the next iteration of the Nth loop."""

    def __init__(self, levels: int = 1) -> None:
        super().__init__("continue")
        self.levels = levels


class ReturnException(Exception):
    """``return N`` from a function or sourced script."""

    def __init__(self, code: int = 0) -> None:
        super().__init__("return")
        self.code = code


class ExitException(Exception):
    """``exit N`` - tear down the whole interpreter."""

    def __init__(self, code: int = 0) -> None:
        super().__init__("exit")
        self.code = code
