#!/usr/bin/env bash
# Docker-compose-style health polling: read a "status" each iteration,
# bail out as soon as it goes healthy.

# Pretend the service becomes healthy on the 3rd poll.
states=(starting starting healthy)
attempt=0

# Use a global REPLY-style return (assignment via name instead of $())
# so the side-effect on $attempt persists in the parent shell.
poll_health() {
  local idx=$attempt
  attempt=$((attempt + 1))
  if (( idx >= ${#states[@]} )); then
    HEALTH=unknown
  else
    HEALTH=${states[$idx]}
  fi
}

deadline=10
while (( attempt < deadline )); do
  poll_health
  printf 'attempt %d: %s\n' "$attempt" "$HEALTH"
  case "$HEALTH" in
    healthy) echo "service is healthy after $attempt attempts"; exit 0 ;;
    unhealthy) echo "service is failing"; exit 1 ;;
  esac
done

echo "timed out after $deadline attempts"
exit 2
