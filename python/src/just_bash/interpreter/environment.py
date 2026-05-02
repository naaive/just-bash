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
        # Trap handlers, keyed by signal name (``EXIT``, ``ERR``, ``INT``, ...).
        # ``""`` value disables the trap; absence means default behavior.
        self.traps: dict[str, str] = {}
        # Approximation of ``$SECONDS`` - we record the wall-clock origin and
        # read it on demand. ``$RANDOM`` reads from a deterministic generator
        # (seeded from ``$RANDOM`` writes when set).
        import random
        import time

        self._start_time = time.monotonic()
        self._rng = random.Random()
        # Pre-populate well-known introspection variables so script preambles
        # that reference ``$BASH_VERSION`` etc. don't break.
        self.set_var("BASH_VERSION", "5.2.21(1)-just-bash-py")
        self.set_var("BASH", "/usr/bin/bash")
        self.set_var("BASH_SOURCE", "")
        self.set_var("BASHPID", "1")
        self.set_var("EUID", "1000")
        self.set_var("UID", "1000")
        self.set_var("HOSTNAME", "sandbox")
        self.set_var("HOSTTYPE", "x86_64")
        self.set_var("MACHTYPE", "x86_64-pc-linux-gnu")
        self.set_var("OSTYPE", "linux-gnu")
        self.set_var("PPID", "0")
        self.set_var("RANDOM", "0")
        self.set_var("LINENO", "0")
        self.set_var("SHELL", "/bin/bash")
        self.set_var("SHLVL", "1")
        self.set_var("SECONDS", "0")
        self.set_var("OPTIND", "1")
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
        # Computed introspection vars: re-evaluate on each read.
        if name == "SECONDS":
            import time

            return str(int(time.monotonic() - self._start_time))
        if name == "RANDOM":
            return str(self._rng.randrange(0, 32768))
        if name == "EPOCHSECONDS":
            import time

            return str(int(time.time()))
        if name == "EPOCHREALTIME":
            import time

            return f"{time.time():.6f}"
        if name == "SRANDOM":
            return str(self._rng.randrange(0, 2**32))
        if name == "PIPESTATUS":
            return str(self.last_pipeline_status[-1]) if self.last_pipeline_status else "0"
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
        existing = scope.vars.get(name)
        # If the variable was previously declared associative, treat the words
        # as ``key=value`` assignments (matches ``declare -A m; m=(a 1 b 2)``).
        if existing is not None and existing.assoc is not None:
            assoc: dict[str, str] = {}
            for v in values:
                if "=" in v:
                    k, _, val = v.partition("=")
                    assoc[k] = val
            existing.assoc = assoc
            existing.value = ""
            existing.exported = existing.exported or exported
            return
        scope.vars[name] = Variable(
            value=values[0] if values else "", array=list(values), exported=exported
        )

    def declare_assoc(self, name: str, *, exported: bool = False, local: bool = False) -> None:
        """Mark ``name`` as an associative array (``declare -A``)."""
        scope = self._scopes[-1] if local else self.global_scope
        existing = scope.vars.get(name)
        if existing is not None:
            if existing.assoc is None:
                existing.assoc = {}
            existing.exported = existing.exported or exported
            return
        scope.vars[name] = Variable(value="", assoc={}, exported=exported)

    def set_assoc_element(self, name: str, key: str, value: str) -> None:
        """Set ``arr[key] = value`` for an associative array."""
        v = self._lookup(name)
        if v is None:
            self.global_scope.vars[name] = Variable(value="", assoc={key: value})
            return
        if v.assoc is None:
            v.assoc = {}
        v.assoc[key] = value

    def set_array_element(self, name: str, index: int, value: str) -> None:
        """Set ``arr[index] = value`` for an indexed array (auto-extends)."""
        v = self._lookup(name)
        if v is None:
            arr = [""] * index + [value]
            self.global_scope.vars[name] = Variable(value=value if index == 0 else "", array=arr)
            return
        if v.assoc is not None:
            v.assoc[str(index)] = value
            return
        if v.array is None:
            v.array = [v.value]
        while len(v.array) <= index:
            v.array.append("")
        v.array[index] = value
        if index == 0:
            v.value = value

    def get_array(self, name: str) -> list[str] | None:
        v = self._lookup(name)
        if v is None:
            return None
        return v.array

    def get_assoc(self, name: str) -> dict[str, str] | None:
        v = self._lookup(name)
        if v is None:
            return None
        return v.assoc

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
