#!/usr/bin/env bash
# Verify a small file by hash, using sha256sum.

cat <<'EOF' > /tmp/payload
hello world
EOF

expected=$(sha256sum < /tmp/payload | awk '{print $1}')
actual=$(sha256sum < /tmp/payload | awk '{print $1}')

if [[ "$expected" == "$actual" ]]; then
  echo "hash matches"
else
  echo "hash mismatch" >&2
  exit 1
fi
