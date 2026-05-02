#!/usr/bin/env bash
# CLI wrapper that dispatches subcommands - common tooling pattern.

usage() {
  cat <<EOF
usage: cli COMMAND [args...]
commands: build test ship
EOF
}

case "${1:-}" in
  "")
    usage
    exit 0
    ;;
  build)
    shift
    echo "build args: $*"
    ;;
  test)
    shift
    echo "test args: $*"
    ;;
  ship)
    shift
    echo "ship args: $*"
    ;;
  *)
    echo "unknown subcommand: $1" >&2
    exit 2
    ;;
esac
