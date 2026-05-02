#!/usr/bin/env bash
# Indexed and associative arrays.

arr=(zero one two three)
echo "len=${#arr[@]}"
echo "first=${arr[0]}"
arr+=(four)
echo "after-append=${arr[@]}"

# Iteration with index.
for ((i = 0; i < ${#arr[@]}; i++)); do
  echo "$i:${arr[$i]}"
done

declare -A m
m[apple]=red
m[banana]=yellow
m[grape]=purple

# Sort the iteration so output is deterministic across bashes.
for k in "${!m[@]}"; do
  echo "$k=${m[$k]}"
done | sort
