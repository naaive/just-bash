#!/usr/bin/env bash
# Pattern from a typical backup script: snapshot a "data dir" into a
# timestamped tarball name, then prune all but the N latest by sort order.

set -e

mkdir -p /tmp/backups
# Pre-seed some fake older backups (lex order matches chrono since we use
# zero-padded timestamps).
touch /tmp/backups/db-20240101-010000.sql.gz
touch /tmp/backups/db-20240115-020000.sql.gz
touch /tmp/backups/db-20240201-030000.sql.gz
touch /tmp/backups/db-20240301-040000.sql.gz
touch /tmp/backups/db-20240401-050000.sql.gz

# Take a "new" backup with a fixed timestamp (so the test is deterministic).
new=/tmp/backups/db-20240501-060000.sql.gz
echo "BAK" > "$new"
echo "created $new"

KEEP=3
mapfile -t all < <(ls /tmp/backups | sort)
total=${#all[@]}
to_delete=$(( total - KEEP ))

if (( to_delete > 0 )); then
  echo "pruning $to_delete old backup(s):"
  for (( i = 0; i < to_delete; i++ )); do
    f=${all[$i]}
    echo "  rm /tmp/backups/$f"
    rm -f "/tmp/backups/$f"
  done
fi

echo "kept:"
ls /tmp/backups | sort
