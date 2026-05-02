#!/usr/bin/env bash
# printf format string is reused for multiple value tuples.

printf '%-6s %3d\n' alpha 1 beta 22 gamma 333

printf 'hex=%x oct=%o bin=%d\n' 255 8 5

# %s with no argument prints empty string per POSIX.
printf '[%s]\n' a b c
