#!/usr/bin/env bash
# Array operations: copy, filter, map, fold.

src=(10 20 30 40 50)

# Copy via "${arr[@]}".
dst=("${src[@]}")
echo "copy:${dst[*]}"

# Filter (keep > 20).
filtered=()
for n in "${src[@]}"; do
  if (( n > 20 )); then
    filtered+=("$n")
  fi
done
echo "filtered:${filtered[*]}"

# Map (double).
mapped=()
for n in "${src[@]}"; do
  mapped+=($((n * 2)))
done
echo "mapped:${mapped[*]}"

# Fold (sum).
total=0
for n in "${src[@]}"; do
  ((total += n))
done
echo "total:$total"

# Length, first, last.
echo "len=${#src[@]}"
echo "first=${src[0]}"
echo "last=${src[$((${#src[@]} - 1))]}"
