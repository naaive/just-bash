"""Variable scope, exported flags, function table, positional parameters.

Bash variables sit in nested scopes:
- The "global" scope, which is also where ``export`` stores environment.
- A stack of "local" scopes pushed when entering a function with ``local``.

Lookup is innermost-first; ``set``/``export`` writes to the appropriate scope.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from just_bash.ast.nodes import FunctionDef


@dataclass(slots=True)
class Variable:
    value: str = ""
    exported: bool = False
    readonly: bool = False
    array: list[str] | None = None
    assoc: dict[str, str] | None = None


@dataclass(slots=True)
class Function:
    name: str
    definition: FunctionDef


@dataclass(slots=True)
class Scope:
    """A flat name -> Variable mapping."""

    vars: dict[str, Variable] = field(default_factory=dict)


class Environment:
    """Variable + function environment for the interpreter.

    The bottom of ``self._scopes`` is the global scope. Function bodies push a
    new scope; ``local NAME`` writes there. Reads walk the stack from top to
    bottom and fall back to the global scope.
    """

    def __init__(self, *, initial_env: dict[str, str] | None = None) -> None:
        self._scopes: list[Scope] = [Scope()]
        self.functions: dict[str, Function] = {}
        self.positional: list[str] = []
        self.script_name: str = "just-bash"
        self.last_exit: int = 0
        self.last_pipeline_status: list[int] = []
        self.shell_options: set[str] = set()
        if initial_env:
            for k, v in initial_env.items():
                self.set_var(k, v, exported=True)

    # -------------------------------------------------------------- scoping
    @property
    def global_scope(self) -> Scope:
        return self._scopes[0]

    def push_scope(self) -> None:
        self._scopes.append(Scope())

    def pop_scope(self) -> None:
        if len(self._scopes) <= 1:
            raise RuntimeError("cannot pop global scope")
        self._scopes.pop()

    def in_function(self) -> bool:
        return len(self._scopes) > 1

    # ----------------------------------------------------------------- vars
    def get(self, name: str) -> str | None:
        v = self._lookup(name)
        if v is None:
            return None
        if v.array is not None:
            return v.array[0] if v.array else ""
        return v.value

    def get_var(self, name: str) -> Variable | None:
        return self._lookup(name)

    def _lookup(self, name: str) -> Variable | None:
        for scope in reversed(self._scopes):
            if name in scope.vars:
                return scope.vars[name]
        return None

    def has(self, name: str) -> bool:
        return self._lookup(name) is not None

    def set_var(
        self,
        name: str,
        value: str,
        *,
        exported: bool = False,
        local: bool = False,
        append: bool = False,
    ) -> None:
        scope = self._scopes[-1] if local else self._target_scope_for(name)
        existing = scope.vars.get(name)
        if existing is None and not local:
            existing = self.global_scope.vars.get(name)
            scope = self.global_scope
        if existing is None:
            scope.vars[name] = Variable(value=value, exported=exported)
            return
        if existing.readonly:
            raise PermissionError(f"{name}: readonly variable")
        if append:
            if existing.array is not None:
                existing.array.append(value)
            else:
                existing.value = (existing.value or "") + value
        else:
            existing.value = value
            existing.array = None
            existing.assoc = None
        if exported:
            existing.exported = True

    def _target_scope_for(self, name: str) -> Scope:
        for scope in reversed(self._scopes):
            if name in scope.vars:
                return scope
        return self.global_scope

    def set_array(
        self, name: str, values: list[str], *, exported: bool = False, local: bool = False
    ) -> None:
        scope = self._scopes[-1] if local else self.global_scope
        scope.vars[name] = Variable(
            value=values[0] if values else "", array=list(values), exported=exported
        )

    def get_array(self, name: str) -> list[str] | None:
        v = self._lookup(name)
        if v is None:
            return None
        return v.array

    def unset(self, name: str) -> None:
        for scope in reversed(self._scopes):
            if name in scope.vars:
                del scope.vars[name]
                return

    def export(self, name: str, value: str | None = None) -> None:
        v = self._lookup(name)
        if v is None:
            self.set_var(name, value or "", exported=True)
            return
        v.exported = True
        if value is not None:
            v.value = value

    # ------------------------------------------------------------- exporting
    def env_dict(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for scope in self._scopes:
            for name, v in scope.vars.items():
                if v.exported:
                    out[name] = v.value
        return out

    # ------------------------------------------------------------- functions
    def define_function(self, name: str, defn: FunctionDef) -> None:
        self.functions[name] = Function(name=name, definition=defn)

    def get_function(self, name: str) -> Function | None:
        return self.functions.get(name)

    def all_var_names(self) -> list[str]:
        names: set[str] = set()
        for scope in self._scopes:
            names.update(scope.vars.keys())
        return sorted(names)


__all__ = ["Environment", "Function", "Scope", "Variable"]
