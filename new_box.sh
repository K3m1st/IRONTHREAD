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

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BOXES_DIR=~/Desktop/HTB/boxes
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
mkdir -p "$BOX_DIR/scout"
mkdir -p "$BOX_DIR/planner"
mkdir -p "$BOX_DIR/webdig"
mkdir -p "$BOX_DIR/elliot"
mkdir -p "$BOX_DIR/noire"
mkdir -p "$BOX_DIR/shared/notes"
mkdir -p "$BOX_DIR/shared/schemas"
mkdir -p "$BOX_DIR/shared/raw"

# ── Deploy agent files ───────────────────────────────────────
# Scout
cp "$TEMPLATES_DIR/scout/CLAUDE.md"                "$BOX_DIR/scout/CLAUDE.md"
cp "$TEMPLATES_DIR/scout/SCOUT_SYSTEM_PROMPT.md"   "$BOX_DIR/scout/SCOUT_SYSTEM_PROMPT.md"
cp "$TEMPLATES_DIR/scout/SCOUT_REPORT_TEMPLATE.md" "$BOX_DIR/scout/SCOUT_REPORT_TEMPLATE.md"
cp "$TEMPLATES_DIR/scout/SCOUT_REPORT_SCHEMA.json" "$BOX_DIR/scout/SCOUT_REPORT_SCHEMA.json"

# Planner
cp "$TEMPLATES_DIR/planner/CLAUDE.md"                  "$BOX_DIR/planner/CLAUDE.md"
cp "$TEMPLATES_DIR/planner/PLANNER_SYSTEM_PROMPT.md"   "$BOX_DIR/planner/PLANNER_SYSTEM_PROMPT.md"

# Webdig
cp "$TEMPLATES_DIR/webdig/CLAUDE.md"                   "$BOX_DIR/webdig/CLAUDE.md"
cp "$TEMPLATES_DIR/webdig/WEBDIG_SYSTEM_PROMPT.md"     "$BOX_DIR/webdig/WEBDIG_SYSTEM_PROMPT.md"

# Elliot
cp "$TEMPLATES_DIR/elliot/CLAUDE.md"                   "$BOX_DIR/elliot/CLAUDE.md"
cp "$TEMPLATES_DIR/elliot/ELLIOT_SYSTEM_PROMPT.md"     "$BOX_DIR/elliot/ELLIOT_SYSTEM_PROMPT.md"

# Noire
cp "$TEMPLATES_DIR/noire/CLAUDE.md"                    "$BOX_DIR/noire/CLAUDE.md"
cp "$TEMPLATES_DIR/noire/NOIRE_SYSTEM_PROMPT.md"       "$BOX_DIR/noire/NOIRE_SYSTEM_PROMPT.md"

# Shared schemas
cp "$REPO_DIR/schemas/DEPLOYMENT_WEBDIG_SCHEMA.json"   "$BOX_DIR/shared/schemas/DEPLOYMENT_WEBDIG_SCHEMA.json"
cp "$REPO_DIR/schemas/DEPLOYMENT_NOIRE_SCHEMA.json"    "$BOX_DIR/shared/schemas/DEPLOYMENT_NOIRE_SCHEMA.json"
cp "$REPO_DIR/schemas/HANDOFF_SCHEMA.json"             "$BOX_DIR/shared/schemas/HANDOFF_SCHEMA.json"
cp "$REPO_DIR/schemas/NOIRE_FINDINGS_SCHEMA.json"      "$BOX_DIR/shared/schemas/NOIRE_FINDINGS_SCHEMA.json"
cp "$REPO_DIR/schemas/WEBDIG_FINDINGS_SCHEMA.json"     "$BOX_DIR/shared/schemas/WEBDIG_FINDINGS_SCHEMA.json"

# ── Write operation metadata ─────────────────────────────────
cat > "$BOX_DIR/shared/target.txt" << EOF
BOX_NAME=$BOX_NAME
TARGET_IP=$TARGET_IP
EOF

cat > "$BOX_DIR/shared/operation.md" << EOF
# Operation: $BOX_NAME
> Created: $(date)
> Target IP: $TARGET_IP
> Status: ACTIVE

## Agent Status
| Agent | Status |
|-------|--------|
| SCOUT | PENDING |
| PLANNER | PENDING |
| WEBDIG | PENDING |
| ELLIOT | PENDING |
| NOIRE | PENDING |
| SMBREACH | PENDING |
| DNSMAP | PENDING |

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
echo "  Step 1 — Run Scout:"
echo "    cd $BOX_DIR/scout && claude"
echo ""
echo "  Step 2 — After Scout completes, run Planner:"
echo "    cd $BOX_DIR/planner && claude"
echo ""
echo "  Current primary path:"
echo "    Planner -> webdig -> Planner -> elliot -> noire -> Planner -> elliot (as needed)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
