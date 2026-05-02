#!/usr/bin/env bash
# Heredocs of every flavour.

cat <<EOF
plain heredoc
EOF

name=alice
cat <<EOF
expanded: $name and $(echo today)
EOF

cat <<'NOEXPAND'
literal: $name and $(echo today)
NOEXPAND

cat <<-INDENTED
	tab-stripped 1
	tab-stripped 2
	INDENTED

# Here-string.
cat <<<"here-string content"
