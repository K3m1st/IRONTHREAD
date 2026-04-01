# IRONTHREAD
> Offensive AI Agent Framework for HTB / Pentesting

---

## Overview

Three-agent architecture backed by MCP tool servers and a persistent state engine (Memoria):

```
ORACLE (strategy + recon)  →  ELLIOT (exploitation)  →  NOIRE (post-access)
        ↑                           ↑                          ↑
   sova-mcp                    remote-mcp                 remote-mcp
   webdig-mcp                  memoria-mcp                memoria-mcp
   memoria-mcp
```

- **ORACLE** — reconnaissance, CVE research, strategic analysis, attack surface mapping, operator briefings
- **ELLIOT** — scoped exploitation and privilege escalation
- **NOIRE** — post-access investigation, credential harvesting, privesc lead identification

All agents share state through **Memoria** (SQLite), ensuring no information is lost between sessions.

```bash
# One-time setup
./scripts/install.sh

# Every new box
./scripts/new_box.sh BOXNAME 10.10.10.10
```

---

## Repository Structure

```
IRONTHREAD/
├── templates/                  ← source of truth for agent prompts
│   ├── oracle/                 ← strategic planner
│   ├── elliot/                 ← exploitation specialist
│   └── noire/                  ← post-access investigator
├── mcp/                        ← MCP tool servers
│   ├── sova/server.py          ← reconnaissance tools
│   ├── webdig/server.py        ← web enumeration tools
│   ├── memoria/server.py       ← persistent state engine (SQLite)
│   ├── remote/server.py        ← SSH session pool
│   └── requirements.txt
├── schemas/                    ← JSON contracts + operational templates
├── scripts/                    ← setup and validation scripts
├── tools/
│   └── dashboard/              ← operator TUI dashboard
├── docs/                       ← tradecraft research
├── writeups/                   ← completed operation debriefs
├── .claude/commands/           ← operator slash commands
└── boxes/                      ← per-box operation directories (gitignored)
```

---

## Quick Start

### One-Time Setup

```bash
cd ~/IRONTHREAD
chmod +x scripts/install.sh scripts/new_box.sh
./scripts/install.sh
```

### Every New Box

```bash
./scripts/new_box.sh Monitored 10.10.10.10
```

Creates `boxes/Monitored/` with oracle/, elliot/, noire/, and shared/ directories — copies templates, schemas, and MCP config.

### Operational Flow

```bash
# 1. ORACLE — recon, analysis, attack surface
cd boxes/Monitored/oracle && claude

# 2. ELLIOT — exploitation (when ORACLE writes handoff.json)
cd boxes/Monitored/elliot && claude

# 3. NOIRE — post-access investigation (when foothold is established)
cd boxes/Monitored/noire && claude

# Cycle as needed: ORACLE → ELLIOT → NOIRE → ORACLE
```

---

## MCP Tool Servers

### sova-mcp (Reconnaissance)
| Tool | Description |
|------|-------------|
| `sova_full_scan` | nmap full port scan with service detection |
| `sova_whatweb` | Web technology fingerprinting |
| `sova_banner_grab` | Service banner grab on specific port |
| `sova_zone_transfer` | DNS zone transfer attempt |
| `sova_null_session` | SMB null session enumeration |
| `sova_anon_ftp` | Anonymous FTP access test |
| `sova_udp_scan` | UDP port scan |
| `sova_add_hosts` | Add entries to /etc/hosts |

### webdig-mcp (Web Enumeration)
| Tool | Description |
|------|-------------|
| `webdig_dir_bust` | Directory bruteforcing (gobuster) |
| `webdig_vhost_fuzz` | Virtual host fuzzing (ffuf) |
| `webdig_curl` | HTTP requests with full control |
| `webdig_js_review` | JavaScript endpoint/secret extraction |

### memoria-mcp (State Engine)
| Tool | Description |
|------|-------------|
| `memoria_get_state` | Full operational snapshot (targets, findings, creds, actions) |
| `memoria_set_state` | Set operation-level state (phase, flags) |
| `memoria_upsert_target` | Create/update target with access info |
| `memoria_add_service` | Record discovered service |
| `memoria_store_credential` | Store credential in vault (masked by default) |
| `memoria_get_credentials` | Query credential vault with filters |
| `memoria_add_finding` | Record vulnerability, attack path, or privesc lead |
| `memoria_update_finding` | Update finding status/evidence |
| `memoria_log_action` | Audit trail entry |
| `memoria_query_target` | Full target dossier |

Includes a consistency engine that warns when access level, flags, and phase are out of sync.

### remote-mcp (SSH Session Pool)
| Tool | Description |
|------|-------------|
| `remote_connect` | Establish persistent SSH connection |
| `remote_exec` | Execute command on target (auto-logs to Memoria) |
| `remote_upload` | Upload file to target |
| `remote_download` | Download file from target |
| `remote_status` | Show active sessions |
| `remote_disconnect` | Close SSH session |

---

## Operator Dashboard

Terminal UI for real-time operational awareness. Reads directly from Memoria.

```bash
pip3 install -r tools/dashboard/requirements.txt
python3 tools/dashboard/app.py <BoxName>
```

Displays: target info, services, findings (with drill-down), credentials, action timeline. Color-coded by severity, agent, and access level. Auto-refreshes every 10 seconds.

---

## Operator Skills

Slash commands available inside Claude Code sessions:

| Skill | What it does |
|-------|-------------|
| `/status` | Read shared/ state, present operational picture |
| `/writeup` | Post-engagement: produce public writeup + internal debrief |

---

## Schemas & Contracts

| Schema | Purpose |
|--------|---------|
| `HANDOFF_SCHEMA.json` | ORACLE → ELLIOT authorization gate |
| `DEPLOYMENT_NOIRE_SCHEMA.json` | ORACLE → NOIRE deployment config |
| `SOVA_REPORT_SCHEMA.json` | Recon output format |
| `WEBDIG_FINDINGS_SCHEMA.json` | Web enumeration format |
| `NOIRE_FINDINGS_SCHEMA.json` | Post-access findings format |
| `BASE_FINDINGS_SCHEMA.json` | Generic findings structure |
| `OPSEC_PROFILES.md` | LOUD / MODERATE / GHOST profiles |
| `TRADECRAFT_PLAYBOOK.md` | Shared tactical decisions |

---

## Session Resume

All agents call `memoria_get_state()` at session start for full context. State persists in `boxes/{BOX}/shared/memoria.db` across sessions — no manual checkpointing required.

---

## Requirements

- Kali Linux (or macOS for development)
- Claude Code: `npm install -g @anthropic-ai/claude-code`
- Anthropic API key: `export ANTHROPIC_API_KEY=your_key`
- Python 3 with `mcp[cli]` and `paramiko`: `pip3 install -r mcp/requirements.txt`
- Standard tools: nmap, whatweb, gobuster, ffuf, smbclient, dig, curl
- Dashboard: `pip3 install -r tools/dashboard/requirements.txt`
