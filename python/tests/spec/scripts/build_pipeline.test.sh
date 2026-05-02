#!/usr/bin/env bash
# A miniature build pipeline: write sources, run a "compilation" via sed,
# collect stats. Exercises file IO + sed + control-flow + arithmetic.

set -e

mkdir -p /tmp/build/src /tmp/build/out

i=0
for name in alpha beta gamma delta; do
  ((i++))
  cat <<EOF > "/tmp/build/src/$name.c"
int main(void) { return $i; }
EOF
done

# "Compile": prefix every line with ``//`` so we have measurable artefacts.
for src in /tmp/build/src/*.c; do
  out=/tmp/build/out/$(basename "$src" .c).o
  sed 's,^,// ,' "$src" > "$out"
done

# Collect counts (always deterministic).
files_in=$(ls /tmp/build/src | wc -l)
files_out=$(ls /tmp/build/out | wc -l)
total_lines=$(wc -l /tmp/build/out/*.o | tail -n 1)

echo "in:$files_in out:$files_out"
echo "total:${total_lines##* }"
