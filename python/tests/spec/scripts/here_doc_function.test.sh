#!/usr/bin/env bash
# A function that emits a heredoc.

emit() {
  cat <<EOF
[$1]
key=value
nested=${2:-default}
EOF
}

emit alpha
emit beta override
