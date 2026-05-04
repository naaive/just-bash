#!/usr/bin/env bash
# Pattern from package install scripts (apt-style wrappers, brew formulas):
# resolve dependencies recursively, sort topologically, emit install order.

declare -A DEPS=(
  [a]=""
  [b]=""
  [c]="a"
  [d]="a b"
  [e]="c d"
  [f]="e a"
  [g]="f b"
)

declare -A SEEN
declare -a ORDER

resolve() {
  local pkg=$1
  if [[ -n "${SEEN[$pkg]:-}" ]]; then
    return
  fi
  SEEN[$pkg]=1
  for dep in ${DEPS[$pkg]:-}; do
    resolve "$dep"
  done
  ORDER+=("$pkg")
}

# Install requested set (might include duplicates / overlap).
for target in g e a; do
  resolve "$target"
done

echo "install order:"
for p in "${ORDER[@]}"; do
  printf '  %s' "$p"
  deps=${DEPS[$p]:-}
  if [[ -n "$deps" ]]; then
    printf ' (needs: %s)' "$deps"
  fi
  printf '\n'
done

echo "total: ${#ORDER[@]}"
