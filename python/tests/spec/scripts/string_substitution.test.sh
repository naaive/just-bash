#!/usr/bin/env bash
# Parameter-expansion substitutions: prefix/suffix anchors and replace-all.

s="alpha-beta-gamma-beta-delta"

echo "${s/beta/X}"     # first only
echo "${s//beta/X}"    # all
echo "${s/#alpha/A}"   # anchored at start
echo "${s/%delta/D}"   # anchored at end
echo "${s/-/_}"        # first dash
echo "${s//-/_}"       # all dashes
