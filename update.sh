#!/bin/bash
# update.sh — Downloaded and run by Dictate.app when user clicks Update
# Args: $1 = APP_DATA_DIR, $2 = APP_RESOURCES (inside .app bundle)

APP_DATA_DIR="${1:-$HOME/.dictate}"
APP_RESOURCES="${2:-/Applications/Dictate.app/Contents/Resources}"
GITHUB_RAW="https://raw.githubusercontent.com/mcolfax/dictate/main"

echo "⏳ Updating Dictate…"
sleep 1  # Let old process exit

# Download updated Python files into the bundle
curl -fsSL "$GITHUB_RAW/server.py"     -o "$APP_RESOURCES/server.py"
curl -fsSL "$GITHUB_RAW/app.py"        -o "$APP_RESOURCES/app.py"
curl -fsSL "$GITHUB_RAW/make_icons.py" -o "$APP_RESOURCES/make_icons.py"

# Regenerate icons in case they changed
"$APP_DATA_DIR/venv/bin/python3" "$APP_RESOURCES/make_icons.py" --output "$APP_RESOURCES"

echo "✅ Update complete — restarting Dictate"
sleep 1
open /Applications/Dictate.app
