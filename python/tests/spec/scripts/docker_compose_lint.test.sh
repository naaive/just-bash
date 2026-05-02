#!/usr/bin/env bash
# Lint a docker-compose.yml: check that every "image:" entry has a tag,
# and that no service uses :latest.

mkdir -p /tmp
cat > /tmp/docker-compose.yml <<'EOF'
version: "3"
services:
  web:
    image: nginx:1.25
    ports:
      - "80:80"
  api:
    image: myapp:latest
    depends_on: [db]
  db:
    image: postgres
  worker:
    image: redis:7-alpine
EOF

issues=0
service=""
while IFS= read -r line; do
  # Track current service for context.
  if [[ "$line" =~ ^[[:space:]]{2}([a-z][a-z0-9-]*): ]]; then
    service=${BASH_REMATCH[1]}
    continue
  fi
  # Look for image declarations.
  if [[ "$line" =~ ^[[:space:]]+image:[[:space:]]+(.+)$ ]]; then
    image=${BASH_REMATCH[1]}
    image=${image%\"}
    image=${image#\"}
    if [[ "$image" != *":"* ]]; then
      echo "[$service] missing tag: $image"
      issues=$((issues + 1))
    elif [[ "$image" == *":latest" ]]; then
      echo "[$service] uses :latest: $image"
      issues=$((issues + 1))
    else
      echo "[$service] ok: $image"
    fi
  fi
done < /tmp/docker-compose.yml

echo "issues: $issues"
