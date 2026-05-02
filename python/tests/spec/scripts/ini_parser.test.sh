#!/usr/bin/env bash
# Parse a tiny INI file into associative arrays per section.

ini=/tmp/cfg.ini
mkdir -p /tmp
cat > "$ini" <<'EOF'
[server]
host=example.com
port=8080
[client]
retries=3
timeout=30
EOF

declare -A server
declare -A client
section=""

while IFS= read -r line; do
  case "$line" in
    \[*\])
      section=${line#[}
      section=${section%]}
      ;;
    *=*)
      key=${line%%=*}
      val=${line#*=}
      case "$section" in
        server) server[$key]=$val ;;
        client) client[$key]=$val ;;
      esac
      ;;
  esac
done < "$ini"

echo "server.host=${server[host]}"
echo "server.port=${server[port]}"
echo "client.retries=${client[retries]}"
echo "client.timeout=${client[timeout]}"
