#!/usr/bin/env bash
# Mini log-rotation script: create N rotation files in numeric order.

mkdir -p /tmp/logs

for i in 1 2 3 4 5; do
  echo "entry-$i" > "/tmp/logs/app.log.$i"
done

# Move the oldest to .archive, keep the last 3.
ls -1 /tmp/logs | sort -t. -k3n > /tmp/order
total=$(wc -l < /tmp/order)
keep=3
remove=$((total - keep))

if (( remove > 0 )); then
  head -n "$remove" /tmp/order | sed 's/^/would-archive: /'
fi

# Show survivors deterministically.
tail -n "$keep" /tmp/order
