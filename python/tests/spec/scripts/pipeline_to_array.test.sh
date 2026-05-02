#!/usr/bin/env bash
# Capture a sorted unique list into an array via mapfile.

text=$'banana\napple\nbanana\ncherry\napple'
mapfile -t fruits < <(echo "$text" | sort -u)

echo "count=${#fruits[@]}"
for f in "${fruits[@]}"; do
  printf 'item: %s\n' "$f"
done
