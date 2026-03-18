# IRONTHREAD
> HTB Offensive AI Agent Framework

---

## Overview

Staged agent workflow with a web-first primary thread:

`SOVA -> PLANNER -> WEBDIG -> PLANNER -> ELLIOT -> NOIRE -> PLANNER -> ELLIOT`

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
├── templates/                ← source of truth for all agent files
│   ├── sova/                 ← recon agent
│   ├── planner/              ← strategic command layer
│   ├── webdig/               ← web enumeration specialist
│   ├── elliot/               ← exploit specialist
│   └── noire/                ← post-access investigation
├── schemas/                  ← JSON contracts
│   ├── DEPLOYMENT_WEBDIG_SCHEMA.json
│   ├── DEPLOYMENT_NOIRE_SCHEMA.json
│   ├── HANDOFF_SCHEMA.json
│   ├── NOIRE_FINDINGS_SCHEMA.json
│   └── WEBDIG_FINDINGS_SCHEMA.json
├── scripts/
│   ├── install.sh            ← run once
│   ├── new_box.sh            ← run every new box
│   └── validate_phase_artifacts.sh
├── docs/                     ← architecture docs
│   ├── PHASE_1_5.md
│   ├── INFRA_WIREFRAME.md
│   └── WEB_FIRST_CONTROL_STRATEGY.md
└── writeups/                 ← operation debriefs and lessons
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
- Creates `~/Desktop/HTB/boxes/` as your operation base directory
- Symlinks `new_box.sh` to your PATH so you can call it from anywhere
- Verifies all template files are present

---

## Every New Box

```bash
new_box.sh Monitored 10.10.10.10
```

**What it does:**
- Creates `~/Desktop/HTB/boxes/Monitored/`
- Builds full directory tree with sova/, planner/, webdig/, elliot/, noire/, shared/
- Copies all agent files from templates and schemas into the right places
- Writes target IP into shared/target.txt

**Then follow the printed instructions:**

```bash
# Step 1 — Sova runs recon
cd ~/Desktop/HTB/boxes/Monitored/sova && claude

# Step 2 — Planner evaluates and deploys specialists
cd ~/Desktop/HTB/boxes/Monitored/planner && claude

# Then follow the primary thread:
# Planner -> webdig -> Planner -> elliot -> noire -> Planner -> elliot
```

---

## Operational Flow

```
new_box.sh
    └── creates box directory
            ↓
cd sova && claude
    └── Sova runs full port scan and identifies all services
    └── Sova writes scouting_report.md + scouting_report.json to shared/
    └── Sova delivers handoff brief → you confirm
            ↓
cd ../planner && claude
    └── Planner reads scouting report, researches CVEs
    └── Planner writes attack_surface.md
    └── Planner delivers brief → you confirm next move
            ↓
cd ../webdig && claude
    └── WEBDIG enumerates assigned web surface within deployment scope
    └── WEBDIG writes findings to shared/
            ↓
cd ../planner && claude
    └── Planner re-evaluates, updates attack surface
    └── Planner writes handoff.json for scoped exploitation
            ↓
cd ../elliot && claude
    └── Elliot validates handoff.json, exploits within scope
    └── Elliot returns to Planner or recommends NOIRE after foothold
            ↓
cd ../noire && claude
    └── Noire investigates the host from current foothold
    └── Noire writes ranked privesc leads, returns to Planner
            ↓
cd ../planner && claude → cd ../elliot && claude
    └── Planner scopes next move → Elliot executes
```

---

## Session Resume

All agents check `../shared/` at startup and resume from the last session. Nothing is lost.

```bash
cd ~/Desktop/HTB/boxes/BOXNAME/sova && claude
cd ~/Desktop/HTB/boxes/BOXNAME/planner && claude
```

---

## Directory Structure Per Box

```
~/Desktop/HTB/boxes/{BOX_NAME}/
    ├── sova/
    │   ├── CLAUDE.md
    │   ├── SOVA_SYSTEM_PROMPT.md
    │   ├── SOVA_REPORT_TEMPLATE.md
    │   └── SOVA_REPORT_SCHEMA.json
    │
    ├── planner/
    │   ├── CLAUDE.md
    │   └── PLANNER_SYSTEM_PROMPT.md
    │
    ├── webdig/
    │   ├── CLAUDE.md
    │   └── WEBDIG_SYSTEM_PROMPT.md
    │
    ├── elliot/
    │   ├── CLAUDE.md
    │   └── ELLIOT_SYSTEM_PROMPT.md
    │
    ├── noire/
    │   ├── CLAUDE.md
    │   └── NOIRE_SYSTEM_PROMPT.md
    │
    └── shared/
        ├── target.txt
        ├── operation.md
        ├── scouting_report.md
        ├── scouting_report.json
        ├── attack_surface.md
        ├── deployment_webdig.json
        ├── deployment_noire.json
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
# edit templates/sova/SOVA_SYSTEM_PROMPT.md
git add . && git commit -m "sharpen Sova identification boundary" && git push
```

Changes apply to all future boxes via `new_box.sh`. Existing boxes keep their original files.

---

## Requirements

- Kali Linux
- Claude Code: `npm install -g @anthropic-ai/claude-code`
- Anthropic API key: `export ANTHROPIC_API_KEY=your_key`
- Standard Kali tools: nmap, whatweb, gobuster, ffuf, smbclient, enum4linux, dig, dnsenum

---

## Docs

- Architecture: [docs/INFRA_WIREFRAME.md](docs/INFRA_WIREFRAME.md)
- Control model: [docs/WEB_FIRST_CONTROL_STRATEGY.md](docs/WEB_FIRST_CONTROL_STRATEGY.md)
- Phase 1.5: [docs/PHASE_1_5.md](docs/PHASE_1_5.md)
- Contracts: `schemas/`
- Validation: `scripts/validate_phase_artifacts.sh`

---

## Troubleshooting

**new_box.sh not found**
```bash
source ~/.bashrc   # reload PATH after install
```

**Claude Code not found**
```bash
npm install -g @anthropic-ai/claude-code
```

**Templates missing**
```bash
./scripts/install.sh   # re-run, it will tell you what's missing
```
