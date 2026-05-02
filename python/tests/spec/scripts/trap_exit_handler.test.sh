#!/usr/bin/env bash
# trap EXIT cleanup.

cleanup() {
  echo "cleanup invoked"
}
trap cleanup EXIT

echo "main work"
exit 0
