#!/usr/bin/env bash
# Validate required env vars and report missing ones.

required=(APP_NAME APP_PORT APP_LOG_LEVEL)

# Pre-populate two of three.
APP_NAME=demo
APP_PORT=9000

missing=()
for var in "${required[@]}"; do
  if [[ -z ${!var:-} ]]; then
    missing+=("$var")
  fi
done

if (( ${#missing[@]} == 0 )); then
  echo "ok"
  exit 0
fi

echo "missing: ${missing[*]}" >&2
exit 1
