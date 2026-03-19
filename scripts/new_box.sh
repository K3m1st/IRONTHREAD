#!/bin/bash
# ============================================================
# new_box.sh — Spin up a new HTB operation in one command
# Usage: new_box BOXNAME TARGET_IP
# Example: new_box Monitored 10.10.11.248
# ============================================================

set -e

BOX_NAME=$1
TARGET_IP=$2

if [ -z "$BOX_NAME" ] || [ -z "$TARGET_IP" ]; then
    echo "Usage: new_box BOXNAME TARGET_IP"
    echo "Example: new_box Monitored 10.10.11.248"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BOXES_DIR=$REPO_DIR/boxes
BOX_DIR=$BOXES_DIR/$BOX_NAME
TEMPLATES_DIR=$REPO_DIR/templates

# ── Guard ────────────────────────────────────────────────────
if [ -d "$BOX_DIR" ]; then
    echo "[!] $BOX_DIR already exists. Aborting."
    exit 1
fi

echo ""
echo "[*] Spinning up operation: $BOX_NAME ($TARGET_IP)"

# ── Build directory tree ─────────────────────────────────────
mkdir -p "$BOX_DIR/oracle"
mkdir -p "$BOX_DIR/elliot"
mkdir -p "$BOX_DIR/shared/notes"
mkdir -p "$BOX_DIR/shared/schemas"
mkdir -p "$BOX_DIR/shared/raw"

# ── Deploy agent files ───────────────────────────────────────
# Oracle
cp "$TEMPLATES_DIR/oracle/CLAUDE.md"                  "$BOX_DIR/oracle/CLAUDE.md"
cp "$TEMPLATES_DIR/oracle/ORACLE_SYSTEM_PROMPT.md"    "$BOX_DIR/oracle/ORACLE_SYSTEM_PROMPT.md"

# Elliot
cp "$TEMPLATES_DIR/elliot/CLAUDE.md"                  "$BOX_DIR/elliot/CLAUDE.md"
cp "$TEMPLATES_DIR/elliot/ELLIOT_SYSTEM_PROMPT.md"    "$BOX_DIR/elliot/ELLIOT_SYSTEM_PROMPT.md"

# Shared schemas
cp "$REPO_DIR/schemas/HANDOFF_SCHEMA.json"            "$BOX_DIR/shared/schemas/HANDOFF_SCHEMA.json"
cp "$REPO_DIR/schemas/SOVA_REPORT_SCHEMA.json"        "$BOX_DIR/shared/schemas/SOVA_REPORT_SCHEMA.json"
cp "$REPO_DIR/schemas/WEBDIG_FINDINGS_SCHEMA.json"    "$BOX_DIR/shared/schemas/WEBDIG_FINDINGS_SCHEMA.json"
cp "$REPO_DIR/schemas/NOIRE_FINDINGS_SCHEMA.json"     "$BOX_DIR/shared/schemas/NOIRE_FINDINGS_SCHEMA.json"
cp "$REPO_DIR/schemas/BASE_FINDINGS_SCHEMA.json"     "$BOX_DIR/shared/schemas/BASE_FINDINGS_SCHEMA.json"

# ── Ensure MCP servers configured at repo root ─────────────────
# .mcp.json must live at the git root — Claude Code only reads it there.
# This is idempotent — same config for all boxes.
if [ ! -f "$REPO_DIR/.mcp.json" ]; then
    cat > "$REPO_DIR/.mcp.json" << MCPEOF
{
  "mcpServers": {
    "sova-mcp": {
      "command": "python3",
      "args": ["$REPO_DIR/mcp/sova/server.py"]
    },
    "webdig-mcp": {
      "command": "python3",
      "args": ["$REPO_DIR/mcp/webdig/server.py"]
    },
    "noire-mcp": {
      "command": "python3",
      "args": ["$REPO_DIR/mcp/noire/server.py"]
    }
  }
}
MCPEOF
    echo "[+] MCP servers configured at $REPO_DIR/.mcp.json"
else
    echo "[+] MCP servers already configured."
fi

# ── Write operation metadata ─────────────────────────────────
cat > "$BOX_DIR/shared/target.txt" << EOF
BOX_NAME=$BOX_NAME
TARGET_IP=$TARGET_IP
EOF

cat > "$BOX_DIR/shared/operation.md" << EOF
# Operation: $BOX_NAME
> Created: $(date)
> Target IP: $TARGET_IP
> Status: RECON

## Phase Tracking
| Phase | Status | Started | Completed |
|-------|--------|---------|-----------|
| 1. Reconnaissance | PENDING | — | — |
| 2. Analysis & CVE Research | PENDING | — | — |
| 3. Web Enumeration | PENDING | — | — |
| 4. Exploitation (initial) | PENDING | — | — |
| 5. Post-Access Investigation | PENDING | — | — |
| 6. Privilege Escalation | PENDING | — | — |

## Agent Status
| Agent | Status | Last Deployment | Turns Used |
|-------|--------|-----------------|------------|
| ORACLE | PENDING | — | — |
| ELLIOT | PENDING | — | — |

## Notes

EOF

cat > "$BOX_DIR/shared/notes/important_notes.md" << EOF
# Important Notes — $BOX_NAME
> Created: $(date)
> Target IP: $TARGET_IP

Use this file for high-signal notes worth keeping beyond the immediate session:
- key architectural decisions
- attack-path pivots
- unusual findings
- research observations worth carrying into future boxes
- capstone-relevant lessons
EOF

# ── Done ─────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Operation ready: $BOX_NAME"
echo "  Target: $TARGET_IP"
echo "  Location: $BOX_DIR"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  Step 1 — Run Oracle (recon + analysis + enumeration):"
echo "    cd $BOX_DIR/oracle && claude"
echo ""
echo "  Step 2 — When Oracle writes handoff.json, run Elliot:"
echo "    cd $BOX_DIR/elliot && claude"
echo ""
echo "  Flow: Oracle → Elliot → Oracle → Elliot (as needed)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
