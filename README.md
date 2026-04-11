# IRONTHREAD

**Status:** Active Development | **License:** MIT | **Platform:** Kali Linux / macOS

IRONTHREAD automates penetration testing operations using three specialized AI agents that share persistent state through a SQLite database (Memoria). Each agent has a defined role, strict authorization gates, and access to purpose-built MCP tool servers. Built and validated against 10+ Hack The Box machines.

---

## Architecture

```
ORACLE (Strategy + Recon)  -->  ELLIOT (Exploitation)  -->  NOIRE (Post-Access)
        |                            |                           |
   sova-mcp                     remote-mcp                  remote-mcp
   webdig-mcp                   memoria-mcp                 memoria-mcp
   memoria-mcp
```

- **ORACLE** -- Reconnaissance, CVE research, vulnerability primitive decomposition, attack surface mapping, operator briefings. Never exploits.
- **ELLIOT** -- Scoped exploitation and privilege escalation. Operates within turn budgets and scope defined by ORACLE's handoff.
- **NOIRE** -- Post-access investigation, credential harvesting, privesc lead identification. Investigates but does not escalate.

Agents communicate through JSON authorization contracts (`handoff.json`, `deployment_noire.json`). An agent cannot proceed without a valid, signed-off contract from the previous phase. All agents share state through **Memoria**, a SQLite-backed persistent state engine.

---

## Prerequisites

Before setup, ensure you have:

- **Claude Code**: `curl -fsSL https://claude.ai/install.sh | bash`
- **Anthropic API key** or Claude subscription with OAuth: `export ANTHROPIC_API_KEY=your_key`
- **Python 3.10+**: `python3 --version`
- **Pentest tools**: nmap, whatweb, gobuster, ffuf, smbclient, dig, curl
- **For Windows targets**: NetExec, impacket, BloodHound, kerbrute, rpcclient, ldapsearch

---

## Quick Start

### One-Time Setup

```bash
git clone https://github.com/K3m1st/IRONTHREAD.git
cd IRONTHREAD
chmod +x scripts/install.sh scripts/new_box.sh
./scripts/install.sh
```

This installs Python dependencies for MCP servers and the operator dashboard.

### Start a New Operation

```bash
./scripts/new_box.sh Monitored 10.10.10.10          # Linux target
./scripts/new_box.sh Corporate 10.10.10.20 --windows # Windows target
```

Creates `boxes/Monitored/` with agent directories (oracle/, elliot/, noire/), shared state directory, copied templates, and schemas.

### Operational Flow

```bash
# 1. ORACLE -- recon, CVE research, attack surface analysis
cd boxes/Monitored/oracle && claude

# 2. ELLIOT -- exploitation (after ORACLE writes handoff.json)
cd boxes/Monitored/elliot && claude

# 3. NOIRE -- post-access investigation (after foothold established)
cd boxes/Monitored/noire && claude

# Cycle as needed: ORACLE -> ELLIOT -> NOIRE -> ORACLE
```

Each agent reads its system prompt and session instructions automatically. ORACLE briefs the operator before handing off. ELLIOT validates the handoff contract before touching anything.

---

## MCP Tool Servers

Six Python MCP servers provide programmatic tool access to agents.

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

### memoria-mcp (Persistent State Engine)
| Tool | Description |
|------|-------------|
| `memoria_get_state` | Full operational snapshot |
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

### wintools-mcp (Windows/AD Enumeration)
| Tool | Description |
|------|-------------|
| `wintools_smb_enum` | NetExec SMB enumeration |
| `wintools_rpc_enum` | rpcclient commands (enumdomusers, groups, etc.) |
| `wintools_ldap_query` | LDAP queries against domain controllers |
| `wintools_bloodhound` | BloodHound collection |
| `wintools_kerberoast` | Kerberoasting via impacket |
| `wintools_kerbrute` | Kerberos username/password bruteforce |
| + more | See `mcp/wintools/server.py` for full list |

### winrm-mcp (Windows Remote Management)
Persistent WinRM session pool, mirroring remote-mcp's pattern for Windows targets.

---

## Memoria -- Persistent State

All agents call `memoria_get_state()` at session start for full context. State persists in `boxes/{BOX}/shared/memoria.db` across sessions.

**Schema:**
- `targets` -- IP, hostname, OS, access level, flags
- `services` -- port, protocol, service name, version, banner
- `credentials` -- type, username, secret (masked by default), verification status
- `findings` -- category, severity, confidence, evidence, status
- `actions` -- full audit trail of every agent action with timestamps
- `state` -- key-value operation metadata (current phase, flags, etc.)

Credentials are masked by default (first 4 chars + `***`). Agents must explicitly request unmasked secrets.

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

## Repository Structure

```
IRONTHREAD/
├── templates/                  <- source of truth for agent prompts
│   ├── oracle/                 <- strategic planner + recon
│   ├── elliot/                 <- exploitation specialist
│   └── noire/                  <- post-access investigator
├── mcp/                        <- MCP tool servers (Python)
│   ├── sova/server.py          <- reconnaissance tools
│   ├── webdig/server.py        <- web enumeration tools
│   ├── memoria/server.py       <- persistent state engine
│   ├── remote/server.py        <- SSH session pool
│   ├── wintools/server.py      <- Windows/AD enumeration
│   ├── winrm/server.py         <- WinRM session pool
│   └── requirements.txt
├── schemas/                    <- JSON contracts + operational templates
│   ├── HANDOFF_SCHEMA.json     <- ORACLE -> ELLIOT authorization gate
│   ├── DEPLOYMENT_NOIRE_SCHEMA.json
│   ├── OPSEC_PROFILES.md       <- LOUD / MODERATE / GHOST profiles
│   ├── TRADECRAFT_PLAYBOOK.md  <- operational discipline reference
│   └── ...
├── scripts/
│   ├── install.sh              <- one-time dependency setup
│   └── new_box.sh              <- scaffold new operation
├── tools/
│   └── dashboard/              <- operator TUI dashboard
├── docs/                       <- tradecraft research
├── writeups/                   <- completed operation debriefs
├── boxes/                      <- per-box operation directories (created locally, gitignored)
└── .claude/commands/           <- operator slash commands
```

---

## Schemas and Contracts

| Schema | Purpose |
|--------|---------|
| `HANDOFF_SCHEMA.json` | ORACLE -> ELLIOT authorization gate (scope, vulnerability primitive, turn budget, opsec profile) |
| `DEPLOYMENT_NOIRE_SCHEMA.json` | ORACLE -> NOIRE deployment config (objective, access level, allowed actions) |
| `OPSEC_PROFILES.md` | Noise profiles: LOUD / MODERATE / GHOST with per-tool ratings |
| `TRADECRAFT_PLAYBOOK.md` | Post-access enumeration tiers, credential handling, command timing |
| `ATTACK_SURFACE_TEMPLATE.md` | Format for ORACLE's analytical notebook |
| `EXPLOIT_LOG_TEMPLATE.md` | Format for ELLIOT's execution narrative |
| `BRIEF_TEMPLATE.md` | Format for operator briefings |

---

## Key Design Decisions

**Vulnerability Primitive Decomposition** -- ORACLE doesn't just identify CVEs. It decomposes the underlying primitive (what the attacker controls) and enumerates all valid delivery forms before handoff. This prevents agents from fixating on a single PoC technique.

**Authorization Gates** -- Agents cannot self-authorize operations. ORACLE must write `handoff.json` with `elliot_authorized: true`. ELLIOT hard-stops if this file is missing or unauthorized. Same pattern for NOIRE.

**Turn Budgets** -- ELLIOT operates under a hard turn budget (8-40 turns based on exploit complexity). Prevents runaway exploitation attempts. At 80% budget consumed, ELLIOT reassesses strategy.

**Incremental State** -- Agents store findings and credentials to Memoria immediately on discovery, not at end of session. This enables zero-cost opportunity checks by subsequent agents.

**Noise Awareness** -- Opsec profiles (LOUD/MODERATE/GHOST) with per-tool noise ratings mapped to real IDS signatures (Suricata SIDs). Baked into agent prompts, not bolted on.

---

## Disclaimer

IRONTHREAD is designed for authorized security testing, educational purposes, and CTF/lab environments (Hack The Box, TryHackMe, etc.). Do not use this framework against systems you do not have explicit authorization to test. The authors are not responsible for misuse.

---

## License

MIT -- see [LICENSE](./LICENSE).
