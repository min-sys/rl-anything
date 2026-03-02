#!/bin/bash
set -euo pipefail

# rl-anything plugin installer / updater
# Usage:
#   curl -sL https://raw.githubusercontent.com/shohu/rl-anything/main/install.sh | bash
#   ./install.sh

MARKETPLACE_NAME="rl-anything"
PLUGIN_NAME="rl-anything"
PLUGIN_KEY="${PLUGIN_NAME}@${MARKETPLACE_NAME}"
REPO_URL="https://github.com/shohu/rl-anything.git"

CLAUDE_DIR="$HOME/.claude"
PLUGINS_DIR="$CLAUDE_DIR/plugins"
MARKETPLACES_DIR="$PLUGINS_DIR/marketplaces"
CACHE_DIR="$PLUGINS_DIR/cache"
INSTALLED_JSON="$PLUGINS_DIR/installed_plugins.json"

echo "=== rl-anything installer ==="

# 1. marketplace clone/update
MARKETPLACE_PATH="$MARKETPLACES_DIR/$MARKETPLACE_NAME"
mkdir -p "$MARKETPLACES_DIR"

if [ -d "$MARKETPLACE_PATH/.git" ]; then
    echo "[1/4] Updating marketplace..."
    git -C "$MARKETPLACE_PATH" pull --ff-only origin main 2>/dev/null || git -C "$MARKETPLACE_PATH" fetch origin main && git -C "$MARKETPLACE_PATH" reset --hard origin/main
else
    echo "[1/4] Cloning marketplace..."
    rm -rf "$MARKETPLACE_PATH"
    git clone "$REPO_URL" "$MARKETPLACE_PATH"
fi

# 2. Read version from plugin.json
VERSION=$(python3 -c "import json; print(json.load(open('$MARKETPLACE_PATH/.claude-plugin/plugin.json'))['version'])")
GIT_SHA=$(git -C "$MARKETPLACE_PATH" rev-parse HEAD)
echo "[2/4] Version: $VERSION (${GIT_SHA:0:12})"

# 3. Copy to cache
INSTALL_PATH="$CACHE_DIR/$MARKETPLACE_NAME/$PLUGIN_NAME/$VERSION"
echo "[3/4] Installing to cache..."
rm -rf "$INSTALL_PATH"
mkdir -p "$INSTALL_PATH"
# Copy all files except .git
rsync -a --exclude='.git' "$MARKETPLACE_PATH/" "$INSTALL_PATH/"

# 4. Update installed_plugins.json
echo "[4/4] Updating installed_plugins.json..."
NOW=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

python3 << PYEOF
import json
from pathlib import Path

installed_path = Path("$INSTALLED_JSON")

if installed_path.exists():
    data = json.loads(installed_path.read_text())
else:
    data = {"version": 2, "plugins": {}}

data["plugins"]["$PLUGIN_KEY"] = [{
    "scope": "user",
    "installPath": "$INSTALL_PATH",
    "version": "$VERSION",
    "installedAt": data.get("plugins", {}).get("$PLUGIN_KEY", [{}])[0].get("installedAt", "$NOW") if "$PLUGIN_KEY" in data.get("plugins", {}) else "$NOW",
    "lastUpdated": "$NOW",
    "gitCommitSha": "$GIT_SHA",
}]

installed_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
PYEOF

echo ""
echo "Done! rl-anything $VERSION installed (scope: user)"
echo "Restart Claude Code to activate."
