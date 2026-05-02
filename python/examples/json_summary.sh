#!/usr/bin/env just-bash
# Summarize a JSON file via the bundled `jq` subset.

input=${1:-/dev/stdin}

echo "type: $(jq -r 'type // "unknown"' "$input")"
echo "keys: $(jq -r 'keys | join(",")' "$input" 2>/dev/null || echo 'n/a')"
echo "len:  $(jq -r 'length' "$input")"
