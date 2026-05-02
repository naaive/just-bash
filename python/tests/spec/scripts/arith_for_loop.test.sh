#!/usr/bin/env bash
# C-style for loop with arithmetic.

sum=0
for ((i = 1; i <= 5; i++)); do
  sum=$((sum + i * i))
done
echo "sum=$sum"

# Nested loop building a multiplication-style table line.
for ((r = 1; r <= 3; r++)); do
  for ((c = 1; c <= 3; c++)); do
    printf '%3d ' "$((r * c))"
  done
  printf '\n'
done
