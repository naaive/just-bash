#!/usr/bin/env bash
# Decide whether each cert needs renewal based on expiry days.

# Synthetic cert table: domain -> days until expiry.
declare -A days_left=(
  [example.com]=45
  [api.example.com]=8
  [old.example.com]=2
  [internal.example.com]=120
  [legacy.example.com]=-3
)

THRESHOLD=30

renew=()
ok=()
expired=()

for domain in $(printf '%s\n' "${!days_left[@]}" | sort); do
  d=${days_left[$domain]}
  if (( d < 0 )); then
    expired+=("$domain")
  elif (( d <= THRESHOLD )); then
    renew+=("$domain")
  else
    ok+=("$domain")
  fi
done

printf 'expired (%d):\n' "${#expired[@]}"
for d in "${expired[@]}"; do printf '  - %s\n' "$d"; done

printf 'renew (%d):\n' "${#renew[@]}"
for d in "${renew[@]}"; do
  printf '  - %s (%d days left)\n' "$d" "${days_left[$d]}"
done

printf 'ok (%d):\n' "${#ok[@]}"
for d in "${ok[@]}"; do
  printf '  - %s (%d days left)\n' "$d" "${days_left[$d]}"
done

# Exit status reflects whether action is needed.
if (( ${#renew[@]} + ${#expired[@]} > 0 )); then
  echo "action required"
  exit 1
fi
echo "all good"
