#!/usr/bin/env bash
# Realistic argparse pattern with getopts + positional fallback.

verbose=0
output=
threshold=0

usage() {
  cat <<EOF
usage: $(basename "$0") [-v] [-o FILE] [-t N] FILE...
EOF
}

while getopts "vo:t:h" opt; do
  case $opt in
    v) verbose=1 ;;
    o) output=$OPTARG ;;
    t) threshold=$OPTARG ;;
    h) usage; exit 0 ;;
    \?) echo "bad opt"; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

set -- -t 5 -v -o out.txt input1 input2

# (Re-run with synthetic args.)
OPTIND=1
verbose=0
output=
threshold=0
while getopts "vo:t:h" opt; do
  case $opt in
    v) verbose=1 ;;
    o) output=$OPTARG ;;
    t) threshold=$OPTARG ;;
  esac
done
shift $((OPTIND - 1))

echo "verbose=$verbose output=$output threshold=$threshold"
echo "files:"
for f in "$@"; do
  echo "- $f"
done
