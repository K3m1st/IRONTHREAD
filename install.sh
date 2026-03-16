#!/bin/bash
# ============================================================
# install.sh — One-time setup for Adversary Agent Architecture
# Run once after cloning the repo. Never again.
# ============================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTB_BASE=~/Desktop/HTB
BOXES_DIR=$HTB_BASE/boxes
TEMPLATES_DIR=$REPO_DIR/templates

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Adversary Agent Architecture — One-Time Setup"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── Step 1 — Check Claude Code ───────────────────────────────
echo "[1/5] Checking Claude Code..."
if ! command -v claude &> /dev/null; then
    echo "  [!] Claude Code not found."
    echo "  Install it with: npm install -g @anthropic-ai/claude-code"
    echo "  Then re-run this script."
    exit 1
fi
echo "  [✓] Claude Code found: $(claude --version 2>/dev/null || echo 'installed')"

# ── Step 2 — Check API key ───────────────────────────────────
echo "[2/5] Checking Anthropic API key..."
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  [!] ANTHROPIC_API_KEY not set."
    echo "  Add this to your ~/.bashrc or ~/.zshrc:"
    echo "    export ANTHROPIC_API_KEY=your_key_here"
    echo "  Then run: source ~/.bashrc"
    echo "  Then re-run this script."
    exit 1
fi
echo "  [✓] API key found."

# ── Step 3 — Verify templates ────────────────────────────────
echo "[3/5] Verifying template files..."

REQUIRED_FILES=(
    "templates/scout/CLAUDE.md"
    "templates/scout/SCOUT_SYSTEM_PROMPT.md"
    "templates/scout/SCOUT_REPORT_TEMPLATE.md"
    "templates/scout/SCOUT_REPORT_SCHEMA.json"
    "templates/planner/CLAUDE.md"
    "templates/planner/PLANNER_SYSTEM_PROMPT.md"
    "templates/webdig/CLAUDE.md"
    "templates/webdig/WEBDIG_SYSTEM_PROMPT.md"
    "templates/elliot/CLAUDE.md"
    "templates/elliot/ELLIOT_SYSTEM_PROMPT.md"
    "schemas/DEPLOYMENT_WEBDIG_SCHEMA.json"
    "schemas/HANDOFF_SCHEMA.json"
    "schemas/WEBDIG_FINDINGS_SCHEMA.json"
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
    echo "  Some template files are missing from the repo."
    echo "  Check your repo is fully cloned: git pull"
    exit 1
fi
echo "  [✓] All template files present."

# ── Step 4 — Create boxes directory ──────────────────────────
echo "[4/5] Setting up boxes directory..."
mkdir -p "$BOXES_DIR"
echo "  [✓] Boxes directory: $BOXES_DIR"

# ── Step 5 — Add new_box.sh to PATH ──────────────────────────
echo "[5/5] Adding new_box.sh to PATH..."

NEW_BOX_SCRIPT=$REPO_DIR/new_box.sh
chmod +x "$NEW_BOX_SCRIPT"
chmod +x "$REPO_DIR/install.sh"
chmod +x "$REPO_DIR/scripts/publish_obsidian_note.sh" 2>/dev/null || true
chmod +x "$REPO_DIR/scripts/validate_phase_artifacts.sh" 2>/dev/null || true

# Detect shell and update the right rc file
SHELL_RC=""
if [ -f ~/.zshrc ]; then
    SHELL_RC=~/.zshrc
elif [ -f ~/.bashrc ]; then
    SHELL_RC=~/.bashrc
fi

ALIAS_LINE="alias new_box='$NEW_BOX_SCRIPT'"

if [ -n "$SHELL_RC" ]; then
    if ! grep -q "adversary-agents/new_box.sh" "$SHELL_RC" 2>/dev/null; then
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
