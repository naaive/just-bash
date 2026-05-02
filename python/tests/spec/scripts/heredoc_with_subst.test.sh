#!/usr/bin/env bash
# Heredocs: with and without substitution.

name=alice
count=3

cat <<EOF
hello $name (interp on)
EOF

cat <<'EOF'
hello $name (interp off)
EOF

cat <<-EOF
		(stripped) lines
		count is $count
EOF
