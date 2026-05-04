#!/usr/bin/env bash
# Pattern from CI .bashrc / setup-script: exit early if already bootstrapped,
# pick up tool versions from ASDF-style file, write to GITHUB_ENV-style sink.

set -euo pipefail

# Idempotency guard.
if [[ -n "${BOOTSTRAP_DONE:-}" ]]; then
  echo "already bootstrapped"
  exit 0
fi

mkdir -p /tmp/.tool-versions-test
cat > /tmp/.tool-versions-test/.tool-versions <<'EOF'
nodejs 20.10.0
python 3.11.7
ruby 3.2.2
# rust pinned by rust-toolchain.toml
golang 1.21.5
EOF

# Parse and emit GITHUB_ENV-style "NAME=VALUE" lines.
sink=/tmp/github_env
> "$sink"

while IFS=' ' read -r tool version; do
  # Skip blanks and comments.
  [[ -z "$tool" || "$tool" == \#* ]] && continue
  upper=$(echo "$tool" | tr 'a-z' 'A-Z')
  echo "${upper}_VERSION=${version}" >> "$sink"
done < /tmp/.tool-versions-test/.tool-versions

echo "--- bootstrap output ---"
sort "$sink"
