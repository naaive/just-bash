#!/usr/bin/env bash
# Recursive function: factorial.

fact() {
  if (( $1 <= 1 )); then
    echo 1
    return
  fi
  local prev
  prev=$(fact $(( $1 - 1 )))
  echo $(( $1 * prev ))
}

for n in 0 1 2 5 7; do
  printf '%d! = %d\n' "$n" "$(fact "$n")"
done
