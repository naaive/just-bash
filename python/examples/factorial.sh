#!/usr/bin/env just-bash
# Recursive factorial using a function and arithmetic command substitution.

fact() {
  if (( $1 <= 1 )); then
    echo 1
  else
    local sub
    sub=$(fact $(( $1 - 1 )))
    echo $(( $1 * sub ))
  fi
}

for i in {1..6}; do
  printf "%d! = %s\n" "$i" "$(fact $i)"
done
