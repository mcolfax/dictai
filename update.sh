#!/bin/bash
# update.sh — sync git source → app bundle
# Run this after `git pull`, then relaunch Dictate from /Applications.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RESOURCES="/Applications/Dictate.app/Contents/Resources"

echo "→ Copying Python files into app bundle and ~/.dictate/..."
for f in app.py server.py settings_window.py overlay.py make_icons.py; do
    cp "$SCRIPT_DIR/$f" "$RESOURCES/$f"
    cp "$SCRIPT_DIR/$f" "$HOME/.dictate/$f"
done

echo "→ Regenerating icons..."
"$HOME/.dictate/venv/bin/python3" "$SCRIPT_DIR/make_icons.py" --outdir "$RESOURCES"
cp "$RESOURCES"/icon*.png "$HOME/.dictate/" 2>/dev/null

echo "→ Removing quarantine..."
xattr -dr com.apple.quarantine /Applications/Dictate.app 2>/dev/null || true

echo ""
echo "✅ Done. Relaunch Dictate from /Applications to apply changes."
