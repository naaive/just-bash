#!/usr/bin/env bash
# Find files with identical content using checksum + group-by.

mkdir -p /tmp/dupes
echo hello > /tmp/dupes/a
echo hello > /tmp/dupes/b
echo world > /tmp/dupes/c
echo hello > /tmp/dupes/d
echo unique > /tmp/dupes/e
echo world > /tmp/dupes/f

declare -A checksum_files

for f in /tmp/dupes/*; do
  sum=$(sha256sum "$f" | awk '{print $1}')
  if [[ -n "${checksum_files[$sum]:-}" ]]; then
    checksum_files[$sum]="${checksum_files[$sum]} $(basename "$f")"
  else
    checksum_files[$sum]=$(basename "$f")
  fi
done

# Print groups with more than one file, sorted for determinism.
echo "Duplicate groups:"
for sum in $(printf '%s\n' "${!checksum_files[@]}" | sort); do
  group=${checksum_files[$sum]}
  count=0
  for _ in $group; do count=$((count + 1)); done
  if (( count > 1 )); then
    echo "  ${sum:0:8}... -> $group ($count files)"
  fi
done
