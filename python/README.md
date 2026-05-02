# just-bash-py

Python port of [just-bash](../packages/just-bash): a sandboxed bash
interpreter with an in-memory virtual filesystem (and an opt-in real-FS
overlay). Designed for AI agents and tooling that need a secure,
deterministic shell environment without spawning real subprocesses.

> **Status**: working bash subset that runs the vast majority of practical
> scripts. Built across 6 commits totalling ~21k Python lines, with **510+
> tests** including ~130 fixtures pinned against real bash.

## Quickstart

```bash
cd python
uv venv && source .venv/bin/activate
uv pip install -e '.[dev]'

# Run an inline script.
just-bash -c 'echo "hello $USER" | tr a-z A-Z'

# Run a script against a real-FS root - reads see real files, writes go to
# the in-memory overlay so the host disk is untouched.
just-bash --root . -c 'find . -name "*.py" | wc -l'

# Print the AST without executing.
just-bash --print-ast -c 'for i in 1 2 3; do echo $i; done'

# Quality gates (also run in CI on Linux + macOS, py3.11/3.12/3.13):
ruff check . && ruff format --check .
pyright
pytest
```

## Architecture

```
Source ─► Lexer ─► Parser ─► AST ─► Interpreter ─► ExecResult
                                       │
                                       ▼
                              Environment + VFS / OverlayFs
```

`Interpreter.fs` is duck-typed (`VirtualFs | OverlayFs`); both expose the
same set of methods so commands work uniformly against either backend.

## Supported bash subset

### Syntax / parser

- Pipelines with `!` negation, `|`, `|&`
- `&&` / `||` / `;` chains; `&` background flag (collected, not actually
  scheduled)
- `if` / `then` / `elif` / `else` / `fi`
- `for VAR in WORDS`, `for ((init; cond; step))`, `for VAR in {1..N}`
- `while` / `until` / `do` / `done`
- `case PATTERN in ... ;; ... esac` (with `|` alternatives)
- `( ... )` subshell with isolated environment + cwd
- `{ ... }` command group
- Function definitions: `name() { ... }` and `function name { ... }`
- `[[ EXPR ]]` conditional and `(( EXPR ))` arithmetic command
- `<<` / `<<-` heredocs (with quoted-delimiter no-expansion form),
  `<<<` here-strings
- Process substitution `<(cmd)` / `>(cmd)` via `/dev/fd/N` synth paths
- Trailing redirections on compound blocks: `done >file`, `) 2>err`, ...
- `2>&1` / `>&2` fd duplication
- Comments

### Word expansion

- Brace: `{a,b,c}`, `{1..10}`, `{1..10..2}`, `{a..z}`, with prefix/suffix
- Tilde: `~`, `~user` (HOME-aware)
- Parameter:
  - `$VAR`, `${VAR}`, `${VAR:-d}`, `${VAR:=d}`, `${VAR:+a}`, `${VAR:?msg}`
  - `${#VAR}`, `${VAR:o}`, `${VAR:o:l}` (incl. negative offsets)
  - `${VAR#p}`, `${VAR##p}`, `${VAR%p}`, `${VAR%%p}`
  - `${VAR/p/r}`, `${VAR//p/r}`, `${VAR/#p/r}`, `${VAR/%p/r}`
  - Case folding: `${VAR^^}`, `${VAR^}`, `${VAR,,}`, `${VAR,}` (with optional
    pattern: `${VAR^^[hl]}`)
  - Transforms: `${VAR@U}`, `${VAR@L}`, `${VAR@u}`, `${VAR@Q}` (shell-quote),
    `${VAR@E}` (interpret backslash escapes)
  - Indirect: `${!ref}`, `${!ref:-default}`
  - Var-name prefix lists: `${!prefix*}`, `${!prefix@}`
  - Array: `${arr[N]}`, `${arr[@]}`, `${arr[*]}`, `${#arr[@]}`,
    `${!arr[@]}`, `arr+=(...)`, `arr[N]=v`
  - Associative arrays via `declare -A`: `${m[key]}`, `${!m[@]}` returns
    actual keys
- Command substitution: `$(...)`, `` `...` `` (incl. inside double quotes
  and inside arithmetic)
- Arithmetic: `$((expr))`, `((expr))` with full operator set including
  `**`, `<<`, `>>`, ternary, postfix `++`/`--`, base-N (`16#ff`)
- Word splitting on `$IFS`
- Globbing: `*`, `?`, `[abc]`, `**` (recursive)
- Quote removal

### Builtins (40+)

`:` `true` `false` `echo` `printf` `cd` `pwd` `export` `unset` `set`
`read` `exit` `return` `shift` `test` `[` `local` `eval` `source` / `.`
`type` `command` `let` `break` `continue` `declare` / `typeset` `trap`
`pushd` `popd` `dirs` `alias` `unalias` `shopt` `time` `umask` `ulimit`
`history` `help` `mapfile` / `readarray` `wait` `jobs` `disown` `bg` `fg`
`enable` `compgen` `complete` `bind` `caller` `logout` `suspend` `hash`

### Commands (75+)

- **Core**: `cat`, `ls` (with `-a` / `-l` / `-1` / `-d` / `-r` / `-R` / `-F`),
  `mkdir` / `rmdir` / `touch`, `head` / `tail` (with legacy `-N` shorthand),
  `wc`, `tee`, `basename`, `dirname`, `env`, `which`, `yes`
- **Text**: `sort` (with `-r` / `-n` / `-u` / `-f` / `-b`), `uniq`
  (`-c` / `-d` / `-u` / `-i`), `tr` (with `[:lower:]` etc.), `cut`
  (`-d` / `-f` / `-c` / `-b`), `rev`, `nl`, `pr`, `fmt` (`-w`), `look`,
  `tsort`, `expand` / `unexpand`, `fold`, `paste`, `comm`, `diff` (`-q` /
  `-u`), `join`, `tac`, `shuf`, `column`, `split`
- **Pattern**: `grep` (BRE / `-E` / `-F` / `-P`, `-i` / `-v` / `-n` / `-c` /
  `-l` / `-H` / `-h` / `-r` / `-w` / `-x` / `-q` / `-o` / `-A` / `-B` / `-C`),
  `sed` (BRE / `-E`, `-i`, multi `-e`, hold space, branches, `y/SRC/DST/`,
  `a`/`i`/`c`/`d`/`p`/`q`/`=`/`n`/`{...}`), `awk` (full pattern-action
  language including UDFs, control flow, builtins)
- **Filesystem**: `cp` / `mv` / `rm` (`-r` / `-f`), `find` (`-name`,
  `-iname`, `-type`, `-path`, `-empty`, `-size`, `-maxdepth`, `-mindepth`,
  `-not`, `-or`, `-and`, `-print`, `-exec ... \;`, `-exec ... +`, `-delete`),
  `realpath`, `stat`, `du`, `df`, `xargs` (`-n` / `-I` / `-r` / `-0`),
  `mktemp`, `dd`
- **Encoding / hashing**: `base64`, `md5sum` / `sha1sum` / `sha256sum`,
  `cksum`, `crc32`, `cmp`, `hexdump` (`-C`), `xxd` (`-p` / `-r`)
- **Date / time / proc**: `date` (POSIX format strings), `sleep` (no-op),
  `time` (zeros, runs the inner command), `ps`, `top`, `lsof`, `ifconfig`,
  `ip`, `free`
- **Network stubs** (no real I/O): `curl`, `wget`, `ping`, `host`, `dig`,
  `nslookup`
- **Archive**: `tar` (`-c` / `-x` / `-t` / `-f`), `zip`, `unzip` (`-l`)
- **System info**: `hostname`, `whoami`, `id`, `uname` (`-a`/`-s`/`-r`/...),
  `getent` (passwd / group / hosts), `file`, `tput`, `stty`, `clear`,
  `reset`
- **JSON**: `jq` subset (`.`, `.field`, `.field.sub`, `.[N]`, `length`,
  `keys`, `-r` / `-c`)
- **Other**: `seq`, `expr`, `getopt`, `watch`

## Filesystem layers

- **`VirtualFs`** — pure in-memory tree. The default; ideal for unit tests
  and isolated agent runs. Pre-populated with `/dev/null` and `/tmp` so
  common idioms like `2>/dev/null` work.
- **`OverlayFs(root, allow_symlinks=False, allow_writes=True)`** — wraps a
  real-FS root. Reads fall through to disk; writes go to an in-memory
  overlay so the host filesystem is never modified. Default-deny symlink
  policy: any traversal of a host symlink (or `..` escape) is rejected,
  matching the security model of the original TS implementation. Reads use
  `O_NOFOLLOW` to close the TOCTOU gap on symlink swap.

CLI usage:

```bash
just-bash --root /path/to/project -c 'find . -name "*.md"'
just-bash --root . --allow-symlinks -c 'cat /symlink-target'
```

## Out of scope / known gaps

- WASM-backed `python3` / `sqlite3` / `js-exec` commands (covered by the
  TS implementation)
- Real network access
- Job control (`bg` / `fg` / `wait` are no-ops)
- BSD-style `cksum` polynomial parity (we use zlib CRC32)
- Live `top` / `watch` refresh
- `select` interactive loop
- Bash debugger / `BASH_*` introspection variables

## Layout

```
python/
├── pyproject.toml         # hatchling + ruff + pyright + pytest
├── src/just_bash/
│   ├── ast/               # Dataclass AST nodes
│   ├── parser/            # Lexer, recursive-descent parser, word/arith parsers
│   ├── interpreter/       # Tree-walking interpreter, builtins, expansion
│   ├── fs/                # VirtualFs + OverlayFs + path utilities
│   ├── commands/          # External-command implementations
│   └── cli.py             # `just-bash` entry point
└── tests/
    ├── parser/            # Lexer + parser unit tests
    ├── interpreter/       # Expansion / arithmetic / control-flow / arrays
    ├── commands/          # Command behaviour tests
    ├── fs/                # VFS + OverlayFs (incl. symlink-deny security)
    ├── integration/       # End-to-end + CLI tests
    └── comparison/        # Real-bash output fixtures (RECORD_FIXTURES=1)
```

## Re-recording comparison fixtures

When you change an expansion / command behaviour, regenerate the bash
baselines:

```bash
RECORD_FIXTURES=1 pytest tests/comparison
```

The harness runs each script through real `bash` in a clean tempdir and
writes the captured stdout / stderr / exit code to
`tests/comparison/fixtures/<name>.json`. Subsequent `pytest` runs replay
just-bash-py against that fixture so the suite is reproducible across
machines.
