#!/usr/bin/env bash
# Pattern from kubectl/Helm wrapper scripts: parse --namespace / --context
# from arbitrary positions, leave the rest untouched, then call through.

args=(--context prod-east --replicas 3 -n staging deploy myapp --rollout)

context=
namespace=default
positional=()
i=0
while (( i < ${#args[@]} )); do
  a=${args[$i]}
  case "$a" in
    --context|-c)
      context=${args[$((i+1))]}
      i=$((i + 2))
      ;;
    --context=*)
      context=${a#--context=}
      i=$((i + 1))
      ;;
    --namespace|-n)
      namespace=${args[$((i+1))]}
      i=$((i + 2))
      ;;
    --namespace=*)
      namespace=${a#--namespace=}
      i=$((i + 1))
      ;;
    *)
      positional+=("$a")
      i=$((i + 1))
      ;;
  esac
done

echo "context=$context"
echo "namespace=$namespace"
echo "positional=(${positional[*]})"

# Build the would-be invocation.
cmd=(kubectl)
[[ -n "$context" ]] && cmd+=(--context "$context")
cmd+=(-n "$namespace")
cmd+=("${positional[@]}")
echo "exec: ${cmd[*]}"
