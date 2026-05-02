#!/usr/bin/env bash
# Top-K word frequency.

text="the quick brown fox jumps over the lazy dog the fox jumps high"
echo "$text" | tr ' ' '\n' | sort | uniq -c | sort -rn | head -3
