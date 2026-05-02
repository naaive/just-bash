#!/usr/bin/env bash
# Parse an Apache-style access log and emit a per-status summary.

mkdir -p /tmp
cat > /tmp/access.log <<'EOF'
10.0.0.1 - - [10/May/2024:08:23:01] "GET /index.html HTTP/1.1" 200 1024
10.0.0.2 - - [10/May/2024:08:23:05] "GET /missing.css HTTP/1.1" 404 145
10.0.0.1 - - [10/May/2024:08:23:08] "POST /api/login HTTP/1.1" 200 567
10.0.0.3 - - [10/May/2024:08:23:11] "GET /admin HTTP/1.1" 403 0
10.0.0.2 - - [10/May/2024:08:23:14] "GET /static/app.js HTTP/1.1" 200 8192
10.0.0.4 - - [10/May/2024:08:23:21] "GET /missing-page HTTP/1.1" 404 145
10.0.0.5 - - [10/May/2024:08:23:30] "GET /api/health HTTP/1.1" 500 18
EOF

declare -A status_count
total_bytes=0
unique_ips_set=()

while IFS= read -r line; do
  ip=${line%% *}
  # Status code is the second-to-last field.
  status=$(echo "$line" | awk '{print $(NF-1)}')
  bytes=$(echo "$line" | awk '{print $NF}')
  status_count[$status]=$(( ${status_count[$status]:-0} + 1 ))
  total_bytes=$(( total_bytes + bytes ))
  # Track unique IPs.
  found=0
  for u in "${unique_ips_set[@]}"; do
    [[ "$u" == "$ip" ]] && { found=1; break; }
  done
  (( found == 0 )) && unique_ips_set+=("$ip")
done < /tmp/access.log

echo "Total bytes: $total_bytes"
echo "Unique IPs: ${#unique_ips_set[@]}"
for code in $(printf '%s\n' "${!status_count[@]}" | sort); do
  echo "  $code: ${status_count[$code]}"
done
