#!/usr/bin/env bash
# Verify set -o pipefail propagates failures through pipelines.

set -o pipefail

# A failing first stage should make the whole pipeline fail.
( false; echo unreachable ) | cat
echo "rc=$?"

# All-success pipeline returns 0.
( echo ok ) | cat
echo "rc=$?"

set +o pipefail
# Without pipefail, a failing first stage doesn't propagate.
false | true
echo "off-rc=$?"
