#!/usr/bin/env just-bash
# Print a build matrix using nested loops, brace expansion, and printf.

declare -A status
status[linux]=ok
status[macos]=pending
status[windows]=skip

for os in "${!status[@]}"; do
  for py in 3.11 3.12 3.13; do
    printf "%-9s py%-4s -> %s\n" "$os" "$py" "${status[$os]}"
  done
done
