"""External-command implementations.

Each command is a function ``(interp, argv, io) -> exit_code`` registered in
``registry.default_registry``.
"""

from just_bash.commands.registry import default_registry

__all__ = ["default_registry"]
