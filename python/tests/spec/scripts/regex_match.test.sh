#!/usr/bin/env bash
# [[ str =~ regex ]] basic matches.

# IPv4-ish.
for ip in 192.168.1.1 999.0.0.1 not-an-ip; do
  if [[ "$ip" =~ ^[0-9.]+$ ]]; then
    echo "$ip: numeric-dotted"
  else
    echo "$ip: no"
  fi
done

# Capture pattern.
s="key=value123"
if [[ "$s" =~ ^[a-z]+=[a-z0-9]+$ ]]; then
  echo "matched: $s"
fi
