#!/bin/bash

set -euo pipefail

DEFAULT_VAULT_PATH="$HOME/Desktop/AllSeeing/Agent Orchestration Idea"

if [ "$#" -lt 1 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 SOURCE_NOTE [VAULT_PATH] [VAULT_SUBDIR]"
    echo "Example: $0 shared/notes/important_notes.md \"$DEFAULT_VAULT_PATH\" IRONTHREAD/Boxes"
    exit 1
fi

SOURCE_NOTE="$1"
VAULT_PATH="${2:-$DEFAULT_VAULT_PATH}"
VAULT_PATH="${VAULT_PATH/#\~/$HOME}"
VAULT_SUBDIR="${3:-IRONTHREAD/Inbox}"

if [ ! -d "$VAULT_PATH" ]; then
    echo "[!] Vault path does not exist: $VAULT_PATH"
    exit 1
fi

if [ ! -f "$SOURCE_NOTE" ]; then
    echo "[!] Source note does not exist: $SOURCE_NOTE"
    exit 1
fi

DEST_DIR="$VAULT_PATH/$VAULT_SUBDIR"
mkdir -p "$DEST_DIR"

DEST_FILE="$DEST_DIR/$(basename "$SOURCE_NOTE")"
cp "$SOURCE_NOTE" "$DEST_FILE"

echo "[+] Note published to: $DEST_FILE"
