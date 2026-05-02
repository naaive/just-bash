#!/usr/bin/env bash
# autoconf-style feature detection: probe for tools and write config.h.

declare -A have

probe() {
  local cmd=$1
  if command -v "$cmd" >/dev/null 2>&1; then
    have[$cmd]=1
    echo "checking for $cmd... yes"
  else
    have[$cmd]=0
    echo "checking for $cmd... no"
  fi
}

# Probe a stable set: the first three are always present (sandbox builtins).
for cmd in echo printf cat tr sed awk; do
  probe "$cmd"
done

# Decide which features go into config.h.
{
  echo "/* generated config */"
  echo "#define HAVE_ECHO ${have[echo]}"
  echo "#define HAVE_PRINTF ${have[printf]}"
  echo "#define HAVE_TR ${have[tr]}"
  echo "#define HAVE_SED ${have[sed]}"
  echo "#define HAVE_AWK ${have[awk]}"
} > /tmp/config.h

cat /tmp/config.h
