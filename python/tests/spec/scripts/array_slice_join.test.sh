#!/usr/bin/env bash
# Array slicing and joining via custom IFS.

arr=(zero one two three four five)

echo "${arr[@]:2}"
echo "${arr[@]:1:3}"
echo "len=${#arr[@]}"
echo "lengths: ${#arr[0]} ${#arr[3]}"

# Join all elements with comma using IFS in a subshell.
joined=$(IFS=,; echo "${arr[*]}")
echo "$joined"
