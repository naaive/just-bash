#!/usr/bin/env bash
# Extract a single version block from a CHANGELOG.md.

mkdir -p /tmp
cat > /tmp/CHANGELOG.md <<'EOF'
# Changelog

## [1.2.0] - 2024-01-15
- Added new auth flow
- Fixed flaky tests

## [1.1.1] - 2023-12-01
- Patched buffer overrun

## [1.1.0] - 2023-11-20
- Initial public release
EOF

target_version=${1:-1.1.1}

awk -v ver="$target_version" '
  $0 ~ "^## \\[" ver "\\]" { capture=1; print; next }
  /^## \[/ && capture { exit }
  capture { print }
' /tmp/CHANGELOG.md
