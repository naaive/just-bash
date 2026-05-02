#!/usr/bin/env bash
# Control-flow constructs.

for i in 1 2 3; do
  for j in a b; do
    echo "$i$j"
  done
done

n=0
while (( n < 4 )); do
  echo "n=$n"
  ((n++))
done

x=hello
case $x in
  h*) echo "starts with h" ;;
  *)  echo "other" ;;
esac

if [[ -z "" ]]; then echo empty; fi
if (( 5 > 3 )); then echo greater; fi
