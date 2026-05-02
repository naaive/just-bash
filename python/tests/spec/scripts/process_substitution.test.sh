#!/usr/bin/env bash
# Compare two sorted lists via process substitution.

diff <(printf 'a\nb\nc\n') <(printf 'a\nx\nc\n') | head -10
