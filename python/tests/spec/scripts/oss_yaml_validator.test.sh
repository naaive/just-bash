#!/usr/bin/env bash
# A naive YAML-ish validator: check indentation is multiples of 2,
# detect tabs, ensure colon-followed values where applicable.

mkdir -p /tmp
cat > /tmp/cfg.yml <<'EOF'
server:
  host: localhost
  port: 8080
  ssl:
    enabled: true
    cert: /etc/ssl/cert.pem
clients:
  - alpha
  - beta
EOF

errors=0
lineno=0
while IFS= read -r line; do
  lineno=$((lineno + 1))
  # Detect tabs.
  if [[ "$line" == *$'\t'* ]]; then
    echo "line $lineno: tab character"
    errors=$((errors + 1))
    continue
  fi
  # Compute leading spaces.
  trimmed=${line#"${line%%[![:space:]]*}"}
  prefix_len=$(( ${#line} - ${#trimmed} ))
  if (( prefix_len % 2 != 0 )); then
    echo "line $lineno: odd indent ($prefix_len)"
    errors=$((errors + 1))
  fi
  # Skip blank / list / comment.
  [[ -z "$trimmed" || "$trimmed" == \#* || "$trimmed" == -* ]] && continue
  # mapping key must contain ':'.
  if [[ "$trimmed" != *:* ]]; then
    echo "line $lineno: missing colon in '$trimmed'"
    errors=$((errors + 1))
  fi
done < /tmp/cfg.yml

if (( errors == 0 )); then
  echo "valid"
fi
echo "errors=$errors"
