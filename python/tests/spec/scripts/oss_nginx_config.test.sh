#!/usr/bin/env bash
# Generate nginx server blocks for a list of vhosts.

vhosts=(
  "example.com:8080:/var/www/example"
  "api.example.com:9000:/var/www/api"
  "static.example.com:80:/var/www/static"
)

mkdir -p /tmp/nginx
out=/tmp/nginx/sites.conf
> "$out"

for entry in "${vhosts[@]}"; do
  IFS=':' read -r host port root <<< "$entry"
  cat >> "$out" <<EOF
server {
    listen $port;
    server_name $host;
    root $root;
    location / {
        try_files \$uri \$uri/ =404;
    }
}

EOF
done

# Print the generated file.
cat "$out"

# Validate: count server blocks, ensure each vhost is referenced.
n=$(grep -c '^server {' "$out")
echo "blocks: $n"
for entry in "${vhosts[@]}"; do
  host=${entry%%:*}
  if grep -q "server_name $host;" "$out"; then
    echo "ok: $host"
  else
    echo "MISSING: $host"
  fi
done
