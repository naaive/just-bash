#!/usr/bin/env bash
# Generate a changelog section from a list of "commits" grouped by type.

commits=(
  "feat: add nameref support"
  "fix: handle empty IFS"
  "feat: bash 5+ vars"
  "docs: update README"
  "fix: unquoted empty word splitting"
  "chore: bump version"
  "feat: extglob in [[ ]]"
  "test: more spec scripts"
  "fix: regex captures"
)

declare -A by_type=(
  [feat]=""
  [fix]=""
  [docs]=""
  [test]=""
  [chore]=""
)

for line in "${commits[@]}"; do
  type=${line%%:*}
  msg=${line#*: }
  if [[ -n "${by_type[$type]+_}" ]]; then
    by_type[$type]+="- $msg"$'\n'
  else
    by_type[other]+="- $line"$'\n'
  fi
done

# Emit sections in a deterministic order.
for section in feat fix docs test chore; do
  body=${by_type[$section]:-}
  if [[ -n "$body" ]]; then
    case "$section" in
      feat)  echo "## Features" ;;
      fix)   echo "## Bug Fixes" ;;
      docs)  echo "## Documentation" ;;
      test)  echo "## Tests" ;;
      chore) echo "## Chores" ;;
      *)     echo "## Other" ;;
    esac
    printf '%s\n' "$body"
  fi
done
