#!/usr/bin/env bash
# Generate a minimal placeholder .icns for electron-builder (macOS).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/clients/termit-desktop/build"
ICONSET="${OUT}/icon.iconset"
ICNS="${OUT}/icon.icns"

mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" /System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns \
    --out "${ICONSET}/icon_${size}x${size}.png" >/dev/null 2>&1 || {
    python3 - <<PY
from pathlib import Path
import struct
import zlib

size = ${size}
path = Path("${ICONSET}/icon_${size}x${size}.png")

def png_chunk(tag: bytes, data: bytes) -> bytes:
    chunk = tag + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

raw = b"".join(
    b"\\x00" + bytes([row * 32 % 256]) * size
    for row in range(size)
)
png = b"\\x89PNG\\r\\n\\x1a\\n"
png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
png += png_chunk(b"IDAT", zlib.compress(raw, 9))
png += png_chunk(b"IEND", b"")
path.write_bytes(png)
PY
  }
  double=$((size * 2))
  cp "${ICONSET}/icon_${size}x${size}.png" "${ICONSET}/icon_${double}x${double}.png" 2>/dev/null || true
done

if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "$ICONSET" -o "$ICNS"
  echo "Created $ICNS"
else
  echo "iconutil not found — skip .icns generation" >&2
fi
