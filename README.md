# IRONTHREAD
> HTB Offensive AI Agent Framework

---

## Overview

Two-agent architecture with MCP tool servers:

```
Oracle (recon + analysis + enumeration via MCP) → Elliot (exploitation)
```

Oracle handles reconnaissance (sova-mcp), web enumeration (webdig-mcp), strategic analysis, CVE research, post-access investigation (noire-mcp), and operator briefings. Elliot handles scoped exploitation.

```bash
# One time only — first time setup
./scripts/install.sh

# Every new box
./scripts/new_box.sh BOXNAME 10.10.10.10
```

---

## Repository Structure

```
IRONTHREAD/
├── README.md
├── templates/               ← source of truth for agent files
│   ├── oracle/              ← strategic command + MCP tools
│   └── elliot/              ← exploit specialist
├── mcp/                     ← MCP tool servers
│   ├── sova/server.py       ← reconnaissance tools
│   ├── webdig/server.py     ← web enumeration tools
│   ├── noire/server.py      ← post-access investigation tools
│   └── requirements.txt     ← mcp[cli]
├── schemas/                 ← JSON contracts
│   ├── HANDOFF_SCHEMA.json
│   ├── SOVA_REPORT_SCHEMA.json
│   ├── WEBDIG_FINDINGS_SCHEMA.json
│   └── NOIRE_FINDINGS_SCHEMA.json
├── scripts/
│   ├── install.sh           ← run once
│   ├── new_box.sh           ← run every new box
│   └── validate_phase_artifacts.sh
├── .claude/commands/         ← operator skills
│   ├── newbox.md            ← /newbox — create new box
│   ├── status.md            ← /status — operational picture
│   ├── findings.md          ← /findings — consolidated findings
│   ├── checkpoint.md        ← /checkpoint — save state for session rehydration
│   └── writeup.md           ← /writeup — public writeup + internal debrief
├── docs/                    ← architecture docs
│   ├── PHASE_1_5.md
│   ├── INFRA_WIREFRAME.md
│   └── WEB_FIRST_CONTROL_STRATEGY.md
└── writeups/                ← operation debriefs and lessons
```

---

## One-Time Setup

Run this once after cloning.

```bash
cd ~/IRONTHREAD
chmod +x scripts/install.sh scripts/new_box.sh
./scripts/install.sh
```

**What install.sh does:**
- Confirms Claude Code is installed
- Installs MCP Python dependencies (`pip3 install mcp[cli]`)
- Creates `~/Desktop/HTB/boxes/` as your operation base directory
- Adds `new_box` alias to your shell
- Verifies all template and MCP files are present

---

## Every New Box

```bash
new_box Monitored 10.10.10.10
```

**What it does:**
- Creates `~/Desktop/HTB/boxes/Monitored/`
- Builds directory tree with oracle/, elliot/, shared/
- Copies agent templates and schemas
- Configures MCP servers in oracle/.claude/settings.local.json
- Writes target IP into shared/target.txt

**Then follow the printed instructions:**

```bash
# Step 1 — Oracle handles everything: recon, analysis, web enum, post-access
cd ~/Desktop/HTB/boxes/Monitored/oracle && claude

# Step 2 — When Oracle writes handoff.json, launch Elliot
cd ~/Desktop/HTB/boxes/Monitored/elliot && claude

# Flow: Oracle → Elliot → Oracle → Elliot (as needed)
```

---

## Operational Flow

```
new_box.sh
    └── creates box directory with MCP config
            ↓
cd oracle && claude
    └── Oracle runs sova-mcp tools: full port scan, service identification
    └── Oracle writes scouting_report.md/json to shared/
    └── Oracle researches CVEs, builds attack_surface.md
    └── Oracle delivers brief → you confirm next move
            ↓
    └── Oracle runs webdig-mcp tools: dir busting, vhost fuzzing, JS review
    └── Oracle writes webdig_findings.md/json to shared/
    └── Oracle re-evaluates, updates attack surface
    └── Oracle writes handoff.json for scoped exploitation
    └── Oracle delivers brief → you confirm
            ↓
cd ../elliot && claude
    └── Elliot validates handoff.json, exploits within scope
    └── Elliot returns to Oracle or recommends post-access investigation
            ↓
cd ../oracle && claude
    └── Oracle runs noire-mcp tools: system profile, sudo, SUID, crons, configs
    └── Oracle writes noire_findings.md/json, ranks privesc leads
    └── Oracle writes new handoff.json for privesc
            ↓
cd ../elliot && claude
    └── Elliot executes privesc within scope
```

---

## MCP Tool Servers

Oracle uses three MCP servers for tool execution:

### sova-mcp (Reconnaissance)
- `sova_full_scan` — nmap -p- -sC -sV -T4
- `sova_whatweb` — whatweb -a 3
- `sova_banner_grab` — nmap -sV on specific port
- `sova_zone_transfer` — dig axfr
- `sova_null_session` — smbclient -N -L
- `sova_anon_ftp` — anonymous FTP test

### webdig-mcp (Web Enumeration)
- `webdig_dir_bust` — gobuster dir
- `webdig_vhost_fuzz` — ffuf Host header fuzzing
- `webdig_whatweb` — whatweb -a 3
- `webdig_curl` — curl with full control
- `webdig_js_review` — JS endpoint/secret extraction

### noire-mcp (Post-Access Investigation)
- `noire_system_profile` — uname, id, os-release
- `noire_sudo_check` — sudo -l
- `noire_suid_scan` — find SUID/SGID
- `noire_cron_inspect` — crontab, cron dirs, timers
- `noire_service_enum` — ps, systemctl, listening ports
- `noire_config_harvest` — read specific config files
- `noire_writable_paths` — find writable files

All noire tools execute on the target via SSH (`execution_context` parameter).

---

## Session Resume

Both agents check `../shared/` at startup and resume from the last session. Oracle reads `checkpoint.md` first (if it exists) for fast rehydration, then `attack_surface.md` for full history.

Before ending an Oracle session, run `/checkpoint` to save a clean state snapshot. This makes the next session resume instant instead of re-parsing the full attack surface history.

```bash
# Inside Oracle session, before ending:
/checkpoint

# Next session:
cd ~/Desktop/HTB/boxes/BOXNAME/oracle && claude
cd ~/Desktop/HTB/boxes/BOXNAME/elliot && claude
```

---

## Directory Structure Per Box

```
~/Desktop/HTB/boxes/{BOX_NAME}/
    ├── oracle/
    │   ├── CLAUDE.md
    │   ├── ORACLE_SYSTEM_PROMPT.md
    │   └── .claude/settings.local.json  ← MCP server config
    │
    ├── elliot/
    │   ├── CLAUDE.md
    │   └── ELLIOT_SYSTEM_PROMPT.md
    │
    └── shared/
        ├── target.txt
        ├── operation.md
        ├── checkpoint.md              ← clean state snapshot for session rehydration
        ├── scouting_report.md / .json
        ├── attack_surface.md
        ├── webdig_findings.md / .json
        ├── noire_findings.md / .json
        ├── handoff.json
        ├── exploit_log.md
        ├── schemas/
        ├── notes/important_notes.md
        └── raw/
```

---

## Updating Agent Files

Edit templates directly — they are the single source of truth:

```bash
# edit templates/oracle/ORACLE_SYSTEM_PROMPT.md
git add . && git commit -m "update Oracle reasoning framework" && git push
```

Changes apply to all future boxes via `new_box.sh`. Existing boxes keep their original files.

---

## Requirements

- Kali Linux (or macOS for development)
- Claude Code: `npm install -g @anthropic-ai/claude-code`
- Anthropic API key: `export ANTHROPIC_API_KEY=your_key`
- Python 3 with mcp[cli]: `pip3 install mcp[cli]`
- Standard tools: nmap, whatweb, gobuster, ffuf, smbclient, dig, curl

---

## Operator Skills

Slash commands available inside any Claude Code session in the repo:

| Skill | What it does |
|-------|-------------|
| `/newbox` | Create a new box operation (wraps `new_box.sh`) |
| `/status` | Read shared/ state, present operational picture |
| `/findings` | Consolidated summary of all findings across phases |
| `/checkpoint` | Save clean state snapshot to `checkpoint.md` for session rehydration |
| `/writeup` | Post-engagement: produce public writeup + internal debrief |

---

## Docs

- Architecture: [docs/INFRA_WIREFRAME.md](docs/INFRA_WIREFRAME.md)
- Control model: [docs/WEB_FIRST_CONTROL_STRATEGY.md](docs/WEB_FIRST_CONTROL_STRATEGY.md)
- Phase 1.5: [docs/PHASE_1_5.md](docs/PHASE_1_5.md)
- Contracts: `schemas/`
- Validation: `scripts/validate_phase_artifacts.sh`
