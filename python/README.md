# just-bash-py

Python rewrite (MVP) of [just-bash](../packages/just-bash): a sandboxed bash
interpreter with an in-memory virtual filesystem. Designed for AI agents that
need a secure, deterministic shell environment without spawning real
subprocesses.

## Status

This is the **MVP slice** of a multi-phase port. The TypeScript original is
~243k LoC across 89 commands; this port targets a working core plus 10
high-frequency utilities.

### Implemented

- **Lexer** — words, single/double quotes, escapes, redirect operators,
  pipes, `&&` / `||` / `;`, parenthesized groups, here-strings.
- **Parser** — `if`, `for ... in`, `while`, `until`, `case`, command groups,
  function definitions, pipelines with `!` negation, redirections,
  assignments, arithmetic command `((...))`, conditional command `[[...]]`.
- **Word expansion** — single/double quotes, escapes, parameter expansion
  (`$VAR`, `${VAR}`, `${VAR:-d}`, `${VAR:=d}`, `${VAR:+a}`, `${VAR:?e}`,
  `${#VAR}`, `${VAR#p}`, `${VAR##p}`, `${VAR%p}`, `${VAR%%p}`,
  `${VAR/p/r}`, `${VAR//p/r}`, `${VAR:o:l}`), command substitution
  `$(...)` / backticks, arithmetic expansion `$((...))`, brace expansion
  (`{a,b,c}` and `{1..10}`), tilde, globbing.
- **Interpreter** — variable scopes, function calls, pipelines (in-process
  via byte streams), redirections (`<`, `>`, `>>`, here-strings),
  exit-status propagation, `&&` / `||` short-circuiting, control flow.
- **Builtins** — `:`, `true`, `false`, `echo`, `printf`, `cd`, `pwd`,
  `export`, `unset`, `set`, `read`, `exit`, `return`, `shift`, `test` /
  `[`, `local`, `eval`, `source` / `.`, `type`, `command`, `let`.
- **Commands** — `cat`, `ls`, `grep` (basic regex + `-i` / `-v` / `-n` /
  `-c` / `-r`), `sed` (basic `s///` with flags and addresses), `awk`
  (basic `BEGIN` / `END` / pattern rules / fields / `print` / `printf`),
  `find` (`-name`, `-type`, `-maxdepth`), `cp`, `mv`, `rm` (`-r`, `-f`),
  `mkdir` (`-p`), `rmdir`, `touch`, `head`, `tail`, `wc`, `sort`, `uniq`,
  `tr`, `cut`, `basename`, `dirname`, `env`, `which`, `true`, `false`.
- **Filesystem** — in-memory tree of files/directories with permissions,
  timestamps, path resolution, glob matching.

### Out of scope for the MVP

- Process substitution `<(...)` / `>(...)`
- Co-processes, job control, traps, signal handling
- Heredocs (only here-strings are supported in MVP)
- Real-FS overlay / OverlayFs (in-memory only)
- WASM-based commands (`python3`, `sqlite3`, `js-exec`)
- Network commands (`curl`)
- Spec-test harness against real bash

## Usage

```bash
# Set up a development environment
cd python
uv venv
source .venv/bin/activate
uv pip install -e '.[dev]'

# Run tests, type-check, lint
pytest
pyright
ruff check .

# Run the shell on an inline script
just-bash -c 'echo "hello $USER" | tr a-z A-Z'

# Run a script file
just-bash script.sh

# Print AST without executing
just-bash --print-ast -c 'for i in 1 2 3; do echo $i; done'
```

## Layout

```
python/
├── pyproject.toml
├── src/just_bash/
│   ├── ast/          # Dataclass AST node definitions
│   ├── parser/       # Lexer + parser
│   ├── interpreter/  # Tree-walking interpreter, expansions, builtins
│   ├── fs/           # In-memory virtual filesystem
│   ├── commands/     # External-command implementations
│   └── cli.py        # `just-bash` entry point
└── tests/
    ├── parser/       # Lexer + parser unit tests
    ├── interpreter/  # Expansion / arithmetic / control-flow tests
    ├── commands/     # Command behavior tests
    └── integration/  # End-to-end script tests
```
