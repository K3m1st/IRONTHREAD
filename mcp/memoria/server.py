#!/usr/bin/env python3
"""Memoria — Active memory infrastructure for IRONTHREAD operations.

SQLite-backed MCP tool server providing persistent state management,
credential vault, target tracking, findings, and action history.
One DB file per operation. All agents read and write through tools.
"""

import asyncio
import json
import os
import sqlite3
from datetime import datetime, timezone

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("memoria-mcp")

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get(
    "MEMORIA_DB",
    os.path.join(os.getcwd(), "..", "shared", "memoria.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS state (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS targets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    ip             TEXT NOT NULL UNIQUE,
    hostname       TEXT,
    os             TEXT,
    status         TEXT NOT NULL DEFAULT 'discovered',
    access_level   TEXT DEFAULT 'none',
    access_user    TEXT,
    access_method  TEXT,
    notes          TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS services (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id  INTEGER NOT NULL REFERENCES targets(id),
    port       INTEGER NOT NULL,
    protocol   TEXT NOT NULL DEFAULT 'tcp',
    service    TEXT,
    version    TEXT,
    banner     TEXT,
    confidence TEXT DEFAULT 'MEDIUM',
    notes      TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(target_id, port, protocol)
);

CREATE TABLE IF NOT EXISTS credentials (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id   INTEGER REFERENCES targets(id),
    cred_type   TEXT NOT NULL,
    username    TEXT,
    secret      TEXT NOT NULL,
    domain      TEXT,
    source      TEXT NOT NULL,
    verified    INTEGER DEFAULT 0,
    context     TEXT,
    found_by    TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id   INTEGER REFERENCES targets(id),
    category    TEXT NOT NULL,
    title       TEXT NOT NULL,
    detail      TEXT NOT NULL,
    confidence  TEXT DEFAULT 'MEDIUM',
    status      TEXT DEFAULT 'open',
    severity    TEXT,
    evidence    TEXT,
    found_by    TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id   INTEGER REFERENCES targets(id),
    agent       TEXT NOT NULL,
    action      TEXT NOT NULL,
    detail      TEXT,
    result      TEXT,
    phase       TEXT,
    session_id  TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_services_target ON services(target_id);
CREATE INDEX IF NOT EXISTS idx_credentials_target ON credentials(target_id);
CREATE INDEX IF NOT EXISTS idx_findings_target ON findings(target_id);
CREATE INDEX IF NOT EXISTS idx_findings_status ON findings(status);
CREATE INDEX IF NOT EXISTS idx_actions_target ON actions(target_id);
CREATE INDEX IF NOT EXISTS idx_actions_agent ON actions(agent);
CREATE INDEX IF NOT EXISTS idx_actions_created ON actions(created_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def _resolve_target_id(conn: sqlite3.Connection, ip: str | None) -> int | None:
    if not ip:
        return None
    row = conn.execute("SELECT id FROM targets WHERE ip = ?", (ip,)).fetchone()
    return row["id"] if row else None


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, default=str))]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # 1. Get full operational state
        Tool(
            name="memoria_get_state",
            description=(
                "Get full operational state: current phase, all targets with "
                "services, active findings, recent actions, and credential "
                "summary. Call at session start for instant awareness."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []},
        ),
        # 2. Set operation-level state
        Tool(
            name="memoria_set_state",
            description=(
                "Set an operation-level key-value pair (current_phase, "
                "active_agent, user_flag, root_flag, etc.)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "State key"},
                    "value": {"type": "string", "description": "State value"},
                },
                "required": ["key", "value"],
            },
        ),
        # 3. Add or update a target
        Tool(
            name="memoria_upsert_target",
            description=(
                "Add or update a target. If IP exists, updates provided fields. "
                "Use when discovering targets or updating access level."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ip": {"type": "string", "description": "Target IP address"},
                    "hostname": {"type": "string"},
                    "os": {"type": "string"},
                    "status": {
                        "type": "string",
                        "enum": ["discovered", "scanning", "foothold", "rooted"],
                    },
                    "access_level": {
                        "type": "string",
                        "enum": ["none", "user", "root", "system"],
                    },
                    "access_user": {"type": "string", "description": "Current user we have access as"},
                    "access_method": {"type": "string", "description": "How we got in"},
                    "notes": {"type": "string"},
                },
                "required": ["ip"],
            },
        ),
        # 4. Record a service
        Tool(
            name="memoria_add_service",
            description=(
                "Record a service on a target. Upserts on (target_ip, port, protocol)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string"},
                    "port": {"type": "integer"},
                    "protocol": {"type": "string", "default": "tcp"},
                    "service": {"type": "string"},
                    "version": {"type": "string"},
                    "banner": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "notes": {"type": "string"},
                },
                "required": ["target_ip", "port"],
            },
        ),
        # 5. Store a credential
        Tool(
            name="memoria_store_credential",
            description=(
                "Store a recovered credential (password, hash, SSH key, token, "
                "API key). All creds go here — single vault."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "cred_type": {
                        "type": "string",
                        "enum": ["password", "hash", "ssh_key", "token", "api_key", "certificate"],
                    },
                    "secret": {"type": "string", "description": "The credential value"},
                    "username": {"type": "string"},
                    "target_ip": {"type": "string"},
                    "domain": {"type": "string"},
                    "source": {"type": "string", "description": "Where found"},
                    "context": {"type": "string", "description": "What it accesses"},
                    "found_by": {"type": "string", "enum": ["ORACLE", "ELLIOT", "NOIRE"]},
                    "verified": {"type": "boolean", "default": False},
                },
                "required": ["cred_type", "secret", "source", "found_by"],
            },
        ),
        # 6. Query credentials
        Tool(
            name="memoria_get_credentials",
            description=(
                "Retrieve stored credentials. Filter by target, username, type, "
                "or verified status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string"},
                    "username": {"type": "string"},
                    "cred_type": {"type": "string"},
                    "verified_only": {"type": "boolean", "default": False},
                },
                "required": [],
            },
        ),
        # 7. Record a finding
        Tool(
            name="memoria_add_finding",
            description=(
                "Record a finding: attack path, vulnerability, misconfiguration, "
                "anomaly, privesc lead, or new surface."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "attack_path", "misconfig", "anomaly",
                            "vuln", "privesc_lead", "new_surface",
                        ],
                    },
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low", "info"]},
                    "status": {
                        "type": "string",
                        "enum": ["open", "in_progress", "validated", "exhausted"],
                        "default": "open",
                    },
                    "evidence": {"type": "string"},
                    "found_by": {"type": "string", "enum": ["ORACLE", "ELLIOT", "NOIRE"]},
                },
                "required": ["category", "title", "detail", "found_by"],
            },
        ),
        # 8. Update a finding
        Tool(
            name="memoria_update_finding",
            description=(
                "Update a finding's status, confidence, or detail. Use when a "
                "path is validated, exhausted, or evidence changes."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "finding_id": {"type": "integer"},
                    "status": {"type": "string", "enum": ["open", "in_progress", "validated", "exhausted"]},
                    "confidence": {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
                    "detail": {"type": "string"},
                    "evidence": {"type": "string"},
                },
                "required": ["finding_id"],
            },
        ),
        # 9. Log an action
        Tool(
            name="memoria_log_action",
            description=(
                "Log a significant action taken by an agent. Provides the "
                "audit trail for the operation."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "agent": {"type": "string", "enum": ["ORACLE", "ELLIOT", "NOIRE"]},
                    "action": {"type": "string", "description": "Short description"},
                    "target_ip": {"type": "string"},
                    "detail": {"type": "string"},
                    "result": {"type": "string"},
                    "phase": {"type": "string"},
                    "session_id": {"type": "string"},
                },
                "required": ["agent", "action"],
            },
        ),
        # 10. Query everything about a target
        Tool(
            name="memoria_query_target",
            description=(
                "Get everything known about a specific target: services, "
                "credentials, findings, and recent actions."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "target_ip": {"type": "string", "description": "Target IP to query"},
                },
                "required": ["target_ip"],
            },
        ),
    ]


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    conn = _db()
    try:
        if name == "memoria_get_state":
            return _handle_get_state(conn)
        elif name == "memoria_set_state":
            return _handle_set_state(conn, arguments)
        elif name == "memoria_upsert_target":
            return _handle_upsert_target(conn, arguments)
        elif name == "memoria_add_service":
            return _handle_add_service(conn, arguments)
        elif name == "memoria_store_credential":
            return _handle_store_credential(conn, arguments)
        elif name == "memoria_get_credentials":
            return _handle_get_credentials(conn, arguments)
        elif name == "memoria_add_finding":
            return _handle_add_finding(conn, arguments)
        elif name == "memoria_update_finding":
            return _handle_update_finding(conn, arguments)
        elif name == "memoria_log_action":
            return _handle_log_action(conn, arguments)
        elif name == "memoria_query_target":
            return _handle_query_target(conn, arguments)
        else:
            return _ok({"error": f"Unknown tool: {name}"})
    finally:
        conn.close()


# -- 1. get_state -----------------------------------------------------------

def _handle_get_state(conn: sqlite3.Connection) -> list[TextContent]:
    state = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM state").fetchall()}

    targets = []
    for t in conn.execute("SELECT * FROM targets ORDER BY id").fetchall():
        target = dict(t)
        target["services"] = [
            dict(s) for s in conn.execute(
                "SELECT port, protocol, service, version, confidence FROM services WHERE target_id = ? ORDER BY port",
                (t["id"],),
            ).fetchall()
        ]
        targets.append(target)

    active_findings = [
        dict(f) for f in conn.execute(
            "SELECT id, target_id, category, title, confidence, status, severity, found_by "
            "FROM findings WHERE status != 'exhausted' ORDER BY id",
        ).fetchall()
    ]

    recent_actions = [
        dict(a) for a in conn.execute(
            "SELECT agent, action, target_id, result, phase, created_at "
            "FROM actions ORDER BY created_at DESC LIMIT 20",
        ).fetchall()
    ]

    cred_summary = conn.execute(
        "SELECT cred_type, COUNT(*) as count, SUM(verified) as verified_count "
        "FROM credentials GROUP BY cred_type",
    ).fetchall()

    return _ok({
        "tool": "memoria_get_state",
        "state": state,
        "targets": targets,
        "active_findings": active_findings,
        "recent_actions": recent_actions,
        "credential_summary": [dict(c) for c in cred_summary],
        "db_path": DB_PATH,
    })


# -- 2. set_state -----------------------------------------------------------

def _handle_set_state(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    key, value, now = args["key"], args["value"], _now()
    old = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    conn.execute(
        "INSERT INTO state (key, value, updated_at) VALUES (?, ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        (key, value, now),
    )
    conn.commit()
    return _ok({
        "tool": "memoria_set_state",
        "key": key,
        "value": value,
        "previous_value": old["value"] if old else None,
        "updated_at": now,
    })


# -- 3. upsert_target -------------------------------------------------------

def _handle_upsert_target(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    ip, now = args["ip"], _now()
    existing = conn.execute("SELECT * FROM targets WHERE ip = ?", (ip,)).fetchone()

    if existing:
        updates = {}
        for field in ("hostname", "os", "status", "access_level", "access_user", "access_method", "notes"):
            if field in args and args[field] is not None:
                updates[field] = args[field]
        if updates:
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE targets SET {set_clause} WHERE ip = ?",
                (*updates.values(), ip),
            )
            conn.commit()
        row = conn.execute("SELECT * FROM targets WHERE ip = ?", (ip,)).fetchone()
    else:
        conn.execute(
            "INSERT INTO targets (ip, hostname, os, status, access_level, access_user, access_method, notes, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                ip,
                args.get("hostname"),
                args.get("os"),
                args.get("status", "discovered"),
                args.get("access_level", "none"),
                args.get("access_user"),
                args.get("access_method"),
                args.get("notes"),
                now,
                now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM targets WHERE ip = ?", (ip,)).fetchone()

    return _ok({"tool": "memoria_upsert_target", "target": dict(row)})


# -- 4. add_service ----------------------------------------------------------

def _handle_add_service(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    ip = args["target_ip"]
    target_id = _resolve_target_id(conn, ip)
    if not target_id:
        # Auto-create target
        _handle_upsert_target(conn, {"ip": ip})
        target_id = _resolve_target_id(conn, ip)

    now = _now()
    conn.execute(
        "INSERT INTO services (target_id, port, protocol, service, version, banner, confidence, notes, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(target_id, port, protocol) DO UPDATE SET "
        "service=excluded.service, version=excluded.version, banner=excluded.banner, "
        "confidence=excluded.confidence, notes=excluded.notes",
        (
            target_id,
            args["port"],
            args.get("protocol", "tcp"),
            args.get("service"),
            args.get("version"),
            args.get("banner"),
            args.get("confidence", "MEDIUM"),
            args.get("notes"),
            now,
        ),
    )
    conn.commit()

    row = conn.execute(
        "SELECT * FROM services WHERE target_id = ? AND port = ? AND protocol = ?",
        (target_id, args["port"], args.get("protocol", "tcp")),
    ).fetchone()
    return _ok({"tool": "memoria_add_service", "service": dict(row)})


# -- 5. store_credential -----------------------------------------------------

def _handle_store_credential(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    target_id = _resolve_target_id(conn, args.get("target_ip"))
    now = _now()

    conn.execute(
        "INSERT INTO credentials (target_id, cred_type, username, secret, domain, source, verified, context, found_by, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            target_id,
            args["cred_type"],
            args.get("username"),
            args["secret"],
            args.get("domain"),
            args["source"],
            1 if args.get("verified") else 0,
            args.get("context"),
            args["found_by"],
            now,
        ),
    )
    conn.commit()
    cred_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Mask secret in response
    secret = args["secret"]
    masked = secret[:4] + "***" if len(secret) > 4 else "***"

    return _ok({
        "tool": "memoria_store_credential",
        "credential_id": cred_id,
        "cred_type": args["cred_type"],
        "username": args.get("username"),
        "secret_masked": masked,
        "source": args["source"],
        "found_by": args["found_by"],
    })


# -- 6. get_credentials ------------------------------------------------------

def _handle_get_credentials(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    query = "SELECT c.*, t.ip as target_ip FROM credentials c LEFT JOIN targets t ON c.target_id = t.id WHERE 1=1"
    params = []

    if args.get("target_ip"):
        query += " AND t.ip = ?"
        params.append(args["target_ip"])
    if args.get("username"):
        query += " AND c.username = ?"
        params.append(args["username"])
    if args.get("cred_type"):
        query += " AND c.cred_type = ?"
        params.append(args["cred_type"])
    if args.get("verified_only"):
        query += " AND c.verified = 1"

    query += " ORDER BY c.created_at DESC"
    rows = conn.execute(query, params).fetchall()
    return _ok({
        "tool": "memoria_get_credentials",
        "count": len(rows),
        "credentials": [dict(r) for r in rows],
    })


# -- 7. add_finding -----------------------------------------------------------

def _handle_add_finding(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    target_id = _resolve_target_id(conn, args.get("target_ip"))
    now = _now()

    conn.execute(
        "INSERT INTO findings (target_id, category, title, detail, confidence, status, severity, evidence, found_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            target_id,
            args["category"],
            args["title"],
            args["detail"],
            args.get("confidence", "MEDIUM"),
            args.get("status", "open"),
            args.get("severity"),
            args.get("evidence"),
            args["found_by"],
            now,
            now,
        ),
    )
    conn.commit()
    finding_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return _ok({
        "tool": "memoria_add_finding",
        "finding_id": finding_id,
        "category": args["category"],
        "title": args["title"],
        "status": args.get("status", "open"),
    })


# -- 8. update_finding --------------------------------------------------------

def _handle_update_finding(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    finding_id = args["finding_id"]
    existing = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    if not existing:
        return _ok({"error": f"Finding {finding_id} not found"})

    updates = {}
    for field in ("status", "confidence", "detail", "evidence"):
        if field in args and args[field] is not None:
            updates[field] = args[field]

    if updates:
        updates["updated_at"] = _now()
        set_clause = ", ".join(f"{k} = ?" for k in updates)
        conn.execute(
            f"UPDATE findings SET {set_clause} WHERE id = ?",
            (*updates.values(), finding_id),
        )
        conn.commit()

    row = conn.execute("SELECT * FROM findings WHERE id = ?", (finding_id,)).fetchone()
    return _ok({"tool": "memoria_update_finding", "finding": dict(row)})


# -- 9. log_action ------------------------------------------------------------

def _handle_log_action(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    target_id = _resolve_target_id(conn, args.get("target_ip"))
    now = _now()

    conn.execute(
        "INSERT INTO actions (target_id, agent, action, detail, result, phase, session_id, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            target_id,
            args["agent"],
            args["action"],
            args.get("detail"),
            args.get("result"),
            args.get("phase"),
            args.get("session_id"),
            now,
        ),
    )
    conn.commit()
    action_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    return _ok({
        "tool": "memoria_log_action",
        "action_id": action_id,
        "agent": args["agent"],
        "action": args["action"],
        "created_at": now,
    })


# -- 10. query_target ---------------------------------------------------------

def _handle_query_target(conn: sqlite3.Connection, args: dict) -> list[TextContent]:
    ip = args["target_ip"]
    target = conn.execute("SELECT * FROM targets WHERE ip = ?", (ip,)).fetchone()
    if not target:
        return _ok({"error": f"Target {ip} not found", "tool": "memoria_query_target"})

    tid = target["id"]

    services = [
        dict(s) for s in conn.execute(
            "SELECT * FROM services WHERE target_id = ? ORDER BY port", (tid,)
        ).fetchall()
    ]

    credentials = [
        dict(c) for c in conn.execute(
            "SELECT * FROM credentials WHERE target_id = ? ORDER BY created_at DESC", (tid,)
        ).fetchall()
    ]

    findings = [
        dict(f) for f in conn.execute(
            "SELECT * FROM findings WHERE target_id = ? ORDER BY id", (tid,)
        ).fetchall()
    ]

    actions = [
        dict(a) for a in conn.execute(
            "SELECT * FROM actions WHERE target_id = ? ORDER BY created_at DESC LIMIT 50", (tid,)
        ).fetchall()
    ]

    return _ok({
        "tool": "memoria_query_target",
        "target": dict(target),
        "services": services,
        "credentials": credentials,
        "findings": findings,
        "recent_actions": actions,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
