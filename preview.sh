#!/usr/bin/env bash
# Render the SVGs and screenshot them with headless Chrome, which uses the same
# engine as GitHub. macOS-only convenience script.
set -euo pipefail
cd "$(dirname "$0")"

PY=${PY:-.venv/bin/python}
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

"$PY" generate.py "$@"

for theme in dark_mode light_mode; do
  w=$(grep -o 'width="[0-9]*"' "$theme.svg" | head -1 | grep -o '[0-9]*')
  h=$(grep -o 'height="[0-9]*"' "$theme.svg" | head -1 | grep -o '[0-9]*')
  "$CHROME" --headless --disable-gpu --hide-scrollbars \
    --force-device-scale-factor=2 --window-size="$w,$h" \
    --screenshot="preview_$theme.png" "file://$PWD/$theme.svg" 2>/dev/null
  echo "wrote preview_$theme.png"
done
