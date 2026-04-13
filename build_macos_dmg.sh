#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Hammer File Maker.app"
VOL_NAME="Hammer File Maker"
OUT_DIR="$PROJECT_DIR/dist/installers"
DMG_PATH="$OUT_DIR/Hammer-File-Maker-macOS.dmg"
TMP_DIR="$(mktemp -d)"
STAGE_DIR="$TMP_DIR/dmg-root"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

mkdir -p "$OUT_DIR" "$STAGE_DIR"

if [ -d "$PROJECT_DIR/dist/$APP_NAME" ]; then
  SRC_APP="$PROJECT_DIR/dist/$APP_NAME"
elif [ -d "$HOME/Desktop/$APP_NAME" ]; then
  SRC_APP="$HOME/Desktop/$APP_NAME"
else
  echo "Fehler: '$APP_NAME' nicht gefunden."
  echo "Bitte zuerst ./build_macos_app.sh ausführen."
  exit 1
fi

cp -R "$SRC_APP" "$STAGE_DIR/$APP_NAME"
ln -s /Applications "$STAGE_DIR/Applications"

rm -f "$DMG_PATH"
hdiutil create \
  -volname "$VOL_NAME" \
  -srcfolder "$STAGE_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

echo "Fertig: $DMG_PATH"
