#!/usr/bin/env bash
# Here-string + pipeline + tr.

s="HELLO WORLD"
result=$(tr 'A-Z' 'a-z' <<< "$s")
echo "[$result]"
