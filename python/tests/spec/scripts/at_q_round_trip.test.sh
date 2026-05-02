#!/usr/bin/env bash
# ${var@Q} produces output that round-trips through eval.

for original in "hello" "hello world" "don't" "with a ; semicolon" ""; do
  quoted=${original@Q}
  eval "echoed=$quoted"
  if [[ "$echoed" == "$original" ]]; then
    printf 'ok: [%s] -> %s\n' "$original" "$quoted"
  else
    printf 'BAD: [%s] -> %s -> [%s]\n' "$original" "$quoted" "$echoed"
  fi
done
