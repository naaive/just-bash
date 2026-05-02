#!/usr/bin/env bash
# A {{ name }} -> value template renderer using parameter expansion + sed.

declare -A vars
vars[name]=alice
vars[project]=just-bash
vars[year]=2026

render() {
  local template=$1
  local output=$template
  for key in "${!vars[@]}"; do
    output=$(echo "$output" | sed "s|{{ *$key *}}|${vars[$key]}|g")
  done
  printf '%s\n' "$output"
}

template='Welcome {{ name }}! You are using {{project}} v{{ year }}.'
render "$template"

# Sorted iteration so output is deterministic across runs.
for k in $(printf '%s\n' "${!vars[@]}" | sort); do
  echo "  - $k = ${vars[$k]}"
done
