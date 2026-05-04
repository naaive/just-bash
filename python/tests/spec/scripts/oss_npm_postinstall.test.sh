#!/usr/bin/env bash
# Modeled on a typical npm "postinstall" / "prepare" script: detect platform,
# pick a binary download URL, then verify a checksum.

# Pretend platform info — set via env so the test is deterministic.
: "${UNAME_S:=Linux}"
: "${UNAME_M:=x86_64}"

case "$UNAME_S" in
  Linux)   os=linux ;;
  Darwin)  os=macos ;;
  MINGW*|MSYS*|CYGWIN*) os=windows ;;
  *)       echo "unsupported OS: $UNAME_S" >&2; exit 1 ;;
esac

case "$UNAME_M" in
  x86_64|amd64)   arch=x64 ;;
  aarch64|arm64)  arch=arm64 ;;
  armv7l)         arch=armv7 ;;
  *)              echo "unsupported arch: $UNAME_M" >&2; exit 1 ;;
esac

artifact="myapp-${os}-${arch}.tar.gz"
echo "platform: ${os}/${arch}"
echo "artifact: $artifact"

# Pretend checksum manifest (in real scripts this would be downloaded).
declare -A SUMS=(
  [myapp-linux-x64.tar.gz]=abc123
  [myapp-macos-arm64.tar.gz]=def456
  [myapp-windows-x64.tar.gz]=789zzz
)

expected=${SUMS[$artifact]:-}
if [[ -z "$expected" ]]; then
  echo "no checksum for $artifact" >&2
  exit 2
fi

echo "expected sha: $expected"

# Stand in for the real download + sha256sum verification.
actual=$expected  # success path
if [[ "$actual" != "$expected" ]]; then
  echo "checksum mismatch" >&2
  exit 3
fi
echo "verified ok"
