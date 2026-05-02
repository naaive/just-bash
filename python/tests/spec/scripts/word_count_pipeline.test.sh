#!/usr/bin/env bash
# Pipeline: split words, lowercase, sort, uniq -c, then sort by count.

text="The quick brown fox jumps over the lazy dog The fox is quick"

echo "$text" \
  | tr ' ' '\n' \
  | tr '[:upper:]' '[:lower:]' \
  | sort \
  | uniq -c \
  | sort -nr \
  | head -3 \
  | sed 's/^ *//'
