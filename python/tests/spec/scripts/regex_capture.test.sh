#!/usr/bin/env bash
# Regex captures into BASH_REMATCH.

if [[ "version=1.2.3-beta" =~ version=([0-9]+)\.([0-9]+)\.([0-9]+) ]]; then
  echo "major=${BASH_REMATCH[1]}"
  echo "minor=${BASH_REMATCH[2]}"
  echo "patch=${BASH_REMATCH[3]}"
  echo "full=${BASH_REMATCH[0]}"
fi

# Failed match clears BASH_REMATCH.
[[ "no" =~ ^([0-9]+)$ ]]
echo "rc=$? len=${#BASH_REMATCH[@]}"
