#!/usr/bin/env bash
# Quoting rules: single, double, backslash, $'...' (ANSI-C is bash-specific
# and not yet covered by just-bash-py; we use the safer subset only).

echo 'literal $var \\ "quote"'
echo "double ${USER:-anon}"
echo "tab\\there"
echo "newline-within-quotes
on second line"

# Mixing.
x=value
echo "leading"' '"$x"' '"trailing"

# Escaped special chars.
echo \$dollar \" \\
