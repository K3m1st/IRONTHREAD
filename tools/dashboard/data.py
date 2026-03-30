"""Data layer for IRONTHREAD Operator Dashboard.

Read-only access to Memoria SQLite databases. Never writes.
"""

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


BOXES_DIR = Path(__file__).resolve().parent.parent.parent / "boxes"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class TargetInfo:
    ip: str = ""
    hostname: str | None = None
    os: str | None = None
    status: str = "unknown"
    access_level: str = "none"
    access_user: str | None = None
    access_method: str | None = None
    phase: str | None = None
    user_flag: str | None = None
    root_flag: str | None = None


@dataclass
class Service:
    port: int = 0
    protocol: str = "tcp"
    service: str | None = None
    version: str | None = None


@dataclass
class Finding:
    id: int = 0
    category: str = ""
    title: str = ""
    severity: str | None = None
    status: str = "open"
    found_by: str = ""
    detail: str = ""
    evidence: str | None = None


@dataclass
class Credential:
    id: int = 0
    cred_type: str = ""
    username: str | None = None
    source: str = ""
    verified: bool = False
    found_by: str = ""
    context: str | None = None


@dataclass
class Action:
    agent: str = ""
    action: str = ""
    phase: str | None = None
    created_at: str = ""


@dataclass
class BoxState:
    target: TargetInfo = field(default_factory=TargetInfo)
    services: list[Service] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)
    credentials: list[Credential] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def resolve_db_path(box_name: str) -> Path:
    """Resolve boxes/{name}/shared/memoria.db from project root."""
    return BOXES_DIR / box_name / "shared" / "memoria.db"


def _connect(db_path: Path) -> sqlite3.Connection:
    """Open a read-only connection to a Memoria database."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


# ---------------------------------------------------------------------------
# Main loader
# ---------------------------------------------------------------------------

def load_box_state(db_path: Path) -> BoxState:
    """Load full operational state from a single Memoria database."""
    conn = _connect(db_path)
    try:
        state = BoxState()

        # --- state KV pairs ---
        kv = {}
        for row in conn.execute("SELECT key, value FROM state"):
            kv[row["key"]] = row["value"]

        # --- target ---
        row = conn.execute(
            "SELECT ip, hostname, os, status, access_level, "
            "access_user, access_method FROM targets LIMIT 1"
        ).fetchone()
        if row:
            state.target = TargetInfo(
                ip=row["ip"],
                hostname=row["hostname"],
                os=row["os"],
                status=row["status"],
                access_level=row["access_level"] or "none",
                access_user=row["access_user"],
                access_method=row["access_method"],
                phase=kv.get("current_phase"),
                user_flag=kv.get("user_flag"),
                root_flag=kv.get("root_flag"),
            )
        else:
            state.target.phase = kv.get("current_phase")
            state.target.user_flag = kv.get("user_flag")
            state.target.root_flag = kv.get("root_flag")

        # --- services ---
        for row in conn.execute(
            "SELECT port, protocol, service, version "
            "FROM services ORDER BY port"
        ):
            state.services.append(Service(
                port=row["port"],
                protocol=row["protocol"],
                service=row["service"],
                version=row["version"],
            ))

        # --- findings (sorted by severity) ---
        for row in conn.execute(
            "SELECT id, category, title, severity, status, found_by, "
            "detail, evidence FROM findings "
            "ORDER BY CASE severity "
            "  WHEN 'critical' THEN 0 WHEN 'high' THEN 1 "
            "  WHEN 'medium' THEN 2 WHEN 'low' THEN 3 ELSE 4 END, id"
        ):
            state.findings.append(Finding(
                id=row["id"],
                category=row["category"],
                title=row["title"],
                severity=row["severity"],
                status=row["status"],
                found_by=row["found_by"],
                detail=row["detail"],
                evidence=row["evidence"],
            ))

        # --- credentials (no secrets — dashboard is read-only display) ---
        for row in conn.execute(
            "SELECT id, cred_type, username, source, verified, found_by, "
            "context FROM credentials ORDER BY id"
        ):
            state.credentials.append(Credential(
                id=row["id"],
                cred_type=row["cred_type"],
                username=row["username"],
                source=row["source"],
                verified=bool(row["verified"]),
                found_by=row["found_by"],
                context=row["context"],
            ))

        # --- actions (most recent 50) ---
        for row in conn.execute(
            "SELECT agent, action, phase, created_at "
            "FROM actions ORDER BY created_at DESC LIMIT 50"
        ):
            state.actions.append(Action(
                agent=row["agent"],
                action=row["action"],
                phase=row["phase"],
                created_at=row["created_at"],
            ))

        return state

    finally:
        conn.close()
