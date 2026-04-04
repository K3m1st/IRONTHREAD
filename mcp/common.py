"""
common — Shared utilities for IRONTHREAD MCP servers.

Provides timestamp generation, file output, and subprocess execution
used by sova-mcp, webdig-mcp, and noire-mcp.
"""

import os
import subprocess
from datetime import datetime, timezone


def ts() -> str:
    """UTC timestamp for filenames."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def save_output(output_dir: str, filename: str, content: str) -> str:
    """Write content to output_dir/filename, creating dirs as needed. Returns path."""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, filename)
    with open(path, "w") as f:
        f.write(content)
    return path


def truncate_output(text: str, limit: int = 3000) -> str:
    """Truncate text for token-efficient responses, with indicator."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncated, {len(text)} total chars — see raw_output_file]"


def run_cmd(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    """Run a subprocess, return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
