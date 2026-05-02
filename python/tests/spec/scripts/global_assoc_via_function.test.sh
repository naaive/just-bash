#!/usr/bin/env bash
# Modify an associative array via a function using namerefs.

declare -A counts

bump() {
  local -n m=$1
  local key=$2
  m[$key]=$(( ${m[$key]:-0} + 1 ))
}

for c in red red blue green red blue; do
  bump counts "$c"
done

for k in red green blue; do
  echo "$k: ${counts[$k]}"
done
