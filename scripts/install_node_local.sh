#!/usr/bin/env bash
# Portable Node.js 22 for Termit client builds (no Homebrew required).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="${ROOT}/.tools"
VERSION="22.16.0"

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) ARCH="darwin-arm64" ;;
  Darwin-x86_64) ARCH="darwin-x64" ;;
  Linux-x86_64) ARCH="linux-x64" ;;
  Linux-aarch64) ARCH="linux-arm64" ;;
  *)
    echo "error: unsupported platform $(uname -s)-$(uname -m)" >&2
    exit 1
    ;;
esac

TARBALL="node-v${VERSION}-${ARCH}"
DEST="${TOOLS}/${TARBALL}"
MARKER="${DEST}/bin/node"

if [[ -x "$MARKER" ]]; then
  echo "Node already installed: $MARKER"
  "$MARKER" --version
  exit 0
fi

mkdir -p "$TOOLS"
TMP="${TOOLS}/${TARBALL}.tar.gz"
URL="https://nodejs.org/dist/v${VERSION}/${TARBALL}.tar.gz"
echo "Downloading $URL ..."
curl -fsSL "$URL" -o "$TMP"
tar -xzf "$TMP" -C "$TOOLS"
rm -f "$TMP"
echo "Installed: $MARKER"
"$MARKER" --version
"${DEST}/bin/npm" --version
