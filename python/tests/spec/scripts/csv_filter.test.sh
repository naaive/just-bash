#!/usr/bin/env bash
# Filter a CSV: print rows whose 3rd column > 50, sorted by name.

csv=/tmp/data.csv
mkdir -p /tmp
cat > "$csv" <<'EOF'
name,role,score
alice,dev,75
bob,ops,40
carol,dev,90
dave,qa,55
eve,dev,30
EOF

tail -n +2 "$csv" | awk -F, '$3 > 50 {print $1","$3}' | sort
