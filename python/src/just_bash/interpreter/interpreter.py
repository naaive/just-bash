"""Tree-walking interpreter and command dispatcher.

The interpreter walks the AST produced by ``just_bash.parser`` and executes it
against an in-memory environment + virtual filesystem. Stdin / stdout / stderr
are byte buffers; pipes are stitched together by feeding one command's stdout
into the next command's stdin in process.
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Callable
from dataclasses import dataclass, field

from just_bash.ast.nodes import (
    ArithmeticCommand,
    Assignment,
    Case,
    Command,
    CompoundCommand,
    ConditionalCommand,
    For,
    FunctionDef,
    Group,
    HereDoc,
    If,
    Pipeline,
    Redirection,
    Script,
    SimpleCommand,
    Statement,
    Subshell,
    Until,
    While,
    Word,
)
from just_bash.fs.vfs import VirtualFs
from just_bash.interpreter.arithmetic import eval_arith
from just_bash.interpreter.conditionals import eval_conditional
from just_bash.interpreter.environment import Environment
from just_bash.interpreter.errors import (
    BreakException,
    ContinueException,
    ExitException,
    InterpreterError,
    ReturnException,
)
from just_bash.interpreter.expansion import expand_pattern, expand_word, expand_word_no_split
from just_bash.parser.parser import parse


@dataclass(slots=True)
class ExecResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


@dataclass(slots=True)
class IO:
    """Standard stream byte buffers for one execution context."""

    stdin: bytes = b""
    stdout: io.BytesIO = field(default_factory=io.BytesIO)
    stderr: io.BytesIO = field(default_factory=io.BytesIO)


CommandImpl = Callable[["Interpreter", "list[str]", "IO"], int]


class Interpreter:
    """Walks an AST and executes it. One ``Interpreter`` per logical run."""

    def __init__(
        self,
        *,
        fs: VirtualFs | None = None,
        env: Environment | None = None,
        commands: dict[str, CommandImpl] | None = None,
    ) -> None:
        self.fs = fs or VirtualFs()
        self.env = env or Environment(
            initial_env={"PATH": "/usr/bin:/bin", "HOME": "/root", "IFS": " \t\n"}
        )
        from just_bash.commands.registry import default_registry

        self.commands: dict[str, CommandImpl] = dict(default_registry())
        if commands:
            self.commands.update(commands)
        from just_bash.interpreter.builtins import default_builtins

        self.builtins: dict[str, CommandImpl] = default_builtins()
        # Counter for unique paths assigned to process-substitution outputs.
        self._procsub_counter: int = 0
        # Pending ``>(cmd)`` deferred execution targets, drained per pipeline.
        self._pending_output_subs: list[tuple[str, Script]] = []

    # ---------------------------------------------------------------- script
    def run_script(self, script: Script) -> int:
        io_ctx = IO(stdin=b"", stdout=self._make_stream(), stderr=self._make_stream())
        try:
            for stmt in script.statements:
                self._run_statement(stmt, io_ctx)
        except ExitException as e:
            return e.code
        return self.env.last_exit

    def run_script_capture(self, script: Script, stdin: bytes = b"") -> ExecResult:
        io_ctx = IO(stdin=stdin)
        try:
            for stmt in script.statements:
                self._run_statement(stmt, io_ctx)
        except ExitException as e:
            self.env.last_exit = e.code
        finally:
            self._fire_trap("EXIT", io_ctx)
        return ExecResult(
            stdout=io_ctx.stdout.getvalue().decode("utf-8", errors="replace"),
            stderr=io_ctx.stderr.getvalue().decode("utf-8", errors="replace"),
            exit_code=self.env.last_exit,
        )

    def _fire_trap(self, signal_name: str, io_ctx: IO) -> None:
        """Invoke the registered handler for ``signal_name`` if any.

        The script's overall exit code is preserved across the handler so a
        ``trap '...' EXIT`` cleanup doesn't stomp on a meaningful exit.
        """
        handler = self.env.traps.get(signal_name)
        if not handler:
            return
        if signal_name == "EXIT":
            self.env.traps.pop(signal_name, None)
        from just_bash.parser.parser import parse

        try:
            sub = parse(handler)
        except Exception:
            return
        saved_exit = self.env.last_exit
        for stmt in sub.statements:
            try:
                self._run_statement(stmt, io_ctx)
            except (ExitException, InterpreterError):
                # Don't let a bad trap kill the outer flow.
                break
        self.env.last_exit = saved_exit

    def run_substitution(self, script: Script) -> str:
        """Run a script for ``$(...)`` and capture its stdout."""
        io_ctx = IO()
        try:
            for stmt in script.statements:
                self._run_statement(stmt, io_ctx)
        except ExitException:
            pass
        return io_ctx.stdout.getvalue().decode("utf-8", errors="replace")

    def _make_stream(self) -> io.BytesIO:
        return io.BytesIO()

    # ----------------------------------------------------------- statements
    def _run_statement(self, stmt: Statement, io_ctx: IO) -> int:
        last = 0
        for i, pipeline in enumerate(stmt.pipelines):
            if i > 0:
                op = stmt.operators[i - 1]
                if op == "&&" and last != 0:
                    continue
                if op == "||" and last == 0:
                    continue
            last = self._run_pipeline(pipeline, io_ctx)
            # Update ``last_exit`` between pipelines so that ``$?`` in a later
            # pipeline reads the most recent code.
            self.env.last_exit = last
            self._drain_output_process_subs(io_ctx)
            # ``set -e`` / ``ERR`` fire after each pipeline UNLESS the next
            # operator is ``&&`` / ``||`` — in that case only the last
            # element of the chain matters (matches bash semantics).
            next_op = stmt.operators[i] if i < len(stmt.operators) else None
            in_chain = next_op in ("&&", "||")
            if last != 0 and not in_chain:
                if "ERR" in self.env.traps:
                    self._fire_trap("ERR", io_ctx)
                if "e" in self.env.shell_options:
                    raise ExitException(last)
        return last

    def _drain_output_process_subs(self, io_ctx: IO) -> None:
        """Feed any pending ``>(cmd)`` outputs to their target commands."""
        pending = getattr(self, "_pending_output_subs", None)
        if not pending:
            return
        self._pending_output_subs = []
        for path, body in pending:
            try:
                data = self.fs.read_file(path)
            except Exception:
                continue
            sub_io = IO(stdin=data, stdout=io_ctx.stdout, stderr=io_ctx.stderr)
            for sub_stmt in body.statements:
                self._run_statement(sub_stmt, sub_io)

    # ------------------------------------------------------------ pipelines
    def _run_pipeline(self, pipeline: Pipeline, io_ctx: IO) -> int:
        if len(pipeline.commands) == 1:
            code = self._run_command(pipeline.commands[0], io_ctx)
            self.env.last_pipeline_status = [code]
            return 1 - code if pipeline.negated else code
        # Multi-stage pipeline: chain stdout -> stdin in process.
        stages_out: list[bytes] = [io_ctx.stdin]
        statuses: list[int] = []
        for i, cmd in enumerate(pipeline.commands):
            stage_io = IO(stdin=stages_out[-1])
            if i < len(pipeline.commands) - 1:
                # All non-last stages capture into a fresh buffer.
                stage_io.stdout = io.BytesIO()
                stage_io.stderr = io_ctx.stderr
            else:
                stage_io.stdout = io_ctx.stdout
                stage_io.stderr = io_ctx.stderr
            code = self._run_command(cmd, stage_io)
            statuses.append(code)
            if i < len(pipeline.commands) - 1:
                stages_out.append(stage_io.stdout.getvalue())
        self.env.last_pipeline_status = statuses
        last = statuses[-1]
        return 1 - last if pipeline.negated else last

    # ------------------------------------------------------------- commands
    def _run_command(self, cmd: Command, io_ctx: IO) -> int:
        if isinstance(cmd, SimpleCommand):
            return self._run_simple(cmd, io_ctx)
        if isinstance(cmd, FunctionDef):
            self.env.define_function(cmd.name, cmd)
            return 0
        return self._run_compound(cmd, io_ctx)

    def _run_compound(self, cmd: CompoundCommand, io_ctx: IO) -> int:
        with self._apply_redirections(cmd.redirections, io_ctx) as new_io:
            if isinstance(cmd, If):
                return self._run_if(cmd, new_io)
            if isinstance(cmd, For):
                return self._run_for(cmd, new_io)
            if isinstance(cmd, While):
                return self._run_while(cmd, new_io, until=False)
            if isinstance(cmd, Until):
                return self._run_while(cmd, new_io, until=True)
            if isinstance(cmd, Case):
                return self._run_case(cmd, new_io)
            if isinstance(cmd, Subshell):
                return self._run_subshell(cmd, new_io)
            if isinstance(cmd, Group):
                return self._run_group(cmd, new_io)
            if isinstance(cmd, ConditionalCommand):
                if cmd.expression is None:
                    return 1
                return 0 if eval_conditional(self, cmd.expression) else 1
            if isinstance(cmd, ArithmeticCommand):
                value = eval_arith(self, cmd.expression)
                return 0 if value != 0 else 1
        raise InterpreterError(f"unsupported compound: {type(cmd).__name__}")

    # ----------------------------------------------------- compound impls
    def _run_if(self, node: If, io_ctx: IO) -> int:
        for clause in node.clauses:
            self._exec_block(clause.condition, io_ctx)
            if self.env.last_exit == 0:
                return self._exec_block(clause.body, io_ctx)
        if node.else_body is not None:
            return self._exec_block(node.else_body, io_ctx)
        return 0

    def _run_for(self, node: For, io_ctx: IO) -> int:
        if node.words is None:
            items = list(self.env.positional)
        else:
            items = []
            for w in node.words:
                items.extend(expand_word(self, w))
        last = 0
        for item in items:
            self.env.set_var(node.variable, item)
            try:
                last = self._exec_block(node.body, io_ctx)
            except ContinueException as e:
                if e.levels > 1:
                    raise ContinueException(e.levels - 1) from None
                continue
            except BreakException as e:
                if e.levels > 1:
                    raise BreakException(e.levels - 1) from None
                break
        return last

    def _run_while(self, node: While | Until, io_ctx: IO, *, until: bool) -> int:
        last = 0
        while True:
            self._exec_block(node.condition, io_ctx)
            cond = self.env.last_exit == 0
            if cond if until else not cond:
                break
            try:
                last = self._exec_block(node.body, io_ctx)
            except ContinueException as e:
                if e.levels > 1:
                    raise ContinueException(e.levels - 1) from None
                continue
            except BreakException as e:
                if e.levels > 1:
                    raise BreakException(e.levels - 1) from None
                break
        return last

    def _run_case(self, node: Case, io_ctx: IO) -> int:
        target = expand_word_no_split(self, node.word)
        for item in node.items:
            for pattern_word in item.patterns:
                pattern = expand_pattern(self, pattern_word)
                import fnmatch

                if fnmatch.fnmatchcase(target, pattern):
                    return self._exec_block(item.body, io_ctx)
        return 0

    def _run_subshell(self, node: Subshell, io_ctx: IO) -> int:
        # Subshell isolation: snapshot env state, execute, restore.
        saved_vars = {name: self.env.get_var(name) for name in self.env.all_var_names()}
        saved_cwd = self.fs.cwd
        try:
            return self._exec_block(node.body, io_ctx)
        finally:
            for name in list(self.env.all_var_names()):
                if name not in saved_vars or saved_vars[name] is None:
                    self.env.unset(name)
                else:
                    v = saved_vars[name]
                    assert v is not None
                    self.env.set_var(name, v.value, exported=v.exported)
            with contextlib.suppress(OSError):
                self.fs.chdir(saved_cwd)

    def _run_group(self, node: Group, io_ctx: IO) -> int:
        return self._exec_block(node.body, io_ctx)

    def _exec_block(self, statements: list[Statement], io_ctx: IO) -> int:
        last = 0
        for stmt in statements:
            last = self._run_statement(stmt, io_ctx)
        return last

    # --------------------------------------------------------- simple command
    def _run_simple(self, cmd: SimpleCommand, io_ctx: IO) -> int:
        with self._apply_redirections(cmd.redirections, io_ctx) as new_io:
            if cmd.name is None:
                # Pure assignments: set variables and return 0.
                for assn in cmd.assignments:
                    self._apply_assignment(assn, exported=False)
                return 0
            argv = self._build_argv(cmd)
            if not argv:
                return 0
            # Apply assignments. If the command is a builtin or function the
            # assignments stay; for external commands we'd export them only
            # for that call. The MVP keeps them in scope - close enough.
            tmp_unset: list[str] = []
            assignment_only_export: list[str] = []
            is_function = self.env.get_function(argv[0]) is not None
            is_builtin = argv[0] in self.builtins
            for assn in cmd.assignments:
                if is_function or is_builtin:
                    self._apply_assignment(assn, exported=False)
                else:
                    # Single-command env override: track for cleanup.
                    if not self.env.has(assn.name):
                        tmp_unset.append(assn.name)
                    self._apply_assignment(assn, exported=True)
                    assignment_only_export.append(assn.name)
            try:
                return self._dispatch(argv, new_io)
            finally:
                for name in tmp_unset:
                    self.env.unset(name)
                for name in assignment_only_export:
                    if name in tmp_unset:
                        continue
                    v = self.env.get_var(name)
                    if v is not None:
                        v.exported = False

    def _build_argv(self, cmd: SimpleCommand) -> list[str]:
        argv: list[str] = []
        if cmd.name is not None:
            argv.extend(expand_word(self, cmd.name))
        for arg in cmd.args:
            argv.extend(expand_word(self, arg))
        return argv

    def _apply_assignment(self, assn: Assignment, *, exported: bool) -> None:
        if assn.array is not None:
            values: list[str] = []
            for w in assn.array:
                values.extend(expand_word(self, w))
            if assn.append:
                existing = self.env.get_array(assn.name) or []
                values = [*existing, *values]
            self.env.set_array(assn.name, values, exported=exported)
            return
        value = expand_word_no_split(self, assn.value) if assn.value is not None else ""
        if assn.subscript is not None:
            # ``arr[key]=value`` form. Decide assoc vs indexed by looking at
            # the existing variable; default to indexed when the subscript is
            # numeric.
            existing = self.env.get_var(assn.name)
            from just_bash.parser.word_parser import parse_word

            sub_word = parse_word(assn.subscript, line=assn.line)
            sub_text = expand_word_no_split(self, sub_word)
            if existing is not None and existing.assoc is not None:
                self.env.set_assoc_element(assn.name, sub_text, value)
                return
            try:
                idx = int(sub_text)
            except ValueError:
                # Treat as associative if the key isn't numeric.
                self.env.set_assoc_element(assn.name, sub_text, value)
                return
            self.env.set_array_element(assn.name, idx, value)
            return
        try:
            self.env.set_var(assn.name, value, exported=exported, append=assn.append)
        except PermissionError as e:
            raise InterpreterError(str(e)) from e

    # ----------------------------------------------------------------- dispatch
    def _dispatch(self, argv: list[str], io_ctx: IO) -> int:
        name = argv[0]
        # Function?
        fn = self.env.get_function(name)
        if fn is not None:
            return self._call_function(fn.definition, argv[1:], io_ctx)
        # Builtin?
        builtin = self.builtins.get(name)
        if builtin is not None:
            try:
                return builtin(self, argv, io_ctx)
            except InterpreterError as e:
                io_ctx.stderr.write(f"{name}: {e}\n".encode())
                return e.exit_code
        # Command implementation?
        impl = self.commands.get(name)
        if impl is not None:
            try:
                return impl(self, argv, io_ctx)
            except InterpreterError as e:
                io_ctx.stderr.write(f"{name}: {e}\n".encode())
                return e.exit_code
        io_ctx.stderr.write(f"{name}: command not found\n".encode())
        return 127

    def _call_function(self, defn: FunctionDef, args: list[str], io_ctx: IO) -> int:
        saved = list(self.env.positional)
        self.env.positional = args
        self.env.push_scope()
        try:
            if defn.body is None:
                return 0
            return self._run_compound(defn.body, io_ctx)
        except ReturnException as e:
            return e.code
        finally:
            self.env.pop_scope()
            self.env.positional = saved

    # -------------------------------------------------------- redirections
    class _RedirectCtx:
        """Context manager that applies redirections and restores them on exit."""

        def __init__(self, interp: Interpreter, redirs: list[Redirection], io_ctx: IO) -> None:
            self.interp = interp
            self.redirs = redirs
            self.io_ctx = io_ctx
            self.new_io = IO(stdin=io_ctx.stdin, stdout=io_ctx.stdout, stderr=io_ctx.stderr)
            self._writes: list[tuple[str, bytes, bool]] = []  # (path, content, append)

        def __enter__(self) -> IO:
            for r in self.redirs:
                self.interp._apply_redirection(r, self.new_io, self._writes)
            return self.new_io

        def __exit__(self, exc_type, exc, tb) -> None:  # type: ignore[no-untyped-def]
            # Flush captured writes for ``>file`` / ``>>file``.
            for path, _, _ in self._writes:
                # Already flushed inside ``_apply_redirection``.
                _ = path

    def _apply_redirections(self, redirs: list[Redirection], io_ctx: IO) -> _RedirectCtx:
        return Interpreter._RedirectCtx(self, redirs, io_ctx)

    def _apply_redirection(
        self,
        r: Redirection,
        io_ctx: IO,
        writes: list[tuple[str, bytes, bool]],
    ) -> None:
        # Heredocs and here-strings.
        if isinstance(r.target, HereDoc):
            target_text = expand_word_no_split(self, r.target.content)
            io_ctx.stdin = target_text.encode("utf-8")
            return
        path = expand_word_no_split(self, r.target)
        op = r.operator
        if op == "<":
            io_ctx.stdin = self.fs.read_file(path)
            return
        if op == "<<<":
            io_ctx.stdin = (path + "\n").encode("utf-8")
            return
        if op in (">", ">|"):
            io_ctx.stdout = _RedirectingStream(self, path, append=False)
            writes.append((path, b"", False))
            return
        if op == ">>":
            io_ctx.stdout = _RedirectingStream(self, path, append=True)
            writes.append((path, b"", True))
            return
        if op == "&>":
            stream = _RedirectingStream(self, path, append=False)
            io_ctx.stdout = stream
            io_ctx.stderr = stream
            return
        if op == "&>>":
            stream = _RedirectingStream(self, path, append=True)
            io_ctx.stdout = stream
            io_ctx.stderr = stream
            return
        # 2>file - operator is ">" with fd=2.
        if op == ">" and r.fd == 2:
            io_ctx.stderr = _RedirectingStream(self, path, append=False)
            return
        # ``>&N`` / ``N>&M`` - duplicate / redirect by file-descriptor number.
        if op == ">&":
            src_fd = r.fd if r.fd is not None else 1
            try:
                dst_fd = int(path)
            except ValueError:
                # ``>&filename`` form (rare): treat as ``> filename``.
                io_ctx.stdout = _RedirectingStream(self, path, append=False)
                return
            target_stream = io_ctx.stdout if dst_fd == 1 else io_ctx.stderr
            if src_fd == 1:
                io_ctx.stdout = target_stream
            elif src_fd == 2:
                io_ctx.stderr = target_stream
            return
        if op == "<&":
            # ``N<&M`` - duplicate input fd. For our buffered model we only
            # support ``<&-`` (close, no-op) and ``<&0`` (already stdin).
            return
        raise InterpreterError(f"unsupported redirection: {op}")


class _RedirectingStream(io.BytesIO):
    """A BytesIO that also writes to a VFS file on every write."""

    def __init__(self, interp: Interpreter, path: str, *, append: bool) -> None:
        super().__init__()
        self.interp = interp
        self.path = path
        self.append = append
        if not append:
            interp.fs.write_file(path, b"")

    def write(self, data: bytes) -> int:  # type: ignore[override]
        super().write(data)
        self.interp.fs.append_file(self.path, data)
        return len(data)


# ---------------------------------------------------------------------------
# Public top-level helper
# ---------------------------------------------------------------------------


def run(
    source: str, *, fs: VirtualFs | None = None, env: Environment | None = None, stdin: bytes = b""
) -> ExecResult:
    """Parse and execute a script string. Returns captured stdout/stderr/exit."""
    script = parse(source)
    interp = Interpreter(fs=fs, env=env)
    return interp.run_script_capture(script, stdin=stdin)


__all__ = ["IO", "ExecResult", "Interpreter", "run"]


_ = Word  # forward-reference appeasement
