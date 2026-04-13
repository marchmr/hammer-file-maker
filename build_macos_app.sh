#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
APP_NAME="Hammer File Maker"
DESKTOP_APP="$HOME/Desktop/$APP_NAME.app"

if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_DIR/requirements.txt"
python -m pip install pyinstaller

rm -rf "$PROJECT_DIR/build" "$PROJECT_DIR/dist" "$PROJECT_DIR/$APP_NAME.spec"

pyinstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --icon "$PROJECT_DIR/assets/hammer_file_maker.icns" \
  --add-data "$PROJECT_DIR/templates:templates" \
  --add-data "$PROJECT_DIR/static:static" \
  --add-data "$PROJECT_DIR/assets:assets" \
  "$PROJECT_DIR/desktop_app.py"

rm -rf "$DESKTOP_APP"
cp -R "$PROJECT_DIR/dist/$APP_NAME.app" "$DESKTOP_APP"
touch "$DESKTOP_APP"

echo "Fertig: $DESKTOP_APP"
