#!/usr/bin/env bash
# Mimics a typical git pre-commit hook: scan staged diff for forbidden
# patterns and report file:line. Driven by a fake "diff" that we feed in.

# Stand-in for `git diff --cached --name-only`.
files=(src/api.go src/secrets.go README.md)

# Stand-in for what `git show :FILE` would emit per file.
declare -A content
content[src/api.go]=$'package api\nfunc Hello() string { return \"world\" }'
content[src/secrets.go]=$'package api\nconst apiKey = \"sk-PROD-abcd1234\"\nconst pass = \"hunter2\"'
content[README.md]=$'# Project\nNothing to see here.'

forbidden=(
  'TODO[^:]*:'
  'sk-[A-Za-z0-9]+'
  'password[ \t]*=[ \t]*"'
)

failures=0
for f in "${files[@]}"; do
  body=${content[$f]}
  line_no=0
  while IFS= read -r line; do
    line_no=$((line_no + 1))
    for pat in "${forbidden[@]}"; do
      if [[ "$line" =~ $pat ]]; then
        echo "FAIL: $f:$line_no: ${BASH_REMATCH[0]}"
        failures=$((failures + 1))
      fi
    done
  done <<< "$body"
done

if (( failures > 0 )); then
  echo "blocked: $failures secret(s) found"
  exit 1
fi
echo "ok"
