#!/usr/bin/env bash
# extglob inside [[ ]] requires shopt -s extglob.
shopt -s extglob

for v in foo.txt foo.md alpha beta gamma 123abc abc; do
  if [[ "$v" == @(foo.txt|foo.md) ]]; then
    echo "$v: pair"
  elif [[ "$v" == !(*.txt|*.md) ]]; then
    echo "$v: not-text"
  else
    echo "$v: text"
  fi
done
