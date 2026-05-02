#!/usr/bin/env bash
# printf %q produces output that re-parses to the same string.

original="hello world's \$pace"
quoted=$(printf '%q' "$original")
eval "echoed=$quoted"

if [[ "$echoed" == "$original" ]]; then
  echo "round-trip ok"
else
  echo "MISMATCH:"
  echo "  original=$original"
  echo "  echoed=$echoed"
fi
