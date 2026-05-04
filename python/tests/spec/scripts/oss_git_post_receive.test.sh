#!/usr/bin/env bash
# Modeled on git's contrib/hooks/post-receive-email and friends:
# parse a "old new ref" line per pushed ref and act per branch.

# Stand-in for stdin from git: each line is "<old-sha> <new-sha> <ref>".
input='\
0000000000000000000000000000000000000000 a1b2c3d4e5f60718293a4b5c6d7e8f9000000000 refs/heads/main
1111111111111111111111111111111111111111 0000000000000000000000000000000000000000 refs/heads/feature/dropme
2222222222222222222222222222222222222222 3333333333333333333333333333333333333333 refs/heads/release/v2.0
ffffffffffffffffffffffffffffffffffffffff 0000000000000000000000000000000000000000 refs/tags/v1.0
'

zero_sha=0000000000000000000000000000000000000000

while IFS=' ' read -r old new ref; do
  [[ -z "$ref" ]] && continue

  case "$ref" in
    refs/heads/*) refkind=branch; name=${ref#refs/heads/} ;;
    refs/tags/*)  refkind=tag;    name=${ref#refs/tags/} ;;
    *)            refkind=other;  name=$ref ;;
  esac

  if [[ "$old" == "$zero_sha" ]]; then
    action=create
  elif [[ "$new" == "$zero_sha" ]]; then
    action=delete
  else
    action=update
  fi

  printf '%-7s %-6s %-25s %s..%s\n' "$action" "$refkind" "$name" "${old:0:7}" "${new:0:7}"
done <<< "$input"
