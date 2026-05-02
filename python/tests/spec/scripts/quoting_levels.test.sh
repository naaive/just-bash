#!/usr/bin/env bash
# Mixed quoting: single, double, ANSI-C, escaped chars.

x="dollar"

# Single quotes are literal.
echo 'literal $x and \n'

# Double quotes interpolate variables but treat backslashes mostly literally.
echo "value $x and tab\there"

# ANSI-C $'...' processes \n, \t, \\ etc.
printf '%s\n' $'line1\nline2\tindented'

# Adjacent strings of different quoting concatenate.
echo 'a''b'"c""$x"
