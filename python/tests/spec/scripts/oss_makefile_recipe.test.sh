#!/usr/bin/env bash
# A Make recipe extracted to a standalone script. Patterns: per-suffix rules,
# fail-fast on missing source, "stamp" file gating.

set -e

# Start fresh — real /tmp may have leftovers from a prior real-bash run.
rm -rf /tmp/mk-recipe-build /tmp/mk-recipe-src
mkdir -p /tmp/mk-recipe-build /tmp/mk-recipe-src
SRC=/tmp/mk-recipe-src
BLD=/tmp/mk-recipe-build
echo 'int main(){return 0;}'  > $SRC/a.c
echo 'package main; func A(){}' > $SRC/b.go
echo 'fn main() {}'             > $SRC/c.rs

compile_one() {
  local src=$1
  local base=$(basename "$src")
  local stamp=$BLD/${base}.stamp

  # Existence-only gating (the stamp is touched once we've compiled).
  # ``-nt`` would be ideal but mtime granularity differs between bash on
  # disk and the in-memory VFS, so we keep this deterministic.
  if [[ -f "$stamp" ]]; then
    echo "  $base up-to-date"
    return 0
  fi

  case "$src" in
    *.c)  echo "  cc -c $src -o $BLD/${base%.c}.o" ;;
    *.go) echo "  go tool compile -o $BLD/${base%.go}.o $src" ;;
    *.rs) echo "  rustc --emit=obj $src -o $BLD/${base%.rs}.o" ;;
    *)    echo "  skip: unsupported $src" ;;
  esac
  touch "$stamp"
}

for f in $SRC/*.c $SRC/*.go $SRC/*.rs; do
  compile_one "$f"
done

# Re-run: everything should be up-to-date.
echo "--- re-run ---"
for f in $SRC/*.c $SRC/*.go $SRC/*.rs; do
  compile_one "$f"
done

echo "objects:"
ls $BLD/ | grep stamp$ | sort
