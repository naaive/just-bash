#!/usr/bin/env bash
# Pattern from test runners (bats-core, sh-style):
# discover *.test.sh files, run each, capture rc, print TAP-ish summary.

mkdir -p /tmp/tt
cat > /tmp/tt/a.test.sh <<'EOF'
#!/bin/bash
echo "ok 1 - addition"
exit 0
EOF
cat > /tmp/tt/b.test.sh <<'EOF'
#!/bin/bash
echo "ok 1 - first"
echo "not ok 2 - second"
exit 1
EOF
cat > /tmp/tt/c.test.sh <<'EOF'
#!/bin/bash
echo "ok 1 - hello"
exit 0
EOF

passed=0
failed=0
total=0
results=()

for t in $(ls /tmp/tt/*.test.sh | sort); do
  total=$((total + 1))
  name=$(basename "$t")
  out=$(bash "$t" 2>&1)
  rc=$?
  if (( rc == 0 )); then
    passed=$((passed + 1))
    results+=("PASS  $name")
  else
    failed=$((failed + 1))
    results+=("FAIL  $name (rc=$rc)")
  fi
done

printf '%s\n' "${results[@]}"
echo "---"
echo "$passed passed, $failed failed, $total total"
exit $(( failed > 0 ? 1 : 0 ))
