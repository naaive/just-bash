#!/usr/bin/env bash
# Test && / || short-circuit semantics.

t() { echo "ran-$1"; return "$2"; }

# Both succeed -> all branches print.
t a 0 && t b 0
echo --
# First fails -> short-circuit, second skipped.
t c 1 && t d 0
echo --
# First fails -> ||-fallback runs.
t e 1 || t f 0
echo --
# Chain: a OK, b FAIL, fallback c OK, then d OK.
t a 0 && t b 1 || t c 0 && t d 0
