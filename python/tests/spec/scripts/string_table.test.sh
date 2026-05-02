#!/usr/bin/env bash
# Render a fixed-width table of (name, count) pairs.

names=(alpha beta gamma delta)
counts=(7 23 4 199)

printf '%-8s %5s\n' name count
printf '%-8s %5s\n' -------- -----
for i in "${!names[@]}"; do
  printf '%-8s %5d\n' "${names[$i]}" "${counts[$i]}"
done
