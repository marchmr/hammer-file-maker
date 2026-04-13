#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python nicht gefunden. Bitte Python 3 installieren."
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r "$PROJECT_DIR/requirements.txt"

PROJECT_LAUNCHER="$PROJECT_DIR/launch_hammer_file_maker.command"
cat > "$PROJECT_LAUNCHER" <<'LAUNCHER'
#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
source "$PROJECT_DIR/.venv/bin/activate"
python "$PROJECT_DIR/desktop_app.py"
LAUNCHER
chmod +x "$PROJECT_LAUNCHER"

echo "Setup fertig: $PROJECT_LAUNCHER"
