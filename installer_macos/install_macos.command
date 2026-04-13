#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="Hammer File Maker.app"
SRC_APP="$SCRIPT_DIR/$APP_NAME"
DST_APP="/Applications/$APP_NAME"

if [ ! -d "$SRC_APP" ]; then
  echo "Fehler: '$APP_NAME' fehlt im gleichen Ordner wie dieses Script."
  echo "Lege die .app neben 'install_macos.command' und starte erneut."
  exit 1
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew wird installiert..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

if ! command -v brew >/dev/null 2>&1; then
  echo "Fehler: Homebrew konnte nicht installiert werden."
  exit 1
fi

echo "Installiere Abhängigkeiten (ffmpeg, LibreOffice, Inkscape)..."
brew install ffmpeg
brew install --cask libreoffice
brew install --cask inkscape

echo "Installiere App nach /Applications..."
rm -rf "$DST_APP"
cp -R "$SRC_APP" "$DST_APP"
touch "$DST_APP"

echo "Installation abgeschlossen: $DST_APP"
echo "Alle Abhängigkeiten wurden installiert."
echo "Hinweis: Updates manuell ausführen mit:"
echo "brew update && brew upgrade ffmpeg && brew upgrade --cask libreoffice inkscape"
