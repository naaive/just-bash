#!/usr/bin/env bash
# Nested case with fall-through-style chaining.

classify() {
  local x=$1
  case "$x" in
    [0-9])
      case "$x" in
        0) echo zero ;;
        [1-9]) echo digit ;;
      esac
      ;;
    [a-z]) echo lower ;;
    [A-Z]) echo upper ;;
    *) echo other ;;
  esac
}

for v in 0 5 a Z !; do
  classify "$v"
done
