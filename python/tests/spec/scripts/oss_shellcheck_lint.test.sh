#!/usr/bin/env bash
# Tiny shellcheck-style linter: flag a handful of common pitfalls in a
# user-supplied script.

mkdir -p /tmp
cat > /tmp/sample.sh <<'EOF'
#!/usr/bin/env bash
x=$1
y=$x
if [ -n $y ]; then
  echo "got $y"
fi
ls *.txt | wc -l
echo "no quotes around $variable"
EOF

flag() {
  local rule=$1 line=$2 msg=$3
  printf '%-7s line %d: %s\n' "$rule" "$line" "$msg"
  return 0
}

# Pre-build the literal patterns once so the case clauses stay simple.
P_NTEST='[ -n $'
P_ZTEST='[ -z $'

lineno=0
while IFS= read -r line; do
  lineno=$((lineno + 1))
  if [[ "$line" == *"$P_NTEST"* || "$line" == *"$P_ZTEST"* ]]; then
    flag SC2086 "$lineno" "unquoted dollar in test"
  fi
  if [[ "$line" =~ ls[[:space:]]+\*\.[a-zA-Z]+[[:space:]]*\| ]]; then
    flag SC2012 "$lineno" "use find instead of ls in pipe"
  fi
done < /tmp/sample.sh

echo "scan complete"
