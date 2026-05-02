#!/usr/bin/env bash
# Extract values from a JSON-like blob using only text utilities.

blob='{"name":"alice","age":30,"role":"dev"}'

# Strip braces and split on commas.
inner=${blob#\{}
inner=${inner%\}}

IFS=',' read -ra pairs <<< "$inner"
for p in "${pairs[@]}"; do
  k=${p%%:*}
  v=${p#*:}
  k=${k//\"/}
  v=${v//\"/}
  printf '%s -> %s\n' "$k" "$v"
done
