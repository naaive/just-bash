#!/usr/bin/env bash
# Reformat a flat JSON line into a pretty-printed structure using awk.

input='{"name":"alice","age":30,"hobbies":["reading","coding"],"active":true}'

echo "$input" | awk '
{
  indent = 0
  for (i = 1; i <= length($0); i++) {
    c = substr($0, i, 1)
    if (c == "{" || c == "[") {
      printf "%s\n", c
      indent++
      for (j = 0; j < indent; j++) printf "  "
    } else if (c == "}" || c == "]") {
      printf "\n"
      indent--
      for (j = 0; j < indent; j++) printf "  "
      printf "%s", c
    } else if (c == ",") {
      printf "%s\n", c
      for (j = 0; j < indent; j++) printf "  "
    } else {
      printf "%s", c
    }
  }
  printf "\n"
}
'
