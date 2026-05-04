#!/usr/bin/env bash
# Manual long-option parser (since `getopt --longoptions` isn't always
# available). Handles --flag, --opt=value, and --opt value forms.

set -- --verbose --output=/tmp/out --threads 4 --quiet=no positional1 positional2

verbose=0
output=
threads=1
quiet=yes
positional=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --verbose)         verbose=1; shift ;;
    --output=*)        output=${1#--output=}; shift ;;
    --output)          output=$2; shift 2 ;;
    --threads=*)       threads=${1#--threads=}; shift ;;
    --threads)         threads=$2; shift 2 ;;
    --quiet=*)         quiet=${1#--quiet=}; shift ;;
    --quiet)           quiet=$2; shift 2 ;;
    --)                shift; while (( $# > 0 )); do positional+=("$1"); shift; done ;;
    --*)               echo "unknown long flag: $1" >&2; exit 2 ;;
    *)                 positional+=("$1"); shift ;;
  esac
done

echo "verbose=$verbose"
echo "output=$output"
echo "threads=$threads"
echo "quiet=$quiet"
echo "positional[${#positional[@]}]=${positional[*]}"
