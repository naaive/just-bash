#!/usr/bin/env bash
# Render a config template using parameter expansion.

declare -A vars
vars[name]=alice
vars[port]=8080
vars[host]=localhost

template='# config
name = ${name}
host = ${host}:${port}
'

render() {
  local out=$1
  local key
  for key in "${!vars[@]}"; do
    out=$(echo "$out" | sed "s|\${$key}|${vars[$key]}|g")
  done
  printf '%s\n' "$out"
}

render "$template"
