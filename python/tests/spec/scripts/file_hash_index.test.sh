#!/usr/bin/env bash
# Build an index file mapping path -> sha256 for a directory tree.

mkdir -p /tmp/proj/src /tmp/proj/docs
echo 'package main' > /tmp/proj/src/main.go
echo 'func helper() {}' > /tmp/proj/src/util.go
echo '# Project' > /tmp/proj/docs/README.md
echo 'license text' > /tmp/proj/LICENSE

index=/tmp/proj/.index
> "$index"

while IFS= read -r path; do
  sum=$(sha256sum "$path" | awk '{print $1}')
  rel=${path#/tmp/proj/}
  printf '%s  %s\n' "${sum:0:12}" "$rel" >> "$index"
done < <(find /tmp/proj -type f ! -name '.index' | sort)

cat "$index"
echo "entries: $(wc -l < "$index")"
