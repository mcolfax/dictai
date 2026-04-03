#!/bin/bash
# make_release.sh — Full release pipeline for Dictate
# Usage: bash make_release.sh <version>
# Example: bash make_release.sh 1.4.7

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; AMBER='\033[0;33m'; RED='\033[0;31m'; BOLD='\033[1m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅  $1${NC}"; }
info() { echo -e "${AMBER}→   $1${NC}"; }
err()  { echo -e "${RED}❌  $1${NC}"; exit 1; }
step() { echo -e "\n${BOLD}$1${NC}"; }

# ── Args ──────────────────────────────────────────────────────────────────────
VERSION="${1:-}"
[[ -n "$VERSION" ]] || err "Usage: bash make_release.sh <version>  (e.g. 1.4.7)"
TAG="v${VERSION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TAP_DIR="/tmp/homebrew-dictate"
DMG_PATH="$HOME/Desktop/Dictate.dmg"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  🎤  ${BOLD}Dictate — Release Pipeline${NC}"
echo "  Releasing ${TAG}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Preflight checks ──────────────────────────────────────────────────────────
step "1/9  Preflight checks"
command -v gh   &>/dev/null || err "'gh' CLI not found. Install with: brew install gh"
command -v jq   &>/dev/null || err "'jq' not found. Install with: brew install jq"
gh auth status  &>/dev/null || err "Not logged in to gh. Run: gh auth login"
[[ -f "$SCRIPT_DIR/make_dmg.sh" ]] || err "make_dmg.sh not found in $SCRIPT_DIR"
ok "Preflight passed"

# ── Collect release notes ─────────────────────────────────────────────────────
step "2/9  Release notes"
NOTES_FILE="$(mktemp /tmp/dictate_release_notes.XXXXXX.md)"
cat > "$NOTES_FILE" << EOF
## What's new in ${TAG}

<!-- Replace these lines with the actual release notes, then save and close -->
-

## Installation

\`\`\`bash
brew tap mcolfax/dictate
brew install --cask dictate
\`\`\`

## Updating

\`\`\`bash
brew upgrade --cask dictate
\`\`\`
EOF

info "Opening editor for release notes…"
"${EDITOR:-nano}" "$NOTES_FILE"

RELEASE_NOTES="$(cat "$NOTES_FILE")"
[[ -n "$RELEASE_NOTES" ]] || err "Release notes are empty — aborting."
ok "Release notes captured"

# ── Bump versions in source files ─────────────────────────────────────────────
step "3/9  Bump version numbers"

# version.txt
echo "$VERSION" > "$SCRIPT_DIR/version.txt"
ok "version.txt → $VERSION"

# app.py  (CURRENT_VERSION = "x.x.x")
sed -i '' "s/^CURRENT_VERSION = \".*\"/CURRENT_VERSION = \"${VERSION}\"/" "$SCRIPT_DIR/app.py"
ok "app.py CURRENT_VERSION → $VERSION"

# server.py  (APP_VERSION = "x.x.x")
sed -i '' "s/^APP_VERSION = \".*\"/APP_VERSION = \"${VERSION}\"/" "$SCRIPT_DIR/server.py"
ok "server.py APP_VERSION → $VERSION"

# ── Rebuild the app bundle so the DMG contains the new versions ───────────────
step "4/9  Rebuild Dictate.app"
info "Running install.sh to refresh bundle…"
bash "$SCRIPT_DIR/install.sh" 2>&1 | grep -E "(✅|→|❌)" || true
ok "App bundle updated"

# ── Build DMG ─────────────────────────────────────────────────────────────────
step "5/9  Build DMG"
info "Running make_dmg.sh…"
DMG_OUTPUT="$(bash "$SCRIPT_DIR/make_dmg.sh" 2>&1)"
echo "$DMG_OUTPUT"

# Extract SHA256 — make_dmg.sh prints "SHA256: <hash>"
SHA256="$(echo "$DMG_OUTPUT" | grep -oE 'SHA256: [a-f0-9]{64}' | awk '{print $2}')"
[[ -n "$SHA256" ]] || {
    # Fallback: compute directly if not printed
    [[ -f "$DMG_PATH" ]] || err "DMG not found at $DMG_PATH"
    SHA256="$(shasum -a 256 "$DMG_PATH" | awk '{print $1}')"
}
ok "DMG built — SHA256: $SHA256"

# ── Update dictate.rb in main repo ───────────────────────────────────────────
step "6/9  Update dictate.rb"
CASK_FILE="$SCRIPT_DIR/dictate.rb"
sed -i '' "s/version \".*\"/version \"${VERSION}\"/" "$CASK_FILE"
sed -i '' "s/sha256 \".*\"/sha256 \"${SHA256}\"/" "$CASK_FILE"
ok "dictate.rb → version $VERSION, sha256 $SHA256"

# ── Commit and push main repo ────────────────────────────────────────────────
step "7/9  Commit & push main repo"
cd "$SCRIPT_DIR"
git add version.txt app.py server.py dictate.rb
git commit -m "Release ${TAG}"
git push
ok "Main repo pushed"

# ── Create GitHub release + upload DMG ───────────────────────────────────────
step "8/9  Create GitHub release"
gh release create "$TAG" \
    --title "Dictate ${TAG}" \
    --notes "$RELEASE_NOTES" \
    "$DMG_PATH"
ok "GitHub release ${TAG} created with DMG"

# ── Sync tap repo ─────────────────────────────────────────────────────────────
step "9/9  Sync Homebrew tap"
if [[ -d "$TAP_DIR/.git" ]]; then
    info "Pulling latest tap repo…"
    git -C "$TAP_DIR" pull --quiet
else
    info "Cloning tap repo…"
    rm -rf "$TAP_DIR"
    gh repo clone mcolfax/homebrew-dictate "$TAP_DIR" -- --quiet
fi

mkdir -p "$TAP_DIR/Casks"
cp "$CASK_FILE" "$TAP_DIR/Casks/dictate.rb"

# Write the same release notes as a CHANGELOG entry in the tap
CHANGELOG="$TAP_DIR/CHANGELOG.md"
{
    echo "# ${TAG} — $(date +%Y-%m-%d)"
    echo ""
    echo "$RELEASE_NOTES"
    echo ""
    echo "---"
    echo ""
    [[ -f "$CHANGELOG" ]] && cat "$CHANGELOG"
} > "${CHANGELOG}.tmp" && mv "${CHANGELOG}.tmp" "$CHANGELOG"

git -C "$TAP_DIR" add Casks/dictate.rb CHANGELOG.md
git -C "$TAP_DIR" commit -m "Update to ${TAG}"
git -C "$TAP_DIR" push
ok "Tap repo updated and pushed"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "${GREEN}${BOLD}  🎉  Dictate ${TAG} released!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  GitHub release:"
echo "    https://github.com/mcolfax/dictate/releases/tag/${TAG}"
echo ""
echo "  Install / upgrade:"
echo "    brew tap mcolfax/dictate"
echo "    brew install --cask dictate"
echo "    brew upgrade --cask dictate"
echo ""
rm -f "$NOTES_FILE"
