#!/usr/bin/env bash
# Mini ``make``: target -> deps -> action driven by associative arrays.

declare -A deps
declare -A actions

deps[hello.o]="hello.c hello.h"
deps[main.o]="main.c"
deps[app]="hello.o main.o"

actions[hello.o]='echo "compile hello.o"'
actions[main.o]='echo "compile main.o"'
actions[app]='echo "link app"'

build() {
  local target=$1
  local d
  for d in ${deps[$target]:-}; do
    [[ -n ${deps[$d]:-} ]] && build "$d"
  done
  if [[ -n ${actions[$target]:-} ]]; then
    eval "${actions[$target]}"
  fi
}

build app
