#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="TermitShell.app"
APP_DIR="$ROOT/clients/termit-shell/release/$APP_NAME"
CONTENTS_DIR="$APP_DIR/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"
INFO_PLIST="$CONTENTS_DIR/Info.plist"
ICONSET_DIR="$ROOT/clients/termit-shell/build/icon.iconset"
ICON_PATH="$ROOT/clients/termit-shell/build/TermitShell.icns"
ENTITLEMENTS_PATH="$ROOT/clients/termit-shell/build/entitlements.plist"
VERSION="$(cat "$ROOT/VERSION" 2>/dev/null || echo "0.1.0")"

cd "$ROOT/clients/termit-client"
npm install
npm run build

cd "$ROOT/clients/termit-desktop"
npm install
npx vite build

cd "$ROOT/clients/termit-shell"
swift build -c release

rm -rf "$APP_DIR"
mkdir -p "$MACOS_DIR" "$RESOURCES_DIR/renderer" "$RESOURCES_DIR/docs"
mkdir -p "$(dirname "$ICONSET_DIR")"

cp ".build/release/termit-shell" "$MACOS_DIR/termit-shell"
chmod +x "$MACOS_DIR/termit-shell"
cp -R "$ROOT/clients/termit-desktop/dist/." "$RESOURCES_DIR/renderer/"
cp -R "$ROOT/clients/termit-desktop/docs/pdf" "$RESOURCES_DIR/docs/"

rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"
for size in 16 32 128 256 512; do
  sips -z "$size" "$size" /System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns \
    --out "${ICONSET_DIR}/icon_${size}x${size}.png" >/dev/null 2>&1 || {
    python3 - <<PY
from pathlib import Path
import struct
import zlib

size = ${size}
path = Path("${ICONSET_DIR}/icon_${size}x${size}.png")

def png_chunk(tag: bytes, data: bytes) -> bytes:
    chunk = tag + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk) & 0xFFFFFFFF)

raw = b"".join(
    b"\\x00" + bytes([(row * 23) % 256, (row * 47) % 256, (row * 67) % 256]) * size
    for row in range(size)
)
png = b"\\x89PNG\\r\\n\\x1a\\n"
png += png_chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
png += png_chunk(b"IDAT", zlib.compress(raw, 9))
png += png_chunk(b"IEND", b"")
path.write_bytes(png)
PY
  }
  cp "${ICONSET_DIR}/icon_${size}x${size}.png" "${ICONSET_DIR}/icon_$((size * 2))x$((size * 2)).png"
done
if command -v iconutil >/dev/null 2>&1; then
  iconutil -c icns "$ICONSET_DIR" -o "$ICON_PATH"
else
  echo "iconutil not found; skipping .icns generation" >&2
  ICON_PATH=""
fi
if [[ -n "$ICON_PATH" && -f "$ICON_PATH" ]]; then
  cp "$ICON_PATH" "$RESOURCES_DIR/TermitShell.icns"
fi

cat > "$INFO_PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>TermitShell</string>
  <key>CFBundleDisplayName</key>
  <string>Termit Shell</string>
  <key>CFBundleIdentifier</key>
  <string>dev.termit.shell</string>
  <key>CFBundleVersion</key>
  <string>${VERSION}</string>
  <key>CFBundleShortVersionString</key>
  <string>${VERSION}</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>termit-shell</string>
EOF

if [[ -n "$ICON_PATH" && -f "$ICON_PATH" ]]; then
  cat >> "$INFO_PLIST" <<'EOF'
  <key>CFBundleIconFile</key>
  <string>TermitShell</string>
EOF
fi

cat >> "$INFO_PLIST" <<'EOF'
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
  <key>NSSupportsAutomaticGraphicsSwitching</key>
  <true/>
  <key>NSPrincipalClass</key>
  <string>NSApplication</string>
</dict>
</plist>
EOF

if [[ -n "${TERMIT_CODESIGN_IDENTITY:-}" ]]; then
  cat > "$ENTITLEMENTS_PATH" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>com.apple.security.cs.allow-jit</key>
  <true/>
  <key>com.apple.security.network.client</key>
  <true/>
</dict>
</plist>
EOF
  codesign --force --deep --options runtime --entitlements "$ENTITLEMENTS_PATH" \
    --sign "$TERMIT_CODESIGN_IDENTITY" "$APP_DIR"
  echo "Codesign complete with identity: $TERMIT_CODESIGN_IDENTITY"
fi

if [[ -n "${TERMIT_NOTARY_PROFILE:-}" ]]; then
  xcrun notarytool submit "$APP_DIR" --keychain-profile "$TERMIT_NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP_DIR"
  echo "Notarization complete with profile: $TERMIT_NOTARY_PROFILE"
fi

echo "Termit shell app bundle created:"
echo "$APP_DIR"
if [[ -n "${TERMIT_CODESIGN_IDENTITY:-}" ]]; then
  echo "Signed: yes (${TERMIT_CODESIGN_IDENTITY})"
else
  echo "Signed: no (set TERMIT_CODESIGN_IDENTITY for release builds)"
fi
if [[ -n "${TERMIT_NOTARY_PROFILE:-}" ]]; then
  echo "Notarized: yes (${TERMIT_NOTARY_PROFILE})"
else
  echo "Notarized: no (set TERMIT_NOTARY_PROFILE after codesign)"
fi
