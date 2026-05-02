#!/usr/bin/env bash
# [[ ]] conditional expressions and [ ] tests.

if [[ "hello" == h*o ]]; then echo "glob match"; fi
if [[ "abc123" =~ ^[a-z]+[0-9]+$ ]]; then echo "regex match"; fi

if [ -z "" ]; then echo "empty"; fi
if [ -n "x" ]; then echo "nonempty"; fi
if [ "5" -lt "10" ]; then echo "5<10"; fi
if [ "abc" = "abc" ]; then echo "abc=abc"; fi

# Nested logic.
if [[ "a" == "a" && "b" != "c" ]]; then
  echo "and works"
fi

if [[ "x" == "y" || "z" == "z" ]]; then
  echo "or works"
fi
