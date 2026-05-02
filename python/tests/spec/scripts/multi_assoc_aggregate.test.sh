#!/usr/bin/env bash
# Aggregate counts into an associative array.

declare -A counts
items=(red blue red green blue red green green green)

for item in "${items[@]}"; do
  counts[$item]=$(( ${counts[$item]:-0} + 1 ))
done

for k in green red blue; do
  echo "$k: ${counts[$k]}"
done
