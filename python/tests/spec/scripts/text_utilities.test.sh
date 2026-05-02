#!/usr/bin/env bash
# Pipelines through grep/sed/awk/sort/uniq.

input='alpha beta alpha gamma alpha beta'

echo "$input" | tr ' ' '\n' | sort | uniq -c | sort -rn

# sed with anchored substitution.
echo "$input" | sed 's/alpha/A/g'

# awk computing stats.
echo "$input" | tr ' ' '\n' | awk '{ counts[$0]++ } END { for (k in counts) print k": "counts[k] }' | sort

# cut with delimiter.
echo "a:b:c:d" | cut -d: -f2,4
