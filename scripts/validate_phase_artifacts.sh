#!/bin/bash

set -euo pipefail

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 PHASE BOX_SHARED_DIR"
    echo "Example: $0 webdig ~/Desktop/HTB/boxes/Monitored/shared"
    echo "Phases: recon, webdig, elliot, noire"
    exit 1
fi

PHASE="$1"
SHARED_DIR="${2/#\~/$HOME}"

if [ ! -d "$SHARED_DIR" ]; then
    echo "[!] Shared directory not found: $SHARED_DIR"
    exit 1
fi

validate_recon() {
    local report_json="$SHARED_DIR/scouting_report.json"

    [ -f "$report_json" ] || { echo "[!] Missing: $report_json"; exit 1; }

    jq -e '
        (.meta.status == "COMPLETE") and
        (.meta.agent | type == "string") and
        (.ports | type == "array" and length > 0) and
        (.oracle_recommendations | type == "array" and length > 0) and
        (.tools_executed | type == "array" and length > 0)
    ' "$report_json" > /dev/null

    echo "[+] Recon artifacts validated."
}

validate_webdig() {
    local findings_json="$SHARED_DIR/webdig_findings.json"

    [ -f "$findings_json" ] || { echo "[!] Missing: $findings_json"; exit 1; }

    jq -e '
        (.objective.statement | type == "string" and length > 0) and
        (.objective.objective_completed | type == "boolean") and
        (.oracle_flags | type == "array") and
        (.evidence_refs | type == "array") and
        (.tools_executed | type == "array")
    ' "$findings_json" > /dev/null

    echo "[+] WEBDIG findings validated."
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

validate_noire() {
    local findings_json="$SHARED_DIR/noire_findings.json"

    [ -f "$findings_json" ] || { echo "[!] Missing: $findings_json"; exit 1; }

    jq -e '
        (.objective.statement | type == "string" and length > 0) and
        (.current_access.user | type == "string" and length > 0) and
        (.privesc_leads | type == "array") and
        (.oracle_flags | type == "array") and
        (.tools_executed | type == "array")
    ' "$findings_json" > /dev/null

    echo "[+] NOIRE findings validated."
}

case "$PHASE" in
    recon)
        validate_recon
        ;;
    webdig)
        validate_webdig
        ;;
    elliot)
        validate_elliot
        ;;
    noire)
        validate_noire
        ;;
    *)
        echo "[!] Unknown phase: $PHASE"
        echo "    Supported: recon, webdig, elliot, noire"
        exit 1
        ;;
esac
