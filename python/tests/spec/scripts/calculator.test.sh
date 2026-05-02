#!/usr/bin/env bash
# Tiny RPN-ish calculator using a stack array.

stack=()
top=-1
RET=0

push() {
  top=$((top + 1))
  stack[$top]=$1
}

pop() {
  RET=${stack[$top]}
  unset 'stack[top]'
  top=$((top - 1))
}

apply() {
  local op=$1
  pop
  local b=$RET
  pop
  local a=$RET
  case "$op" in
    +) push $((a + b)) ;;
    -) push $((a - b)) ;;
    \*) push $((a * b)) ;;
    /) push $((a / b)) ;;
  esac
}

# (3 + 4) * 2 - 1 = 13
push 3
push 4
apply +
push 2
apply \*
push 1
apply -

echo "${stack[$top]}"
