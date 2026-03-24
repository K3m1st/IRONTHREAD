#!/bin/bash
# Launches an MCP server with the correct working directory.
# Usage: launch.sh <server_name>
# Example: launch.sh sova/server.py
#
# Resolves the repo root from this script's location so .mcp.json
# can use portable paths that work on any machine.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

exec python3 "$SCRIPT_DIR/$1"
