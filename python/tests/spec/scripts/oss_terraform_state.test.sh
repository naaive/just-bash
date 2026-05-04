#!/usr/bin/env bash
# Terraform-style state-file mutator: read existing resource list, add a
# new one, write back, summarise.

mkdir -p /tmp/tf
cat > /tmp/tf/state <<'EOF'
# resource_type|name|attribute=value,...
aws_s3_bucket|logs|region=us-east-1
aws_s3_bucket|backups|region=us-west-2
aws_iam_role|admin|policies=AdministratorAccess
EOF

resources=()
while IFS= read -r line; do
  [[ -z "$line" || "$line" == \#* ]] && continue
  resources+=("$line")
done < /tmp/tf/state

# Add a new resource.
resources+=("aws_s3_bucket|metrics|region=eu-west-1")

# Group by type using assoc array of arrays (we use newline-separated text).
declare -A by_type
for r in "${resources[@]}"; do
  type=${r%%|*}
  rest=${r#*|}
  by_type[$type]+="$rest"$'\n'
done

# Emit a summary.
echo "summary:"
for type in $(printf '%s\n' "${!by_type[@]}" | sort); do
  count=$(echo "${by_type[$type]}" | grep -c .)
  echo "  $type: $count"
done

echo "--- resources ---"
for r in "${resources[@]}"; do
  type=${r%%|*}
  rest=${r#*|}
  name=${rest%%|*}
  printf '  %-18s %s\n' "$type" "$name"
done
