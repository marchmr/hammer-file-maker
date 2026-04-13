#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
DESKTOP_LAUNCHER="$HOME/Desktop/Hammer File Maker.command"
DESKTOP_APP="$HOME/Desktop/Hammer File Maker.app"
APP_ICON="$PROJECT_DIR/assets/hammer_file_maker.icns"
PROJECT_LAUNCHER="$PROJECT_DIR/launch_hammer_file_maker.command"
APP_CONTENTS="$DESKTOP_APP/Contents"
APP_MACOS="$APP_CONTENTS/MacOS"
APP_RESOURCES="$APP_CONTENTS/Resources"

cat > "$DESKTOP_LAUNCHER" <<LAUNCHER
#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$PROJECT_DIR"

if [ ! -x "\$PROJECT_DIR/launch_hammer_file_maker.command" ]; then
  /bin/zsh "\$PROJECT_DIR/install_mac_setup.sh"
fi

/bin/zsh "\$PROJECT_DIR/launch_hammer_file_maker.command"
LAUNCHER

chmod +x "$DESKTOP_LAUNCHER"
echo "Desktop Launcher erstellt: $DESKTOP_LAUNCHER"

rm -rf "$DESKTOP_APP"
mkdir -p "$APP_MACOS" "$APP_RESOURCES"

cat > "$APP_CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>
  <string>Hammer File Maker</string>
  <key>CFBundleDisplayName</key>
  <string>Hammer File Maker</string>
  <key>CFBundleIdentifier</key>
  <string>de.hammerfilemaker.desktop</string>
  <key>CFBundleVersion</key>
  <string>1.0</string>
  <key>CFBundleShortVersionString</key>
  <string>1.0</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleExecutable</key>
  <string>HammerFileMaker</string>
  <key>LSMinimumSystemVersion</key>
  <string>11.0</string>
  <key>LSUIElement</key>
  <false/>
  <key>CFBundleIconFile</key>
  <string>applet</string>
</dict>
</plist>
PLIST

cat > "$APP_MACOS/HammerFileMaker" <<RUNNER
#!/bin/zsh
set -euo pipefail

DESKTOP_LAUNCHER="$DESKTOP_LAUNCHER"
PROJECT_LAUNCHER="$PROJECT_LAUNCHER"

if [ -x "\$PROJECT_LAUNCHER" ]; then
  /usr/bin/open -a Terminal "\$PROJECT_LAUNCHER" >>/tmp/hammer_file_maker.log 2>&1
else
  /bin/zsh "\$DESKTOP_LAUNCHER" >>/tmp/hammer_file_maker.log 2>&1
fi
exit 0
RUNNER
chmod +x "$APP_MACOS/HammerFileMaker"

if [ -f "$APP_ICON" ]; then
  cp "$APP_ICON" "$APP_RESOURCES/applet.icns"
fi

touch "$DESKTOP_APP"
echo "Desktop App erstellt: $DESKTOP_APP"
