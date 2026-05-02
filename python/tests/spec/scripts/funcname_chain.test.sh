#!/usr/bin/env bash
# Print the FUNCNAME stack from inside a nested call chain.
# Use only the inner-most frames, since ``bash file.sh`` adds a "main"
# bottom frame but ``bash -c`` (our comparison harness) does not.

inner() {
  echo "self=${FUNCNAME[0]}"
  echo "caller=${FUNCNAME[1]}"
}

middle() {
  inner
}

outer() {
  middle
}

outer
echo "top-level depth=${#FUNCNAME[@]}"
