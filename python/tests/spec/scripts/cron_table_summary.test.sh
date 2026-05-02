#!/usr/bin/env bash
# Parse a crontab and explain when each entry runs.

mkdir -p /tmp
cat > /tmp/crontab <<'EOF'
# minute  hour  day-of-month  month  day-of-week  command
0 * * * * /usr/local/bin/heartbeat
*/15 * * * * /opt/queue/poll
0 9 * * 1-5 /opt/reports/daily
30 22 1 * * /opt/billing/monthly
0 0 * * 0 /opt/cleanup/weekly
EOF

explain_when() {
  local m=$1 h=$2 dom=$3 mon=$4 dow=$5
  if [[ "$m" == "*" && "$h" == "*" && "$dom" == "*" && "$mon" == "*" && "$dow" == "*" ]]; then
    echo "every minute"
  elif [[ "$m" =~ ^\*/([0-9]+)$ ]]; then
    echo "every ${BASH_REMATCH[1]} minutes"
  elif [[ "$m" == "0" && "$h" == "*" ]]; then
    echo "hourly"
  elif [[ "$h" =~ ^[0-9]+$ && "$dom" == "*" && "$mon" == "*" && "$dow" == "1-5" ]]; then
    echo "weekdays at $h:$(printf '%02d' "$m")"
  elif [[ "$h" =~ ^[0-9]+$ && "$dom" =~ ^[0-9]+$ && "$mon" == "*" && "$dow" == "*" ]]; then
    echo "monthly day $dom at $h:$(printf '%02d' "$m")"
  elif [[ "$dow" =~ ^[0-6]$ ]]; then
    echo "weekly on day $dow"
  else
    echo "custom"
  fi
}

while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  read -ra fields <<< "$line"
  m=${fields[0]}; h=${fields[1]}; dom=${fields[2]}
  mon=${fields[3]}; dow=${fields[4]}
  cmd="${fields[*]:5}"
  printf '%-20s %s\n' "$(explain_when "$m" "$h" "$dom" "$mon" "$dow")" "$cmd"
done < /tmp/crontab
