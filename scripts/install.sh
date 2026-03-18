#!/bin/bash
# ============================================================
# install.sh — One-time setup for Adversary Agent Architecture
# Run once after cloning the repo. Never again.
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HTB_BASE=~/Desktop/HTB
BOXES_DIR=$HTB_BASE/boxes
TEMPLATES_DIR=$REPO_DIR/templates

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Adversary Agent Architecture — One-Time Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1 — Check Claude Code ───────────────────────────────
echo "[1/6] Checking Claude Code..."
if ! command -v claude &> /dev/null; then
    echo "  [!] Claude Code not found."
    echo "  Install it with: npm install -g @anthropic-ai/claude-code"
    echo "  Then re-run this script."
    exit 1
fi
echo "  [✓] Claude Code found: $(claude --version 2>/dev/null || echo 'installed')"

# ── Step 2 — Check API key ───────────────────────────────────
echo "[2/6] Checking Anthropic API key..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  [!] ANTHROPIC_API_KEY not set."
    echo "  Add this to your ~/.bashrc or ~/.zshrc:"
    echo "    export ANTHROPIC_API_KEY=your_key_here"
    echo "  Then run: source ~/.bashrc"
    echo "  Then re-run this script."
    exit 1
fi
echo "  [✓] API key found."

# ── Step 3 — Verify templates and MCP servers ─────────────────
echo "[3/6] Verifying template and MCP files..."

REQUIRED_FILES=(
    "templates/oracle/CLAUDE.md"
    "templates/oracle/ORACLE_SYSTEM_PROMPT.md"
    "templates/elliot/CLAUDE.md"
    "templates/elliot/ELLIOT_SYSTEM_PROMPT.md"
    "schemas/HANDOFF_SCHEMA.json"
    "schemas/SOVA_REPORT_SCHEMA.json"
    "schemas/NOIRE_FINDINGS_SCHEMA.json"
    "schemas/WEBDIG_FINDINGS_SCHEMA.json"
    "mcp/sova/server.py"
    "mcp/webdig/server.py"
    "mcp/noire/server.py"
    "mcp/requirements.txt"
)

MISSING=0
for f in "${REQUIRED_FILES[@]}"; do
    if [ ! -f "$REPO_DIR/$f" ]; then
        echo "  [!] Missing: $f"
        MISSING=1
    fi
done

if [ $MISSING -eq 1 ]; then
    echo ""
    echo "  Some required files are missing from the repo."
    echo "  Check your repo is fully cloned: git pull"
    exit 1
fi
echo "  [✓] All required files present."

# ── Step 4 — Install MCP dependencies ─────────────────────────
echo "[4/6] Installing MCP Python dependencies..."
if pip3 install -q -r "$REPO_DIR/mcp/requirements.txt" 2>/dev/null; then
    echo "  [✓] MCP dependencies installed."
else
    echo "  [!] Failed to install MCP dependencies."
    echo "  Run manually: pip3 install -r $REPO_DIR/mcp/requirements.txt"
fi

# ── Step 5 — Create boxes directory ──────────────────────────
echo "[5/6] Setting up boxes directory..."
mkdir -p "$BOXES_DIR"
echo "  [✓] Boxes directory: $BOXES_DIR"

# ── Step 6 — Add new_box.sh to PATH ──────────────────────────
echo "[6/6] Adding new_box.sh to PATH..."

NEW_BOX_SCRIPT=$REPO_DIR/scripts/new_box.sh
chmod +x "$NEW_BOX_SCRIPT"
chmod +x "$SCRIPT_DIR/install.sh"
chmod +x "$SCRIPT_DIR/publish_obsidian_note.sh" 2>/dev/null || true
chmod +x "$SCRIPT_DIR/validate_phase_artifacts.sh" 2>/dev/null || true

# Detect shell and update the right rc file
SHELL_RC=""
if [ -f ~/.zshrc ]; then
    SHELL_RC=~/.zshrc
elif [ -f ~/.bashrc ]; then
    SHELL_RC=~/.bashrc
fi

ALIAS_LINE="alias new_box='$NEW_BOX_SCRIPT'"

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "alias new_box=" "$SHELL_RC" 2>/dev/null; then
        echo "" >> "$SHELL_RC"
        echo "# Adversary Agent Architecture" >> "$SHELL_RC"
        echo "$ALIAS_LINE" >> "$SHELL_RC"
        echo "  [✓] Added new_box alias to $SHELL_RC"
        echo "  [!] Run: source $SHELL_RC to activate"
    else
        echo "  [✓] new_box alias already in $SHELL_RC"
    fi
fi

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Setup complete."
echo ""
echo "  Reload your shell:"
echo "    source $SHELL_RC"
echo ""
echo "  Then for every new box:"
echo "    new_box BOXNAME 10.10.10.10"
echo ""
echo "  Boxes live at: $BOXES_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
