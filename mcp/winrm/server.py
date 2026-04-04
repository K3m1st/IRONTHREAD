#!/usr/bin/env python3
"""winrm-mcp — Persistent WinRM session pool for IRONTHREAD operations.

Maintains pywinrm sessions keyed by (host, user, port). Agents call
winrm_connect once, then winrm_exec with just a command. Each command
is an independent HTTP request (no persistent TCP connection to manage).
All commands are logged to memoria if available.

NOTE: Unlike SSH, WinRM commands are stateless — each winrm_exec spawns
a fresh cmd.exe or powershell.exe process. There is no persistent working
directory. Chain commands with 'cd C:\\path && command' or
'Set-Location C:\\path; command' for PowerShell.
"""

import asyncio
import base64
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone

import winrm
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("winrm-mcp")

# ---------------------------------------------------------------------------
# Session pool + active session
# ---------------------------------------------------------------------------

_pool: dict[str, winrm.Session] = {}  # key: "user@host:port"
_pool_lock = threading.Lock()

# Single active session — stores connection params so agents don't repeat them.
_active_session: dict = {}


def _pool_key(host: str, user: str, port: int = 5985) -> str:
    return f"{user}@{host}:{port}"


def _create_session(
    host: str,
    user: str,
    password: str,
    port: int = 5985,
    transport: str = "ntlm",
    use_ssl: bool = False,
    domain: str | None = None,
) -> winrm.Session:
    """Create a new WinRM session and store it in the pool."""
    key = _pool_key(host, user, port)
    scheme = "https" if use_ssl else "http"
    endpoint = f"{scheme}://{host}:{port}/wsman"

    # Prepend domain for NTLM auth
    auth_user = f"{domain}\\{user}" if domain else user

    session = winrm.Session(
        endpoint,
        auth=(auth_user, password),
        transport=transport,
        server_cert_validation="ignore",
    )

    with _pool_lock:
        _pool[key] = session

    return session


def _get_session(args: dict) -> tuple[winrm.Session, dict]:
    """Resolve session from args or active session. Returns (session, params)."""
    host = args.get("host") or _active_session.get("host")
    if not host:
        raise ValueError("No host specified and no active session. Call winrm_connect first.")

    user = args.get("user") or _active_session.get("user", "Administrator")
    password = args.get("password") or _active_session.get("password")
    port = args.get("port") or _active_session.get("port", 5985)

    if not password:
        raise ValueError("No password available. WinRM requires a password.")

    key = _pool_key(host, user, port)
    params = {"host": host, "user": user, "password": password, "port": port}

    with _pool_lock:
        session = _pool.get(key)

    if session is None:
        # Auto-create session with stored params
        transport = _active_session.get("transport", "ntlm")
        use_ssl = _active_session.get("use_ssl", False)
        domain = _active_session.get("domain")
        session = _create_session(host, user, password, port, transport, use_ssl, domain)

    return session, params


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


def _clean_ps_error(stderr: str) -> str:
    """Strip CLIXML wrapper from PowerShell stderr."""
    if not stderr or "#< CLIXML" not in stderr:
        return stderr
    msgs = re.findall(r'<S S="Error">(.*?)</S>', stderr, re.DOTALL)
    return "\n".join(msgs) if msgs else stderr


def _decode_output(raw: bytes) -> str:
    """Decode WinRM output, handling potential UTF-16LE from PowerShell."""
    if not raw:
        return ""
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return raw.decode("utf-16-le")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


def _truncate(text: str, limit: int = 4000) -> str:
    """Truncate output for token efficiency."""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n\n[... truncated, {len(text)} total chars]"


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
        row = conn.execute("SELECT id FROM targets WHERE ip = ?", (host,)).fetchone()
        target_id = row[0] if row else None
        truncated = result[:2000] + "..." if len(result) > 2000 else result
        conn.execute(
            "INSERT INTO actions (target_id, agent, action, detail, result, phase, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (target_id, agent, f"winrm_exec: {command[:100]}", command, truncated, "winrm", _now()),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # Best effort


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="winrm_connect",
            description=(
                "Establish a WinRM session to a Windows target. Call once per target — "
                "after connecting, winrm_exec only needs 'command'. "
                "Credentials are remembered for the session. "
                "Default: HTTP port 5985, NTLM auth (standard for HTB)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP or hostname"},
                    "user": {"type": "string", "description": "Windows username", "default": "Administrator"},
                    "password": {"type": "string", "description": "Windows password"},
                    "port": {"type": "integer", "description": "WinRM port (5985=HTTP, 5986=HTTPS)", "default": 5985},
                    "transport": {
                        "type": "string",
                        "description": "Auth transport",
                        "enum": ["ntlm", "basic", "kerberos"],
                        "default": "ntlm",
                    },
                    "use_ssl": {"type": "boolean", "description": "Use HTTPS (port 5986)", "default": False},
                    "domain": {"type": "string", "description": "AD domain (prepended to username for NTLM)"},
                },
                "required": ["host", "password"],
            },
        ),
        Tool(
            name="winrm_exec",
            description=(
                "Execute a command on the active Windows target. Call winrm_connect "
                "first, then only 'command' is needed. "
                "IMPORTANT: Each command runs in a fresh process — no persistent "
                "working directory. Use 'cd C:\\path && command' to chain."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Command to execute"},
                    "shell": {
                        "type": "string",
                        "description": "Shell to use: cmd (default, predictable) or powershell (richer output)",
                        "enum": ["cmd", "powershell"],
                        "default": "cmd",
                    },
                    "host": {"type": "string", "description": "Target IP (optional if winrm_connect was called)"},
                    "user": {"type": "string", "description": "Username (optional if winrm_connect was called)"},
                    "password": {"type": "string", "description": "Password (optional if winrm_connect was called)"},
                    "port": {"type": "integer", "description": "WinRM port", "default": 5985},
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
            name="winrm_upload",
            description=(
                "Upload a file to the Windows target via WinRM. Uses PowerShell "
                "Base64 encoding (no SFTP available over WinRM). Best for files "
                "under 1MB — larger files are chunked automatically."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {"type": "string", "description": "Local file path to upload"},
                    "remote_path": {"type": "string", "description": "Destination path on target (e.g. C:\\Temp\\file.exe)"},
                    "host": {"type": "string", "description": "Target IP (optional if winrm_connect was called)"},
                    "user": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 5985},
                },
                "required": ["local_path", "remote_path"],
            },
        ),
        Tool(
            name="winrm_download",
            description=(
                "Download a file from the Windows target via WinRM. Uses PowerShell "
                "Base64 encoding. Best for files under 1MB."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "remote_path": {"type": "string", "description": "File path on target to download"},
                    "local_path": {"type": "string", "description": "Local destination path"},
                    "host": {"type": "string", "description": "Target IP (optional if winrm_connect was called)"},
                    "user": {"type": "string"},
                    "password": {"type": "string"},
                    "port": {"type": "integer", "default": 5985},
                },
                "required": ["remote_path", "local_path"],
            },
        ),
        Tool(
            name="winrm_status",
            description="Show active WinRM sessions and current session info.",
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        Tool(
            name="winrm_disconnect",
            description=(
                "Remove a WinRM session from the pool. Since WinRM sessions are "
                "HTTP-based, this just clears stored credentials."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {"type": "string", "description": "Target IP (omit to clear all)"},
                    "user": {"type": "string", "default": "Administrator"},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "winrm_connect":
        return _handle_connect(arguments)
    elif name == "winrm_exec":
        return _handle_exec(arguments)
    elif name == "winrm_upload":
        return _handle_upload(arguments)
    elif name == "winrm_download":
        return _handle_download(arguments)
    elif name == "winrm_status":
        return _handle_status()
    elif name == "winrm_disconnect":
        return _handle_disconnect(arguments)
    else:
        return _ok({"error": f"Unknown tool: {name}"})


# -- winrm_connect -----------------------------------------------------------

def _handle_connect(args: dict) -> list[TextContent]:
    global _active_session
    host = args["host"]
    user = args.get("user", "Administrator")
    password = args["password"]
    port = args.get("port", 5985)
    transport = args.get("transport", "ntlm")
    use_ssl = args.get("use_ssl", False)
    domain = args.get("domain")

    try:
        session = _create_session(host, user, password, port, transport, use_ssl, domain)
        # Validate connection with a simple command
        result = session.run_cmd("hostname")
        hostname = _decode_output(result.std_out).strip()
    except Exception as e:
        return _ok({"tool": "winrm_connect", "error": str(e), "host": host})

    _active_session = {
        "host": host,
        "user": user,
        "password": password,
        "port": port,
        "transport": transport,
        "use_ssl": use_ssl,
        "domain": domain,
    }

    return _ok({
        "tool": "winrm_connect",
        "status": "connected",
        "connection": _pool_key(host, user, port),
        "hostname": hostname,
        "transport": transport,
        "message": "Session active. winrm_exec now only needs 'command'.",
    })


# -- winrm_exec --------------------------------------------------------------

def _handle_exec(args: dict) -> list[TextContent]:
    command = args["command"]
    shell = args.get("shell", "cmd")
    agent = args.get("agent", "UNKNOWN")

    try:
        session, params = _get_session(args)
    except ValueError as e:
        return _ok({"tool": "winrm_exec", "error": str(e)})

    try:
        if shell == "powershell":
            result = session.run_ps(command)
        else:
            result = session.run_cmd(command)

        stdout = _decode_output(result.std_out)
        stderr = _decode_output(result.std_err)
        exit_code = result.status_code

        if shell == "powershell":
            stderr = _clean_ps_error(stderr)

    except Exception as e:
        stdout = ""
        stderr = str(e)
        exit_code = -1

    # Auto-log to memoria
    output = stdout if stdout else stderr
    _log_to_memoria(params["host"], agent, command, output, exit_code)

    return _ok({
        "tool": "winrm_exec",
        "command": command,
        "shell": shell,
        "exit_code": exit_code,
        "stdout": _truncate(stdout),
        "stderr": stderr if stderr else None,
    })


# -- winrm_upload -------------------------------------------------------------

CHUNK_SIZE = 500 * 1024  # 500KB chunks for Base64 transfer

def _handle_upload(args: dict) -> list[TextContent]:
    local_path = args["local_path"]
    remote_path = args["remote_path"]

    try:
        session, params = _get_session(args)
    except ValueError as e:
        return _ok({"tool": "winrm_upload", "error": str(e)})

    if not os.path.exists(local_path):
        return _ok({"tool": "winrm_upload", "error": f"Local file not found: {local_path}"})

    try:
        with open(local_path, "rb") as f:
            data = f.read()

        file_size = len(data)

        if file_size <= CHUNK_SIZE:
            # Single transfer
            b64 = base64.b64encode(data).decode("ascii")
            ps_cmd = (
                f'[System.IO.File]::WriteAllBytes("{remote_path}", '
                f'[Convert]::FromBase64String("{b64}"))'
            )
            result = session.run_ps(ps_cmd)
            if result.status_code != 0:
                err = _decode_output(result.std_err)
                return _ok({"tool": "winrm_upload", "error": _clean_ps_error(err)})
        else:
            # Chunked transfer
            # First chunk: create file
            chunk = data[:CHUNK_SIZE]
            b64 = base64.b64encode(chunk).decode("ascii")
            ps_cmd = (
                f'[System.IO.File]::WriteAllBytes("{remote_path}", '
                f'[Convert]::FromBase64String("{b64}"))'
            )
            result = session.run_ps(ps_cmd)
            if result.status_code != 0:
                err = _decode_output(result.std_err)
                return _ok({"tool": "winrm_upload", "error": _clean_ps_error(err)})

            # Subsequent chunks: append
            offset = CHUNK_SIZE
            while offset < file_size:
                chunk = data[offset:offset + CHUNK_SIZE]
                b64 = base64.b64encode(chunk).decode("ascii")
                ps_cmd = (
                    f'$f = [System.IO.File]::Open("{remote_path}", '
                    f'[System.IO.FileMode]::Append); '
                    f'$bytes = [Convert]::FromBase64String("{b64}"); '
                    f'$f.Write($bytes, 0, $bytes.Length); $f.Close()'
                )
                result = session.run_ps(ps_cmd)
                if result.status_code != 0:
                    err = _decode_output(result.std_err)
                    return _ok({"tool": "winrm_upload", "error": _clean_ps_error(err),
                                "bytes_transferred": offset})
                offset += CHUNK_SIZE

        return _ok({
            "tool": "winrm_upload",
            "local_path": local_path,
            "remote_path": remote_path,
            "size_bytes": file_size,
            "status": "success",
        })

    except Exception as e:
        return _ok({"tool": "winrm_upload", "error": str(e),
                     "local_path": local_path, "remote_path": remote_path})


# -- winrm_download -----------------------------------------------------------

def _handle_download(args: dict) -> list[TextContent]:
    remote_path = args["remote_path"]
    local_path = args["local_path"]

    try:
        session, params = _get_session(args)
    except ValueError as e:
        return _ok({"tool": "winrm_download", "error": str(e)})

    try:
        ps_cmd = f'[Convert]::ToBase64String([System.IO.File]::ReadAllBytes("{remote_path}"))'
        result = session.run_ps(ps_cmd)

        if result.status_code != 0:
            err = _decode_output(result.std_err)
            return _ok({"tool": "winrm_download", "error": _clean_ps_error(err),
                         "remote_path": remote_path})

        b64_data = _decode_output(result.std_out).strip()
        file_data = base64.b64decode(b64_data)

        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(file_data)

        return _ok({
            "tool": "winrm_download",
            "remote_path": remote_path,
            "local_path": local_path,
            "size_bytes": len(file_data),
            "status": "success",
        })

    except Exception as e:
        return _ok({"tool": "winrm_download", "error": str(e),
                     "remote_path": remote_path, "local_path": local_path})


# -- winrm_status -------------------------------------------------------------

def _handle_status() -> list[TextContent]:
    sessions = []
    with _pool_lock:
        for key in _pool:
            sessions.append({"connection": key})

    session_info = None
    if _active_session:
        session_info = {
            "connection": _pool_key(
                _active_session["host"],
                _active_session["user"],
                _active_session.get("port", 5985),
            ),
            "transport": _active_session.get("transport", "ntlm"),
            "use_ssl": _active_session.get("use_ssl", False),
        }

    return _ok({
        "tool": "winrm_status",
        "total_sessions": len(sessions),
        "sessions": sessions,
        "active_session": session_info,
    })


# -- winrm_disconnect --------------------------------------------------------

def _handle_disconnect(args: dict) -> list[TextContent]:
    global _active_session
    host = args.get("host")
    user = args.get("user", "Administrator")

    if host:
        port = _active_session.get("port", 5985)
        key = _pool_key(host, user, port)
        with _pool_lock:
            removed = _pool.pop(key, None) is not None
        if (_active_session.get("host") == host
                and _active_session.get("user") == user):
            _active_session = {}
        return _ok({
            "tool": "winrm_disconnect",
            "connection": key,
            "closed": removed,
        })
    else:
        with _pool_lock:
            count = len(_pool)
            _pool.clear()
        _active_session = {}
        return _ok({
            "tool": "winrm_disconnect",
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
