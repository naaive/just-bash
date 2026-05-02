#!/usr/bin/env just-bash
# Count the most common words across all .txt files passed on argv.

if [ $# -eq 0 ]; then
  echo "usage: $0 FILE..." >&2
  exit 2
fi

for f in "$@"; do
  cat "$f"
done | tr -s ' \t' '\n' | tr A-Z a-z | sort | uniq -c | sort -rn | head -10
