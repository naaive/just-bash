#!/usr/bin/env bash
# Tiny finite-state machine using case + arithmetic.

state=start
emit=()
for token in begin payload payload end other; do
  case $state in
    start)
      if [[ $token == "begin" ]]; then
        state=in
        emit+=("BEGIN")
      else
        emit+=("ignore:$token")
      fi
      ;;
    in)
      if [[ $token == "end" ]]; then
        state=done_
        emit+=("END")
      else
        emit+=("payload:$token")
      fi
      ;;
    done_)
      emit+=("after:$token")
      ;;
  esac
done

for x in "${emit[@]}"; do
  echo "$x"
done
echo "final=$state"
