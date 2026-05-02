#!/usr/bin/env bash
# Multi-subcommand CLI dispatcher pattern (e.g. `tool build`, `tool run`).

usage() {
  cat <<'EOF'
usage: tool COMMAND [args...]
  build     compile sources
  run       execute the binary
  test      run the test suite
  clean     remove build artefacts
EOF
}

cmd_build() {
  echo "build: target=${1:-default}"
}

cmd_run() {
  echo "run: args=$*"
}

cmd_test() {
  local pattern=${1:-*}
  echo "test: pattern=$pattern"
}

cmd_clean() {
  echo "clean: removing artefacts"
}

dispatch() {
  local sub=${1:-help}
  shift || true
  case "$sub" in
    help|-h|--help) usage; return 0 ;;
    build|run|test|clean) "cmd_$sub" "$@"; return $? ;;
    *) echo "unknown command: $sub" >&2; usage >&2; return 2 ;;
  esac
}

# Drive a few invocations.
dispatch build prod
dispatch run --port 8080
dispatch test "unit/*"
dispatch clean
dispatch unknown || echo "rc=$?"
