#!/usr/bin/env bash
# getopts with mandatory flag values.

set -- -v -n 5 -o /tmp/out arg1 arg2

verbose=0
count=0
out=

OPTIND=1
while getopts ":vn:o:" opt; do
  case "$opt" in
    v) verbose=$((verbose + 1)) ;;
    n) count=$OPTARG ;;
    o) out=$OPTARG ;;
    \?) echo "bad: $OPTARG" >&2; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

echo "verbose=$verbose count=$count out=$out"
echo "rest: $*"
