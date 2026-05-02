#!/usr/bin/env bash
# Use namerefs to swap two variables.

a=alpha
b=beta

swap() {
  local -n x=$1
  local -n y=$2
  local tmp=$x
  x=$y
  y=$tmp
}

swap a b
echo "a=$a"
echo "b=$b"
