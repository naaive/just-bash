#!/usr/bin/env bash
# Parameter expansion grab-bag.

s=hello
echo "${#s}"
echo "${s:1:3}"
echo "${s^^}"
echo "${s,,}"
echo "${s/ll/LL}"

p=foo.bar.baz
echo "${p#*.}"
echo "${p##*.}"
echo "${p%.*}"
echo "${p%%.*}"

# Default / alternate.
echo "${unset:-fallback}"
unset y
echo "${y:=set}-$y"
echo "${s:+yes}"

# Indirect.
ref=s
echo "${!ref}"

# Array length / iteration.
arr=(a b "c d")
echo "len=${#arr[@]}"
for x in "${arr[@]}"; do
  echo "<$x>"
done
