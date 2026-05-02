#!/usr/bin/env bash
# Heavy parameter-expansion exercise.

s="The Quick Brown FOX"
echo "${s,,}"          # all lower
echo "${s^^}"          # all upper
echo "${s/Quick/Slow}" # first replace
echo "${s// /-}"       # all spaces -> dash
echo "${s%X}"          # trailing X removed (suffix)
echo "${s#The }"       # leading "The " stripped
echo "${#s}"           # length
echo "${s:4:5}"        # substring
