#!/usr/bin/env bash
# A common helper script: classify branch names and decide deploy targets.

branches=(
  main
  develop
  release/v1.2.0
  feature/auth-revamp
  hotfix/critical-bug
  bugfix/login-redirect
  chore/update-deps
  experimental/spike
)

deploy_target() {
  local branch=$1
  case "$branch" in
    main)              echo "production" ;;
    develop|staging)   echo "staging" ;;
    release/*)         echo "qa" ;;
    hotfix/*)          echo "production-hotfix" ;;
    feature/*|bugfix/*)echo "preview" ;;
    chore/*)           echo "ci-only" ;;
    *)                 echo "no-deploy" ;;
  esac
}

semver_only() {
  local branch=$1
  if [[ "$branch" =~ ^release/v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
    printf '%s.%s.%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}" "${BASH_REMATCH[3]}"
  else
    echo "(no semver)"
  fi
}

declare -A by_target=(
  [production]=0
  [staging]=0
  [qa]=0
  [production-hotfix]=0
  [preview]=0
  [ci-only]=0
  [no-deploy]=0
)

for b in "${branches[@]}"; do
  t=$(deploy_target "$b")
  by_target[$t]=$(( by_target[$t] + 1 ))
  printf '%-30s %-20s %s\n' "$b" "$t" "$(semver_only "$b")"
done

echo "---"
for t in $(printf '%s\n' "${!by_target[@]}" | sort); do
  echo "$t: ${by_target[$t]}"
done
