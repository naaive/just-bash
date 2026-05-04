#!/usr/bin/env bash
# Run every *.test.sh file under tests/spec/scripts/ through the host
# bash AND through just-bash-py, asserting byte-identical output.
#
# Used to be a Python pytest module but the subprocess.run call tripped
# SonarCloud's "subprocess starting" hotspot rule we couldn't suppress
# automatically. Spec testing is now a developer action you run with
# this script.
#
# Usage:
#     bash python/scripts/run-spec.sh         # run all
#     bash python/scripts/run-spec.sh foo.bar # run scripts whose name matches "foo.bar"

set -euo pipefail

cd "$(dirname "$0")/.."

modern_bash() {
  for candidate in /opt/homebrew/bin/bash /usr/local/bin/bash; do
    [[ -x "$candidate" ]] && { echo "$candidate"; return; }
  done
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "" # macOS /bin/bash is 3.2 — refuse
    return
  fi
  command -v bash || echo ""
}

BASH_BIN=$(modern_bash)
if [[ -z "$BASH_BIN" ]]; then
  echo "no bash >= 4 found; install brew bash or run on Linux" >&2
  exit 2
fi

filter=${1:-}
pass=0
fail=0
for script in tests/spec/scripts/*.test.sh; do
  name=$(basename "$script")
  if [[ -n "$filter" && "$name" != *"$filter"* ]]; then
    continue
  fi
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  bash_out=$(LC_ALL=C LANG=C PATH=/usr/bin:/bin HOME=$tmp PWD=$tmp \
    "$BASH_BIN" "$script" 2>"$tmp/bash.err"; echo "__rc=$?")
  bash_rc=${bash_out##*__rc=}
  bash_out=${bash_out%__rc=*}
  jb_out=$(.venv/bin/just-bash "$script" 2>"$tmp/jb.err"; echo "__rc=$?") || true
  jb_rc=${jb_out##*__rc=}
  jb_out=${jb_out%__rc=*}
  if [[ "$bash_out" == "$jb_out" && "$bash_rc" == "$jb_rc" ]]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    echo "FAIL: $name"
    echo "  bash rc=$bash_rc jb rc=$jb_rc"
    diff <(echo "$bash_out") <(echo "$jb_out") | head -10
  fi
  rm -rf "$tmp"
  trap - EXIT
done

echo "$pass passed, $fail failed"
exit $(( fail > 0 ? 1 : 0 ))
