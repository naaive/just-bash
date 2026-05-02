#!/usr/bin/env bash
# uniq -c with sort, then numeric reverse.

text=$'apple\nbanana\napple\ncherry\nbanana\napple\ndate'
echo "$text" | sort | uniq -c | sort -nr
