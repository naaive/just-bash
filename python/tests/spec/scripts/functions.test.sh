#!/usr/bin/env bash
# Function definitions, locals, recursion, return values.

greet() {
  local name=$1
  echo "Hello, $name!"
}
greet world

fact() {
  if (( $1 <= 1 )); then
    echo 1
  else
    local sub=$(fact $(($1 - 1)))
    echo $(($1 * sub))
  fi
}

for i in 1 2 3 4 5; do
  echo "$i! = $(fact $i)"
done

# Locals don't leak.
outer=outside
modify() {
  local outer=inside
  echo "in: $outer"
}
modify
echo "out: $outer"

# Return value via $?.
check() {
  return "$1"
}
check 7
echo "rc=$?"
