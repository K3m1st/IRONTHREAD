#!/bin/bash

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 PHASE BOX_SHARED_DIR"
    echo "Example: $0 webdig ~/Desktop/HTB/boxes/Monitored/shared"
    exit 1
fi

PHASE="$1"
SHARED_DIR="${2/#\~/$HOME}"

if [ ! -d "$SHARED_DIR" ]; then
    echo "[!] Shared directory not found: $SHARED_DIR"
    exit 1
fi

validate_webdig() {
    local deploy_json="$SHARED_DIR/deployment_webdig.json"
    local findings_json="$SHARED_DIR/webdig_findings.json"

    [ -f "$deploy_json" ] || { echo "[!] Missing: $deploy_json"; exit 1; }
    [ -f "$findings_json" ] || { echo "[!] Missing: $findings_json"; exit 1; }

    jq -e '
        .authorized == true and
        (.objective | type == "string" and length > 0) and
        (.ports | type == "array" and length > 0) and
        (.priority_paths | type == "array" and length > 0) and
        (.allowed_actions | type == "array" and length > 0) and
        (.disallowed_actions | type == "array" and length > 0)
    ' "$deploy_json" > /dev/null

    jq -e '
        (.objective.statement | type == "string" and length > 0) and
        (.objective.objective_completed | type == "boolean") and
        (.planner_flags | type == "array") and
        (.evidence_refs | type == "array") and
        (.tools_executed | type == "array")
    ' "$findings_json" > /dev/null

    echo "[+] WEBDIG artifacts validated."
}

validate_elliot() {
    local handoff_json="$SHARED_DIR/handoff.json"

    [ -f "$handoff_json" ] || { echo "[!] Missing: $handoff_json"; exit 1; }

    jq -e '
        .elliot_authorized == true and
        (.scope.objective | type == "string" and length > 0) and
        (.scope.in_scope | type == "array" and length > 0) and
        (.scope.stop_conditions | type == "array" and length > 0) and
        (.scope.max_attempts_per_path | type == "number") and
        (.primary_path | type == "string" and length > 0) and
        (.backup_path | type == "string" and length > 0)
    ' "$handoff_json" > /dev/null

    echo "[+] ELLIOT handoff validated."
}

case "$PHASE" in
    webdig)
        validate_webdig
        ;;
    elliot)
        validate_elliot
        ;;
    *)
        echo "[!] Unknown phase: $PHASE"
        echo "    Supported: webdig, elliot"
        exit 1
        ;;
esac
