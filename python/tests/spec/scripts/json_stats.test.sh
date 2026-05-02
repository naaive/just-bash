#!/usr/bin/env bash
# Use the bundled jq subset to extract simple stats.

cat <<'JSON' > /tmp/cfg.json
{"name":"sample","items":[10,20,30,40],"flags":{"verbose":true}}
JSON

echo "name=$(jq -r .name /tmp/cfg.json)"
echo "len=$(jq -r 'length' /tmp/cfg.json)"
echo "first=$(jq -r '.items[0]' /tmp/cfg.json)"
