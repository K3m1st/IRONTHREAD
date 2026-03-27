#!/usr/bin/env python3
"""Remote — Persistent SSH session pool for IRONTHREAD operations.

Maintains long-lived Paramiko connections keyed by (host, user).
Agents call remote_connect once, then remote_exec with just a command.
Connections auto-reconnect on failure. All commands are logged to
memoria if available.
"""

import asyncio
import json
import os
import re
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
# Connection pool + active session
# ---------------------------------------------------------------------------

_pool: dict[str, paramiko.SSHClient] = {}  # key: "user@host"
_pool_lock = threading.Lock()

# Single active session — stores connection params so agents don't repeat them.
# Set by remote_connect, cleared by remote_disconnect.
_active_session: dict = {}


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


def _resolve_session(args: dict) -> dict:
    """Resolve connection params: explicit args > active session > error.

    Returns dict with host, user, key_path, password, port or raises ValueError.
    """
    host = args.get("host") or _active_session.get("host")
    if not host:
        raise ValueError("No host specified and no active session. Call remote_connect first.")

    return {
        "host": host,
        "user": args.get("user") or _active_session.get("user", "root"),
        "key_path": args.get("key_path") or _active_session.get("key_path"),
        "password": args.get("password") or _active_session.get("password"),
        "port": args.get("port") or _active_session.get("port", 22),
    }


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
            name="remote_connect",
            description=(
                "Establish an SSH session to a target. Call once per target — "
                "after connecting, remote_exec only needs 'command'. "
                "Credentials are remembered for the session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP or hostname"},
                    "user": {"type": "string", "description": "SSH username", "default": "root"},
                    "key_path": {"type": "string", "description": "Path to SSH private key"},
                    "password": {"type": "string", "description": "SSH password"},
                    "port": {"type": "integer", "description": "SSH port", "default": 22},
                },
                "required": ["host"],
            },
        ),
        Tool(
            name="remote_exec",
            description=(
                "Execute a command on the active target. Call remote_connect "
                "first, then only 'command' is needed. Working directory "
                "persists across calls (use 'cd /path' to change it). "
                "Host/user/credentials can override the active session."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "host": {"type": "string", "description": "Target IP (optional if remote_connect was called)"},
                    "user": {"type": "string", "description": "SSH username (optional if remote_connect was called)"},
                    "key_path": {"type": "string", "description": "Path to SSH private key (optional)"},
                    "password": {"type": "string", "description": "SSH password (optional)"},
                    "port": {"type": "integer", "description": "SSH port", "default": 22},
                    "timeout": {"type": "integer", "description": "Command timeout in seconds", "default": 30},
                    "agent": {
                        "type": "string",
                        "description": "Which agent is calling (for memoria logging)",
                        "enum": ["ORACLE", "ELLIOT", "NOIRE"],
                    },
                },
                "required": ["command"],
            },
        ),
        Tool(
            name="remote_upload",
            description=(
                "Upload a file to the active target over SFTP. "
                "Uses active session if remote_connect was called."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {"type": "string", "description": "Local file path to upload"},
                    "remote_path": {"type": "string", "description": "Destination path on target"},
                    "host": {"type": "string", "description": "Target IP (optional if remote_connect was called)"},
                    "user": {"type": "string", "default": "root"},
                    "key_path": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 22},
                    "mode": {"type": "integer", "description": "File permissions (octal as int, e.g. 755)", "default": 644},
                },
                "required": ["local_path", "remote_path"],
            },
        ),
        Tool(
            name="remote_download",
            description=(
                "Download a file from the active target over SFTP. "
                "Uses active session if remote_connect was called."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {"type": "string", "description": "File path on target to download"},
                    "local_path": {"type": "string", "description": "Local destination path"},
                    "host": {"type": "string", "description": "Target IP (optional if remote_connect was called)"},
                    "user": {"type": "string", "default": "root"},
                    "key_path": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 22},
                },
                "required": ["remote_path", "local_path"],
            },
        ),
        Tool(
            name="remote_status",
            description=(
                "Show active SSH connections and current session info."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="remote_disconnect",
            description=(
                "Close a specific SSH connection or all connections. "
                "Clears the active session."
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
    if name == "remote_connect":
        return _handle_connect(arguments)
    elif name == "remote_exec":
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


# -- remote_connect ----------------------------------------------------------

def _handle_connect(args: dict) -> list[TextContent]:
    global _active_session
    host = args["host"]
    user = args.get("user", "root")
    key_path = args.get("key_path")
    password = args.get("password")
    port = args.get("port", 22)

    try:
        _get_connection(host, user, key_path, password, port)
    except Exception as e:
        return _ok({"tool": "remote_connect", "error": str(e), "host": host})

    _active_session = {
        "host": host,
        "user": user,
        "key_path": key_path,
        "password": password,
        "port": port,
        "cwd": None,
    }

    return _ok({
        "tool": "remote_connect",
        "status": "connected",
        "connection": _pool_key(host, user),
        "message": "Session active. remote_exec now only needs 'command'.",
    })


# -- remote_exec -------------------------------------------------------------

def _handle_exec(args: dict) -> list[TextContent]:
    command = args["command"]

    # Resolve connection params from args or active session
    try:
        session = _resolve_session(args)
    except ValueError as e:
        return _ok({"tool": "remote_exec", "error": str(e)})

    host = session["host"]
    user = session["user"]
    timeout = args.get("timeout", 30)
    agent = args.get("agent", "UNKNOWN")

    # Prepend cwd if tracked
    cwd = _active_session.get("cwd")
    actual_command = f"cd {cwd} && {command}" if cwd else command

    exit_code, stdout, stderr = _exec_command(
        host, user, actual_command,
        session["key_path"], session["password"], session["port"],
        timeout,
    )

    # Track bare 'cd <path>' commands
    cd_match = re.match(r"^cd\s+(\S+)\s*$", command)
    if cd_match and exit_code == 0:
        new_dir = cd_match.group(1)
        # Resolve the actual path on the remote host
        resolve_cmd = f"cd {cwd + '/' if cwd and not new_dir.startswith('/') else ''}{new_dir} && pwd"
        _, pwd_out, _ = _exec_command(
            host, user, resolve_cmd,
            session["key_path"], session["password"], session["port"], 5,
        )
        resolved = pwd_out.strip()
        if resolved:
            _active_session["cwd"] = resolved

    # Auto-log to memoria
    output = stdout if stdout else stderr
    _log_to_memoria(host, agent, command, output, exit_code)

    result = {
        "tool": "remote_exec",
        "command": command,
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr if stderr else None,
    }
    if cwd:
        result["cwd"] = cwd
    return _ok(result)


# -- remote_upload ------------------------------------------------------------

def _handle_upload(args: dict) -> list[TextContent]:
    local_path = args["local_path"]
    remote_path = args["remote_path"]
    mode = args.get("mode", 0o644)

    try:
        session = _resolve_session(args)
    except ValueError as e:
        return _ok({"tool": "remote_upload", "error": str(e)})

    try:
        client = _get_connection(
            session["host"], session["user"],
            session["key_path"], session["password"], session["port"],
        )
        sftp = client.open_sftp()
        sftp.put(local_path, remote_path)
        sftp.chmod(remote_path, mode)
        sftp.close()

        return _ok({
            "tool": "remote_upload",
            "local_path": local_path,
            "remote_path": remote_path,
            "mode": oct(mode),
            "status": "success",
        })
    except Exception as e:
        return _ok({
            "tool": "remote_upload",
            "error": str(e),
            "local_path": local_path,
            "remote_path": remote_path,
        })


# -- remote_download ----------------------------------------------------------

def _handle_download(args: dict) -> list[TextContent]:
    remote_path = args["remote_path"]
    local_path = args["local_path"]

    try:
        session = _resolve_session(args)
    except ValueError as e:
        return _ok({"tool": "remote_download", "error": str(e)})

    try:
        client = _get_connection(
            session["host"], session["user"],
            session["key_path"], session["password"], session["port"],
        )
        sftp = client.open_sftp()
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        sftp.get(remote_path, local_path)
        size = os.path.getsize(local_path)
        sftp.close()

        return _ok({
            "tool": "remote_download",
            "remote_path": remote_path,
            "local_path": local_path,
            "size_bytes": size,
            "status": "success",
        })
    except Exception as e:
        return _ok({
            "tool": "remote_download",
            "error": str(e),
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

    session_info = None
    if _active_session:
        session_info = {
            "connection": _pool_key(_active_session["host"], _active_session["user"]),
            "cwd": _active_session.get("cwd"),
        }

    return _ok({
        "tool": "remote_status",
        "active_connections": len([c for c in connections if c["active"]]),
        "total_connections": len(connections),
        "connections": connections,
        "active_session": session_info,
    })


# -- remote_disconnect --------------------------------------------------------

def _handle_disconnect(args: dict) -> list[TextContent]:
    global _active_session
    host = args.get("host")
    user = args.get("user", "root")

    if host:
        closed = _close_connection(host, user)
        # Clear active session if it matches
        if (_active_session.get("host") == host
                and _active_session.get("user") == user):
            _active_session = {}
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
        _active_session = {}
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
