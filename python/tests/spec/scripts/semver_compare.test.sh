#!/usr/bin/env bash
# Semantic-version comparator: returns -1 / 0 / 1 like a comparator.

semver_cmp() {
  local a=$1 b=$2
  local IFS=.
  read -ra ap <<< "$a"
  read -ra bp <<< "$b"
  for i in 0 1 2; do
    local av=${ap[$i]:-0}
    local bv=${bp[$i]:-0}
    if (( av < bv )); then echo -1; return; fi
    if (( av > bv )); then echo 1; return; fi
  done
  echo 0
}

for pair in "1.2.3 1.2.3" "1.2.3 1.2.4" "2.0.0 1.99.99" "0.1 0.1.0" "10.0.0 9.99.99"; do
  read -ra parts <<< "$pair"
  printf '%s vs %s -> %s\n' "${parts[0]}" "${parts[1]}" \
    "$(semver_cmp "${parts[0]}" "${parts[1]}")"
done
