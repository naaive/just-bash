#!/usr/bin/env bash
# Filter a log file by level threshold.

log=/tmp/app.log
mkdir -p /tmp
cat > "$log" <<'EOF'
DEBUG starting
INFO listening on 8080
WARN slow query 1.2s
ERROR connection lost
INFO reconnected
DEBUG flushed
EOF

declare -A rank
rank[DEBUG]=10
rank[INFO]=20
rank[WARN]=30
rank[ERROR]=40

threshold=${rank[INFO]}

while IFS= read -r line; do
  level=${line%% *}
  lvl=${rank[$level]:-0}
  if (( lvl >= threshold )); then
    printf '%s\n' "$line"
  fi
done < "$log"
