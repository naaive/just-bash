#!/usr/bin/env bash
# break and continue inside a counted loop.

result=()
for i in 1 2 3 4 5 6 7 8 9 10; do
  if (( i % 2 == 0 )); then
    continue
  fi
  if (( i > 7 )); then
    break
  fi
  result+=("$i")
done

echo "${result[*]}"
