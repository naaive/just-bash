#!/usr/bin/env bash
# Exercise arithmetic features end-to-end.

x=10
y=$((x * 3 + 1))
echo "$y"

# Bit operations.
echo $((0xff & 0x0f))
echo $((1 << 8))
echo $((255 >> 4))

# Pre/post increment.
i=5
echo $((i++)) "$i"
echo $((++i)) "$i"

# Ternary.
echo $(( y > 30 ? 100 : 200 ))

# Compound assignment.
n=10
(( n *= 3 ))
echo "$n"
