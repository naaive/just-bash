#!/usr/bin/env bash
# case with character ranges (POSIX-style ranges only).

for v in 5 a Z ' ' '!' . _ '#'; do
  case "$v" in
    [0-9]) echo "$v -> digit" ;;
    [a-z]) echo "$v -> lower" ;;
    [A-Z]) echo "$v -> upper" ;;
    [.,_]) echo "$v -> separator" ;;
    [!a-zA-Z0-9.,_\ ]) echo "$v -> punct" ;;
    *) echo "$v -> other" ;;
  esac
done
