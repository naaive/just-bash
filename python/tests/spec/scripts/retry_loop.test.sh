#!/usr/bin/env bash
# Retry loop with backoff (no real sleeping).

attempts=0
max=3
status=fail

simulate() {
  local n=$1
  if (( n >= 3 )); then
    return 0
  fi
  return 1
}

while (( attempts < max )); do
  ((attempts++))
  if simulate $attempts; then
    status=ok
    break
  fi
  echo "attempt $attempts failed; retrying"
done

echo "result: $status after $attempts attempts"
