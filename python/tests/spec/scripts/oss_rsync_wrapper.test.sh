#!/usr/bin/env bash
# Mimic an rsync wrapper: build a transfer plan from "changed since" files
# and emit the commands without actually invoking rsync.

mkdir -p /tmp/rs/src /tmp/rs/dst
echo "alpha"  > /tmp/rs/src/a.txt
echo "beta"   > /tmp/rs/src/b.txt
echo "gamma"  > /tmp/rs/src/c.txt
# Pretend a.txt and b.txt have already been mirrored.
echo "alpha"  > /tmp/rs/dst/a.txt
echo "old-b"  > /tmp/rs/dst/b.txt

build_plan() {
  local src_dir=$1 dst_dir=$2
  for src in "$src_dir"/*; do
    local name=${src##*/}
    local dst=$dst_dir/$name
    if [[ ! -e "$dst" ]]; then
      printf 'COPY  %-12s -> %s\n' "$name" "$dst"
      continue
    fi
    if ! diff -q "$src" "$dst" >/dev/null 2>&1; then
      printf 'UPDATE %-11s -> %s\n' "$name" "$dst"
      continue
    fi
    printf 'SKIP   %-11s == %s\n' "$name" "$dst"
  done
  return 0
}

build_plan /tmp/rs/src /tmp/rs/dst
