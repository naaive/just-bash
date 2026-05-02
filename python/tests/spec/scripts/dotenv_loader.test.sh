#!/usr/bin/env bash
# Load a .env file into the environment, ignoring comments and quoting.

env_file=/tmp/app.env
mkdir -p /tmp
cat > "$env_file" <<'EOF'
# database
DB_HOST=localhost
DB_PORT=5432
DB_NAME="prod-db"

# api
API_KEY='super secret'
DEBUG=1
EOF

while IFS= read -r line; do
  # Strip trailing CR (handle CRLF inputs).
  line=${line%$'\r'}
  # Skip blanks and comments.
  [[ -z "$line" ]] && continue
  [[ "$line" =~ ^[[:space:]]*# ]] && continue
  # Split key/value.
  key=${line%%=*}
  val=${line#*=}
  # Strip outer single or double quotes if present.
  if [[ "$val" == \"*\" ]]; then
    val=${val#\"}; val=${val%\"}
  elif [[ "$val" == \'*\' ]]; then
    val=${val#\'}; val=${val%\'}
  fi
  printf 'export %s=%q\n' "$key" "$val"
done < "$env_file"
