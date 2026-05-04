#!/usr/bin/env bash
# Generate a systemd-style unit file from a small "template" via heredoc +
# ${var} substitution.

NAME=myapp
DESC="MyApp service"
USER=app
EXEC=/usr/local/bin/myapp
PORT=8080

mkdir -p /tmp/units

cat > /tmp/units/${NAME}.service <<EOF
[Unit]
Description=$DESC
After=network.target

[Service]
Type=simple
User=$USER
ExecStart=$EXEC --port $PORT
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Sanity check: read it back and assert key directives are present.
required=(
  "Description=$DESC"
  "User=$USER"
  "ExecStart=$EXEC --port $PORT"
)
unit=$(cat /tmp/units/${NAME}.service)
missing=0
for line in "${required[@]}"; do
  if [[ "$unit" != *"$line"* ]]; then
    echo "MISSING: $line"
    missing=$((missing + 1))
  fi
done
if (( missing == 0 )); then
  echo "unit OK"
fi

# Show the [Service] section only.
awk '/^\[Service\]/{flag=1; next} /^\[/{flag=0} flag && NF' \
  /tmp/units/${NAME}.service
