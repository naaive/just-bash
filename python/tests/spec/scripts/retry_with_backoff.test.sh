#!/usr/bin/env bash
# Standard retry-with-exponential-backoff harness used by deployment scripts.

attempt=0
max_attempts=5
backoff_ms=100  # initial backoff

# Simulated flaky operation: succeeds on attempt 3.
run_op() {
  attempt=$((attempt + 1))
  if (( attempt >= 3 )); then
    echo "  -> attempt $attempt: ok"
    return 0
  fi
  echo "  -> attempt $attempt: failure"
  return 1
}

# Outer loop applies backoff between retries.
while (( attempt < max_attempts )); do
  if run_op; then
    echo "succeeded after $attempt attempts"
    exit 0
  fi
  next_ms=$(( backoff_ms * 2 ** (attempt - 1) ))
  if (( attempt < max_attempts )); then
    echo "  retry in ${next_ms}ms"
  fi
done

echo "failed after $attempt attempts"
exit 1
