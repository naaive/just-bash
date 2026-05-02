#!/usr/bin/env bash
# Trap, set -e, exit codes.

set -e

trap 'echo "trap: ERR fired"' ERR
trap 'echo "trap: EXIT fired"' EXIT

cleanup_then_succeed() {
  echo "doing work"
  return 0
}

cleanup_then_succeed

# || true keeps set -e happy on a failing pipeline.
false || true
echo "after-or-true"

# But a bare failure aborts.
echo "before-failure"
( exit 7 )
echo "never-reached"
