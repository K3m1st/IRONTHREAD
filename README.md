# Adversary Agent Architecture
> HTB Offensive AI Agent Framework

---

## Overview

The repo is centered on a staged agent workflow, with a web-first path as the current primary thread:

`SCOUT -> PLANNER -> WEBDIG -> PLANNER -> ELLIOT -> NOIRE -> PLANNER -> ELLIOT`

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
    │   ├── planner/
    │   ├── webdig/
    │   ├── elliot/
    │   └── noire/
    ├── docs/
    │   ├── PHASE_1_5.md
    │   ├── OBSIDIAN_WORKFLOW.md
    │   └── WEB_FIRST_CONTROL_STRATEGY.md
    ├── schemas/
    │   ├── DEPLOYMENT_WEBDIG_SCHEMA.json
    │   ├── DEPLOYMENT_NOIRE_SCHEMA.json
    │   ├── HANDOFF_SCHEMA.json
    │   ├── NOIRE_FINDINGS_SCHEMA.json
    │   └── WEBDIG_FINDINGS_SCHEMA.json
    └── scripts/
        ├── publish_obsidian_note.sh
        └── validate_phase_artifacts.sh
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
- Builds full directory tree with scout/, planner/, webdig/, elliot/, noire/, shared/raw/, and shared/notes/
- Copies shared schemas into `shared/schemas/` for box-local validation and contract reference
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

# Then follow the current primary thread
# Planner -> webdig -> Planner -> elliot -> noire -> Planner -> elliot
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
cd ../webdig && claude
    └── WEBDIG reads shared/scouting_report.json for context
    └── WEBDIG enumerates assigned web surface
    └── WEBDIG writes findings to shared/
            ↓
cd ../planner && claude     (re-evaluate after specialist returns)
    └── PLANNER reads new findings
    └── PLANNER updates attack_surface.md
    └── PLANNER writes handoff.json for scoped exploitation
    └── PLANNER delivers updated brief → you confirm next move
            ↓
cd ../elliot && claude
    └── ELLIOT validates handoff.json
    └── ELLIOT gains initial access when path is viable
    └── ELLIOT returns to Planner or recommends NOIRE after foothold
            ↓
cd ../noire && claude
    └── NOIRE investigates the host from current foothold
    └── NOIRE writes ranked local escalation leads
    └── NOIRE returns to Planner
            ↓
cd ../planner && claude
    └── PLANNER scopes next move from NOIRE findings
            ↓
cd ../elliot && claude
    └── ELLIOT executes scoped privilege escalation as needed
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
    ├── webdig/
    │   ├── CLAUDE.md                    ← Web specialist orchestration
    │   └── WEBDIG_SYSTEM_PROMPT.md      ← Web specialist identity
    │
    ├── elliot/
    │   ├── CLAUDE.md                    ← Exploit specialist orchestration
    │   └── ELLIOT_SYSTEM_PROMPT.md      ← Exploit specialist identity
    │
    ├── noire/
    │   ├── CLAUDE.md                    ← Post-access investigation orchestration
    │   └── NOIRE_SYSTEM_PROMPT.md       ← Post-access investigation identity
    │
    └── shared/                          ← all output lives here
        ├── target.txt                   ← box name + IP
        ├── operation.md                 ← operation status board
        ├── scouting_report.md           ← Scout output (human)
        ├── scouting_report.json         ← Scout output (machine)
        ├── attack_surface.md            ← Planner living doc
        ├── deployment_webdig.json       ← Planner authorization for WEBDIG
        ├── deployment_noire.json        ← Planner authorization for NOIRE
        ├── webdig_findings.md           ← WEBDIG output
        ├── webdig_findings.json         ← WEBDIG structured output
        ├── noire_findings.md            ← NOIRE output
        ├── noire_findings.json          ← NOIRE structured output
        ├── handoff.json                 ← Planner authorization for ELLIOT
        ├── schemas/
        │   ├── DEPLOYMENT_WEBDIG_SCHEMA.json
        │   ├── DEPLOYMENT_NOIRE_SCHEMA.json
        │   ├── HANDOFF_SCHEMA.json
        │   ├── NOIRE_FINDINGS_SCHEMA.json
        │   └── WEBDIG_FINDINGS_SCHEMA.json
        ├── notes/
        │   └── important_notes.md       ← high-signal durable notes
        ├── smbreach_findings.md         ← SMBREACH output
        ├── dnsmap_findings.md           ← DNSMAP output
        └── raw/                         ← all raw tool output
            ├── nmap_full.txt
            └── {tool}_{port}.txt
```

---

## Updating Agent Files

When you improve an agent prompt or control artifact, commit it to the repo:

```bash
cd ~/Desktop/HTB/adversary-agents
# edit templates/scout/SCOUT_SYSTEM_PROMPT.md
# or docs/ / schemas/ for system controls
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

## Notes And Research

- Web-first hardening plan: [docs/PHASE_1_5.md](/Users/kenn3/Desktop/IRONTHREAD/docs/PHASE_1_5.md)
- Control model: [docs/WEB_FIRST_CONTROL_STRATEGY.md](/Users/kenn3/Desktop/IRONTHREAD/docs/WEB_FIRST_CONTROL_STRATEGY.md)
- Obsidian note flow: [docs/OBSIDIAN_WORKFLOW.md](/Users/kenn3/Desktop/IRONTHREAD/docs/OBSIDIAN_WORKFLOW.md)
- Session sync plan: [docs/SESSION_SYNC_PLAN.md](/Users/kenn3/Desktop/IRONTHREAD/docs/SESSION_SYNC_PLAN.md)
- Kali migration note: [docs/KALI_V1_TO_V2_MIGRATION.md](/Users/kenn3/Desktop/IRONTHREAD/docs/KALI_V1_TO_V2_MIGRATION.md)
- Claude sync brief: [docs/CLAUDE_SYNC_BRIEF.md](/Users/kenn3/Desktop/IRONTHREAD/docs/CLAUDE_SYNC_BRIEF.md)
- Structured contracts: `schemas/`
- Validation helper: `scripts/validate_phase_artifacts.sh`

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
