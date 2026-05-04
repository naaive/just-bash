#!/usr/bin/env bash
# Pattern lifted from how autoconf's AC_CHECK_HEADERS / AC_CHECK_FUNCS work:
# probe a list of names, build a per-name HAVE_* macro into a generated
# header, and accumulate cflags.

declare -A FOUND
declare -A SOURCE
SOURCE[stddef.h]=system
SOURCE[stdint.h]=system
SOURCE[stdlib.h]=system
SOURCE[unistd.h]=system
SOURCE[zzz_imaginary.h]=missing
SOURCE[printf]=builtin
SOURCE[strdup]=missing
SOURCE[memrchr]=glibc

ac_check() {
  local kind=$1; local name=$2
  printf '%s ' "$kind" >/dev/null  # echo back to acknowledge the kind hint
  if [[ "${SOURCE[$name]}" == "missing" ]]; then
    echo "checking for $name... no"
    FOUND[$name]=0
    return 1
  fi
  echo "checking for $name... yes"
  FOUND[$name]=1
  return 0
}

for h in stddef.h stdint.h stdlib.h unistd.h zzz_imaginary.h; do
  ac_check header "$h"
done

for f in printf strdup memrchr; do
  ac_check function "$f"
done

echo "--- generated config.h ---"
{
  for name in stddef.h stdint.h stdlib.h unistd.h zzz_imaginary.h printf strdup memrchr; do
    macro="HAVE_$(echo "$name" | tr 'a-z.' 'A-Z_')"
    echo "#define $macro ${FOUND[$name]:-0}"
  done
} | sort
