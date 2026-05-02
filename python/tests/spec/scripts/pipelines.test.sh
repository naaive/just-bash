#!/usr/bin/env bash
# Pipelines and redirection.

printf '%s\n' alpha beta gamma | grep -c 'a'

printf 'banana\napple\ncherry\n' | sort | head -1

printf '%s\n' 1 2 3 4 5 | awk '{ s += $1 } END { print s }'

# Negation of a pipeline.
! true | false
echo "rc=$?"

# Stdin redirect via heredoc.
cat <<EOF
line1
line2 $(echo dyn)
EOF

# 2>&1 merge.
(echo out; echo err >&2) 2>&1 | wc -l
