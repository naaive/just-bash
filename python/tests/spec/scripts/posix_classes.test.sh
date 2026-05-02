#!/usr/bin/env bash
# POSIX char classes used in case + [[ ]] + parameter pattern.

for v in 5 a Z ' ' '!' .; do
  case "$v" in
    [[:digit:]]) echo "$v -> digit" ;;
    [[:alpha:]]) echo "$v -> alpha" ;;
    [[:space:]]) echo "$v -> space" ;;
    [[:punct:]]) echo "$v -> punct" ;;
    *) echo "$v -> other" ;;
  esac
done

# In [[ ]]:
v=hello123
if [[ "$v" == *[[:digit:]]* ]]; then
  echo "contains digit"
fi
