#!/usr/bin/env bash
# Simplified Homebrew-style formula install: extract version from a URL,
# verify a sha256, run pre/post hooks deterministically.

# Formula info (would normally come from a Ruby file).
URL='https://example.com/jq-1.7.1.tar.gz'
EXPECTED_SHA=feedface

# Extract version from filename portion of URL.
filename=${URL##*/}
if [[ "$filename" =~ ^([a-z]+)-([0-9]+\.[0-9]+\.[0-9]+)\.tar\.gz$ ]]; then
  pkg=${BASH_REMATCH[1]}
  ver=${BASH_REMATCH[2]}
else
  echo "could not parse URL: $URL" >&2
  exit 1
fi

echo "package: $pkg"
echo "version: $ver"

# Pre-install hook: ensure dest dir exists.
prefix=/tmp/Cellar/$pkg/$ver
mkdir -p "$prefix"
echo "prefix: $prefix"

# Pretend download + checksum.
actual_sha=$EXPECTED_SHA
if [[ "$actual_sha" != "$EXPECTED_SHA" ]]; then
  echo "checksum mismatch" >&2
  exit 2
fi

# Post-install: link binaries.
mkdir -p /tmp/bin
ln_target=$prefix/bin/$pkg
mkdir -p "$prefix/bin"
echo "stub binary" > "$ln_target"
cp "$ln_target" /tmp/bin/$pkg

echo "installed: $(cat /tmp/bin/$pkg)"
echo "shadowed at: /tmp/bin/$pkg"
