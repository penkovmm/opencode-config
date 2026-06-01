#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "==> Bootstrapping opencode from $SCRIPT_DIR"

# 1. System dependencies
echo "==> System deps: poppler"
brew list poppler >/dev/null 2>&1 || brew install poppler

# 2. Python dependencies
echo "==> Python deps"
python3 -m pip install --break-system-packages -r "$SCRIPT_DIR/requirements.txt"

# 3. Skills → ~/.claude/skills/
echo "==> Linking skills"
mkdir -p ~/.claude/skills
for skill in "$SCRIPT_DIR/skills/"*/; do
    name=$(basename "$skill")
    target="$HOME/.claude/skills/$name"
    rm -rf "$target" 2>/dev/null
    ln -sf "$skill" "$target"
    echo "  $name -> $target"
done

# 4. MCP config → ~/.config/opencode/
echo "==> Linking opencode config"
mkdir -p ~/.config/opencode
rm -f ~/.config/opencode/opencode.jsonc
ln -sf "$SCRIPT_DIR/opencode.jsonc" ~/.config/opencode/opencode.jsonc

# 5. Python scripts → ~/.config/opencode/scripts/
echo "==> Linking scripts"
mkdir -p ~/.config/opencode/scripts
for script in "$SCRIPT_DIR/scripts/"*.py; do
    name=$(basename "$script")
    target="$HOME/.config/opencode/scripts/$name"
    rm -f "$target" 2>/dev/null
    ln -sf "$script" "$target"
    echo "  $name -> $target"
done

# 6. Working dirs
echo "==> Creating working dirs"
mkdir -p ~/.config/opencode/cache/vision
mkdir -p ~/.config/opencode/generated

# 7. .env reminder
if [ ! -f ~/.config/opencode/.env ]; then
    echo "⚠️  Create ~/.config/opencode/.env with:"
    echo "   OPENROUTER_API_KEY=sk-or-v1-..."
    echo "   OPENAI_API_KEY=sk-proj-..."
    echo "   OPENAI_PROXY=http://user:pass@host:port"
fi

echo "==> Done. Run 'opencode' to start."
