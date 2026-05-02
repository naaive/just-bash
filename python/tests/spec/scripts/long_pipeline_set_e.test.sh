#!/usr/bin/env bash
# Combination: set -e + pipefail + intermediate failure should halt the script.

set -e
set -o pipefail

# This pipeline succeeds; script continues.
echo first | grep first

# This pipeline's first stage fails; pipefail propagates; -e halts.
echo before
( exit 7 ) | cat || echo "caught: pipeline rc=$?"
echo after
