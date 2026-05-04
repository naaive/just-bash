#!/usr/bin/env bash
# pg_dump-style wrapper: pick compression based on filename suffix, build
# the command, and verify the dump exists afterwards.

# Inputs that drive the wrapper.
DB_NAME=appdb
OUT_DIR=/tmp/dumps
mkdir -p "$OUT_DIR"

target_for() {
  local suffix=$1
  local out=$OUT_DIR/$DB_NAME-$(printf '%s' "$(date -u +%Y%m%d || echo 20240101)").sql.$suffix
  # Use a fixed timestamp so the test is deterministic.
  out=$OUT_DIR/$DB_NAME-20240101.sql.$suffix
  printf '%s' "$out"
  return 0
}

dump() {
  local suffix=$1
  local target=$(target_for "$suffix")
  local pipe_cmd=
  case "$suffix" in
    gz)  pipe_cmd="| gzip -c" ;;
    bz2) pipe_cmd="| bzip2 -c" ;;
    xz)  pipe_cmd="| xz -c" ;;
    zst) pipe_cmd="| zstd -c" ;;
    "")  pipe_cmd="" ;;
    *)   echo "unsupported suffix: $suffix" >&2; return 2 ;;
  esac

  # Pretend to run the pipeline; we just write a stub file.
  printf 'SQL DUMP for %s (%s)\n' "$DB_NAME" "$suffix" > "$target"
  echo "would run: pg_dump $DB_NAME ${pipe_cmd:+$pipe_cmd} > $target"
  echo "  written: $target ($(wc -c < "$target") bytes)"
}

for suf in gz bz2 xz zst ""; do
  dump "$suf"
done

echo "--- dump dir ---"
ls "$OUT_DIR" | sort
