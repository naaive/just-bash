#!/usr/bin/env bash
# Pivot a CSV: count items per (region, status) into a 2D table.

mkdir -p /tmp
cat > /tmp/orders.csv <<'EOF'
region,status,amount
us-east,paid,120
us-east,paid,80
us-east,refunded,50
us-west,paid,200
us-west,pending,90
eu,paid,300
eu,paid,150
eu,refunded,40
eu,pending,75
EOF

declare -A pivot
declare -A regions
declare -A statuses

# Skip header (line 1).
tail -n +2 /tmp/orders.csv | while IFS=, read -r region status amount; do
  echo "$region,$status,$amount"
done > /tmp/orders.norm

while IFS=, read -r region status amount; do
  key="$region|$status"
  pivot[$key]=$(( ${pivot[$key]:-0} + amount ))
  regions[$region]=1
  statuses[$status]=1
done < /tmp/orders.norm

# Print header.
printf '%-10s' ''
for s in $(printf '%s\n' "${!statuses[@]}" | sort); do
  printf '%10s' "$s"
done
printf '\n'

for r in $(printf '%s\n' "${!regions[@]}" | sort); do
  printf '%-10s' "$r"
  for s in $(printf '%s\n' "${!statuses[@]}" | sort); do
    val=${pivot["$r|$s"]:-0}
    printf '%10s' "$val"
  done
  printf '\n'
done
