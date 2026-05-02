#!/usr/bin/env bash
# Real-world getopts pattern.

set -- -v -n 5 -- one two three

verbose=0
count=1
while getopts "vn:h" opt; do
  case $opt in
    v) verbose=1 ;;
    n) count=$OPTARG ;;
    h) echo "usage: ..." ; exit 0 ;;
    *) echo "bad opt $opt" >&2 ; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

echo "verbose=$verbose count=$count"
echo "args: $*"
for a in "$@"; do
  echo "[$a]"
done
