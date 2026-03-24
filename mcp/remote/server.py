#!/usr/bin/env python3
"""Remote — Persistent SSH session pool for IRONTHREAD operations.

Maintains long-lived Paramiko connections keyed by (host, user).
Agents call remote_exec instead of spawning individual SSH processes.
Connections auto-reconnect on failure. All commands are logged to
memoria if available.
"""

import asyncio
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone

import paramiko
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("remote-mcp")

# ---------------------------------------------------------------------------
# Connection pool
# ---------------------------------------------------------------------------

_pool: dict[str, paramiko.SSHClient] = {}  # key: "user@host"
_pool_lock = threading.Lock()


def _pool_key(host: str, user: str) -> str:
    return f"{user}@{host}"


def _get_connection(
    host: str,
    user: str,
    key_path: str | None = None,
    password: str | None = None,
    port: int = 22,
) -> paramiko.SSHClient:
    """Get or create a persistent SSH connection."""
    key = _pool_key(host, user)

    with _pool_lock:
        client = _pool.get(key)

        # Check if existing connection is still alive
        if client is not None:
            transport = client.get_transport()
            if transport is not None and transport.is_active():
                try:
                    transport.send_ignore()
                    return client
                except Exception:
                    pass
            # Dead connection — remove and reconnect
            try:
                client.close()
            except Exception:
                pass
            del _pool[key]

        # Create new connection
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        connect_kwargs = {
            "hostname": host,
            "port": port,
            "username": user,
            "timeout": 10,
            "banner_timeout": 10,
        }

        if key_path:
            connect_kwargs["key_filename"] = key_path
        elif password:
            connect_kwargs["password"] = password
        else:
            # Try default key locations
            for default_key in [
                os.path.expanduser("~/.ssh/id_rsa"),
                os.path.expanduser("~/.ssh/id_ed25519"),
            ]:
                if os.path.exists(default_key):
                    connect_kwargs["key_filename"] = default_key
                    break

        client.connect(**connect_kwargs)
        _pool[key] = client
        return client


def _close_connection(host: str, user: str) -> bool:
    """Close a specific connection."""
    key = _pool_key(host, user)
    with _pool_lock:
        client = _pool.pop(key, None)
        if client:
            try:
                client.close()
            except Exception:
                pass
            return True
    return False


def _exec_command(
    host: str,
    user: str,
    command: str,
    key_path: str | None = None,
    password: str | None = None,
    port: int = 22,
    timeout: int = 30,
) -> tuple[int, str, str]:
    """Execute a command over persistent SSH, return (exit_code, stdout, stderr)."""
    try:
        client = _get_connection(host, user, key_path, password, port)
        stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
        exit_code = stdout.channel.recv_exit_status()
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return exit_code, out, err
    except paramiko.SSHException as e:
        # Connection might be stale — close and retry once
        _close_connection(host, user)
        try:
            client = _get_connection(host, user, key_path, password, port)
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            exit_code = stdout.channel.recv_exit_status()
            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            return exit_code, out, err
        except Exception as e2:
            return -1, "", f"SSH retry failed: {e2}"
    except Exception as e:
        return -1, "", f"SSH error: {e}"


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


# ---------------------------------------------------------------------------
# Memoria integration (optional — logs commands if DB exists)
# ---------------------------------------------------------------------------

def _log_to_memoria(host: str, agent: str, command: str, result: str, exit_code: int):
    """Best-effort log to memoria DB if it exists."""
    db_path = os.environ.get(
        "MEMORIA_DB",
        os.path.join(os.getcwd(), "..", "shared", "memoria.db"),
    )
    if not os.path.exists(db_path):
        return
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        # Find target_id by IP
        row = conn.execute("SELECT id FROM targets WHERE ip = ?", (host,)).fetchone()
        target_id = row[0] if row else None
        # Truncate result for storage (keep first 2000 chars)
        truncated = result[:2000] + "..." if len(result) > 2000 else result
        conn.execute(
            "INSERT INTO actions (target_id, agent, action, detail, result, phase, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target_id, agent, f"remote_exec: {command[:100]}", command, truncated, "remote", _now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Best effort — don't break the tool if memoria is unavailable


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="remote_exec",
            description=(
                "Execute a command on a remote target over a persistent SSH "
                "connection. Reuses existing connections — no per-command "
                "handshake overhead. Auto-reconnects on failure."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP or hostname"},
                    "command": {"type": "string", "description": "Command to execute"},
                    "user": {"type": "string", "description": "SSH username", "default": "root"},
                    "key_path": {"type": "string", "description": "Path to SSH private key (optional)"},
                    "password": {"type": "string", "description": "SSH password (optional, prefer key)"},
                    "port": {"type": "integer", "description": "SSH port", "default": 22},
                    "timeout": {"type": "integer", "description": "Command timeout in seconds", "default": 30},
                    "agent": {
                        "type": "string",
                        "description": "Which agent is calling (for memoria logging)",
                        "enum": ["ORACLE", "ELLIOT", "NOIRE"],
                    },
                },
                "required": ["host", "command"],
            },
        ),
        Tool(
            name="remote_upload",
            description=(
                "Upload a file to a remote target over persistent SSH (SFTP). "
                "Use for deploying scripts, payloads, or keys."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP or hostname"},
                    "local_path": {"type": "string", "description": "Local file path to upload"},
                    "remote_path": {"type": "string", "description": "Destination path on target"},
                    "user": {"type": "string", "default": "root"},
                    "key_path": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 22},
                    "mode": {"type": "integer", "description": "File permissions (octal as int, e.g. 755)", "default": 644},
                },
                "required": ["host", "local_path", "remote_path"],
            },
        ),
        Tool(
            name="remote_download",
            description=(
                "Download a file from a remote target over persistent SSH (SFTP). "
                "Use for extracting configs, databases, or artifacts."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP or hostname"},
                    "remote_path": {"type": "string", "description": "File path on target to download"},
                    "local_path": {"type": "string", "description": "Local destination path"},
                    "user": {"type": "string", "default": "root"},
                    "key_path": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 22},
                },
                "required": ["host", "remote_path", "local_path"],
            },
        ),
        Tool(
            name="remote_status",
            description=(
                "Show active SSH connections in the pool. Use to verify "
                "connectivity or debug connection issues."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="remote_disconnect",
            description=(
                "Close a specific SSH connection or all connections. "
                "Use when switching targets or cleaning up."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP (omit to close all)"},
                    "user": {"type": "string", "default": "root"},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "remote_exec":
        return _handle_exec(arguments)
    elif name == "remote_upload":
        return _handle_upload(arguments)
    elif name == "remote_download":
        return _handle_download(arguments)
    elif name == "remote_status":
        return _handle_status()
    elif name == "remote_disconnect":
        return _handle_disconnect(arguments)
    else:
        return _ok({"error": f"Unknown tool: {name}"})


# -- remote_exec -------------------------------------------------------------

def _handle_exec(args: dict) -> list[TextContent]:
    host = args["host"]
    command = args["command"]
    user = args.get("user", "root")
    key_path = args.get("key_path")
    password = args.get("password")
    port = args.get("port", 22)
    timeout = args.get("timeout", 30)
    agent = args.get("agent", "UNKNOWN")

    exit_code, stdout, stderr = _exec_command(
        host, user, command, key_path, password, port, timeout
    )

    # Auto-log to memoria
    output = stdout if stdout else stderr
    _log_to_memoria(host, agent, command, output, exit_code)

    return _ok({
        "tool": "remote_exec",
        "host": host,
        "user": user,
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr if stderr else None,
        "connection": _pool_key(host, user),
    })


# -- remote_upload ------------------------------------------------------------

def _handle_upload(args: dict) -> list[TextContent]:
    host = args["host"]
    local_path = args["local_path"]
    remote_path = args["remote_path"]
    user = args.get("user", "root")
    key_path = args.get("key_path")
    password = args.get("password")
    port = args.get("port", 22)
    mode = args.get("mode", 0o644)

    try:
        client = _get_connection(host, user, key_path, password, port)
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.chmod(remote_path, mode)
        sftp.close()

        return _ok({
            "tool": "remote_upload",
            "host": host,
            "local_path": local_path,
            "remote_path": remote_path,
            "mode": oct(mode),
            "status": "success",
        })
    except Exception as e:
        return _ok({
            "tool": "remote_upload",
            "error": str(e),
            "host": host,
            "local_path": local_path,
            "remote_path": remote_path,
        })


# -- remote_download ----------------------------------------------------------

def _handle_download(args: dict) -> list[TextContent]:
    host = args["host"]
    remote_path = args["remote_path"]
    local_path = args["local_path"]
    user = args.get("user", "root")
    key_path = args.get("key_path")
    password = args.get("password")
    port = args.get("port", 22)

    try:
        client = _get_connection(host, user, key_path, password, port)
        sftp = client.open_sftp()
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        sftp.get(remote_path, local_path)
        size = os.path.getsize(local_path)
        sftp.close()

        return _ok({
            "tool": "remote_download",
            "host": host,
            "remote_path": remote_path,
            "local_path": local_path,
            "size_bytes": size,
            "status": "success",
        })
    except Exception as e:
        return _ok({
            "tool": "remote_download",
            "error": str(e),
            "host": host,
            "remote_path": remote_path,
            "local_path": local_path,
        })


# -- remote_status ------------------------------------------------------------

def _handle_status() -> list[TextContent]:
    connections = []
    with _pool_lock:
        for key, client in _pool.items():
            transport = client.get_transport()
            active = transport is not None and transport.is_active()
            connections.append({
                "connection": key,
                "active": active,
                "remote_version": transport.remote_version if transport else None,
            })

    return _ok({
        "tool": "remote_status",
        "active_connections": len([c for c in connections if c["active"]]),
        "total_connections": len(connections),
        "connections": connections,
    })


# -- remote_disconnect --------------------------------------------------------

def _handle_disconnect(args: dict) -> list[TextContent]:
    host = args.get("host")
    user = args.get("user", "root")

    if host:
        closed = _close_connection(host, user)
        return _ok({
            "tool": "remote_disconnect",
            "connection": _pool_key(host, user),
            "closed": closed,
        })
    else:
        # Close all
        count = 0
        with _pool_lock:
            for key in list(_pool.keys()):
                try:
                    _pool[key].close()
                except Exception:
                    pass
                count += 1
            _pool.clear()
        return _ok({
            "tool": "remote_disconnect",
            "closed_all": True,
            "count": count,
        })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
