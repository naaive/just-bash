#!/usr/bin/env bash
# Tiny make-style topological build runner with dependency resolution.

declare -A deps
deps[a]=""
deps[b]=""
deps[c]="a"
deps[d]="a b"
deps[e]="c d"
deps[f]="e"

declare -A built
declare -a order

build() {
  local target=$1
  if [[ "${built[$target]:-0}" == 1 ]]; then
    return 0
  fi
  for dep in ${deps[$target]:-}; do
    build "$dep"
  done
  built[$target]=1
  order+=("$target")
  echo "  build $target"
}

# Build the leaf and watch the order propagate.
echo "building f:"
build f
echo
echo "order: ${order[*]}"
echo "count: ${#order[@]}"
