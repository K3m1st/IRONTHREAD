# Adversary Agent Architecture
> HTB Offensive AI Agent Framework

---

## Overview

Two commands. That's it.

```bash
# One time only — first time setup
./install.sh

# Every new box
./new_box.sh BOXNAME 10.10.10.10
```

---

## Repository Structure

When you clone this repo, it should look like this:

```
~/Desktop/HTB/adversary-agents/
    ├── README.md
    ├── install.sh              ← run once
    ├── new_box.sh              ← run every new box
    ├── templates/
    │   ├── scout/
    │   │   ├── CLAUDE.md
    │   │   ├── SCOUT_SYSTEM_PROMPT.md
    │   │   ├── SCOUT_REPORT_TEMPLATE.md
    │   │   └── SCOUT_REPORT_SCHEMA.json
    │   └── planner/
    │       ├── CLAUDE.md
    │       └── PLANNER_SYSTEM_PROMPT.md
```

---

## One-Time Setup

Run this once after cloning. Never again.

```bash
cd ~/Desktop/HTB/adversary-agents
chmod +x install.sh new_box.sh
./install.sh
```

**What install.sh does:**
- Confirms Claude Code is installed
- Creates `~/Desktop/HTB/boxes/` as your operation base directory
- Symlinks `new_box.sh` to your PATH so you can call it from anywhere
- Verifies all template files are present
- Prints confirmation when ready

---

## Every New Box

When a new box drops, run one command from anywhere:

```bash
new_box.sh Monitored 10.10.10.10
```

**What it does:**
- Creates `~/Desktop/HTB/boxes/Monitored/`
- Builds full directory tree with scout/, planner/, shared/raw/
- Copies all agent files from templates into the right places
- Writes target IP into shared/target.txt
- Prints exactly what to do next

**Then follow the printed instructions:**

```bash
# Step 1 — Run Scout
cd ~/Desktop/HTB/boxes/Monitored/scout
claude

# Scout runs, writes reports to ../shared/
# Scout delivers handoff brief, you confirm
# Type 'exit' or Ctrl+C to close Claude Code

# Step 2 — Run Planner
cd ~/Desktop/HTB/boxes/Monitored/planner
claude
```

That's the entire workflow.

---

## Operational Flow

```
new_box.sh
    └── creates box directory
            ↓
cd scout && claude
    └── SCOUT runs full port scan
    └── SCOUT identifies all services
    └── SCOUT writes scouting_report.md + scouting_report.json to shared/
    └── SCOUT delivers handoff brief → you confirm
            ↓
cd ../planner && claude
    └── PLANNER reads shared/scouting_report.json
    └── PLANNER researches CVEs if warranted
    └── PLANNER writes shared/attack_surface.md
    └── PLANNER delivers operational brief → you confirm next move
            ↓
cd ../specialist && claude  (PLANNER tells you which one)
    └── SPECIALIST reads shared/scouting_report.json for context
    └── SPECIALIST enumerates assigned surface
    └── SPECIALIST writes findings to shared/
            ↓
cd ../planner && claude     (re-evaluate after specialist returns)
    └── PLANNER reads new findings
    └── PLANNER updates attack_surface.md
    └── PLANNER delivers updated brief → you confirm next move
            ↓
[repeat until exploitation phase]
```

---

## Session Resume

Context resets mid-operation? No problem.

Both agents check `../shared/` at startup and resume from where the last session ended. Nothing is lost.

```bash
# Resume Scout mid-scan
cd ~/Desktop/HTB/boxes/BOXNAME/scout && claude

# Resume Planner mid-evaluation
cd ~/Desktop/HTB/boxes/BOXNAME/planner && claude
```

---

## Directory Structure Per Box

After running `new_box.sh`, every box looks like this:

```
~/Desktop/HTB/boxes/{BOX_NAME}/
    ├── scout/
    │   ├── CLAUDE.md                    ← Scout orchestration
    │   ├── SCOUT_SYSTEM_PROMPT.md       ← Scout identity
    │   ├── SCOUT_REPORT_TEMPLATE.md     ← Report template
    │   └── SCOUT_REPORT_SCHEMA.json     ← JSON schema
    │
    ├── planner/
    │   ├── CLAUDE.md                    ← Planner orchestration
    │   └── PLANNER_SYSTEM_PROMPT.md     ← Planner identity
    │
    └── shared/                          ← all output lives here
        ├── target.txt                   ← box name + IP
        ├── operation.md                 ← operation status board
        ├── scouting_report.md           ← Scout output (human)
        ├── scouting_report.json         ← Scout output (machine)
        ├── attack_surface.md            ← Planner living doc
        ├── webdig_findings.md           ← WEBDIG output
        ├── smbreach_findings.md         ← SMBREACH output
        ├── dnsmap_findings.md           ← DNSMAP output
        └── raw/                         ← all raw tool output
            ├── nmap_full.txt
            └── {tool}_{port}.txt
```

---

## Updating Agent Files

When you improve an agent prompt, commit it to the repo:

```bash
cd ~/Desktop/HTB/adversary-agents
# edit templates/scout/SCOUT_SYSTEM_PROMPT.md
git add .
git commit -m "sharpen Scout identification boundary"
git push
```

Changes apply to all future boxes automatically via new_box.sh.
Existing boxes keep their original files — they are snapshots, not symlinks.

---

## Requirements

- Kali Linux
- Claude Code: `npm install -g @anthropic-ai/claude-code`
- Anthropic API key set in environment: `export ANTHROPIC_API_KEY=your_key`
- Standard Kali tools: nmap, whatweb, gobuster, ffuf, smbclient, enum4linux, dig, dnsenum

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
cd ~/Desktop/HTB/adversary-agents
./install.sh       # re-run, it will tell you what's missing
```
