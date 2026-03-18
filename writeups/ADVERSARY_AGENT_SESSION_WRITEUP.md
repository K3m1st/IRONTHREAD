# Adversary Agent Architecture — Session Writeup
> Date: 2026-03-15
> Status: Active Development
> Author: Ken + Claude

---

## Overview

This session was a full design, build, and first live deployment of a multi-agent offensive security framework for HackTheBox. Starting from a concept ("I want to test agents on HTB boxes before OSAI+") and ending with Sova, Planner, WEBDIG, and ELLIOT running live on a real box. The architecture proved itself — and its gaps — in the same session.

---

## What Was Built

### Agent Roster

| Agent | Role | Status |
|-------|------|--------|
| SOVA | Initial recon — full port scan, service identification, fingerprinting | ✅ Complete v1 |
| PLANNER | Strategic command — ingests all intel, CVE research, briefs operator, deploys agents | ✅ Complete v2 |
| WEBDIG | Web specialist — deep directory enum, vhost fuzzing, git dumping, tech fingerprinting | ✅ Complete v1 |
| ELLIOT | Exploit specialist — scoped execution, validated exploitation, access milestone reporting | ✅ Complete v2 |
| SMBREACH | SMB/file share enumeration | ⬜ Pending |
| DNSMAP | DNS zone transfers, subdomain discovery | ⬜ Pending |

### Supporting Infrastructure

| File | Purpose | Status |
|------|---------|--------|
| `new_box.sh` | Spins up full operation directory in one command | ✅ Complete |
| `install.sh` | One-time setup — verifies deps, creates boxes dir, adds alias | ✅ Complete |
| `README.md` | Full deployment and workflow documentation | ✅ Complete |
| `handoff.json` | Structured state file — enforces agent sequencing | ✅ Schema defined |

### Directory Structure Per Box
```
~/Desktop/HTB/boxes/{BOX_NAME}/
    ├── sova/         ← CLAUDE.md + SOVA_SYSTEM_PROMPT.md
    ├── planner/      ← CLAUDE.md + PLANNER_SYSTEM_PROMPT.md
    ├── elliot/       ← CLAUDE.md + ELLIOT_SYSTEM_PROMPT.md
    └── shared/       ← all intelligence, all output, all agent handoffs
        ├── target.txt
        ├── operation.md
        ├── scouting_report.md
        ├── scouting_report.json
        ├── attack_surface.md
        ├── exploit_log.md
        ├── handoff.json
        └── raw/
```

---

## Key Architectural Decisions Made This Session

### 1. Identification vs Enumeration Boundary
Sova's scope was a critical design debate. Resolution: Sova identifies, specialists enumerate. Sova touches every service once to confirm identity and exposure level — then stops. The line is drawn by service type in a boundary table in Sova's system prompt.

### 2. Specialist Squad Model
Moved away from one agent trying to do everything. Sova recommends which specialists to deploy based on what it finds. Each specialist has one domain and does it deeply.

### 3. Loose Leash on Reasoning
Step 2 in Sova's CLAUDE.md deliberately has no hardcoded tool list. Sova reasons about what nmap surfaces and decides what to run next — documented, evidence-based decisions. This reduces variance while preserving adaptive intelligence.

### 4. Sova → Planner as Primary Focus
Mid-session decision: de-prioritize specialist build-out, focus on Sova and Planner as the command layer. The specialists are infantry — Sova and Planner are the architecture that makes the operation coherent.

### 5. Planner as Strategic Advisor
Planner never self-authorizes. It briefs, recommends a single move, and waits for operator confirmation. Executive summary first, full detail below. CVE research is complete before anything surfaces to the operator.

### 6. ELLIOT Scope Enforcement (v2)
After the VariaType live run revealed ELLIOT going rogue — burning 300k tokens on improvised exploit attempts outside his briefed scope — v2 adds:
- Explicit scope boundary from Planner's deployment order
- Hard stop at 3 failed attempts on a single path
- `[NEW SURFACE]` status code for out-of-scope discoveries
- Return to Planner loop — new surface triggers specialist deployment, not ELLIOT improvisation

### 7. Web Search as Operational Intelligence
Models operating purely on training data are like operators who haven't Googled since their training cutoff. Web search activation points added to both Planner and ELLIOT:
- Planner searches on every confirmed version number, every CVE research phase
- ELLIOT searches before running any exploit, on every unexpected response, after every 3-attempt wall
- Search results are documented in operation logs — intelligence is traceable

### 8. handoff.json as Operation State
The mechanism that solves the operator-as-orchestrator problem. Planner writes a structured handoff file before deploying ELLIOT. ELLIOT reads it to confirm scope, authorization, and context files. If `elliot_authorized` is not `true`, ELLIOT does not deploy. This is the precursor to full MCP state management.

---

## Live Operation: VariaType (HTB)

### What Worked
- Sova produced a clean, complete scouting report on first run
- WEBDIG found the portal vhost, dumped the exposed .git, extracted credentials from git history, and mapped every post-auth endpoint — exceptional output
- Planner built a high-quality attack surface document with ranked attack paths
- The overall intelligence picture was more than sufficient for exploitation

### What Failed
- ELLIOT deployed before Planner processed WEBDIG's findings — operation.md showed both as PENDING when ELLIOT was invoked
- Without a validated scope from Planner, ELLIOT improvised — started the right path (portal auth with gitbot creds) but had no stop conditions, no scope boundary, and no structured handoff to fall back on
- ~300k tokens burned on rogue exploration instead of scoped execution
- Root cause: no enforced sequencing between WEBDIG → Planner re-evaluation → ELLIOT deployment

### Lessons Applied
- handoff.json schema designed to enforce sequencing
- ELLIOT v2 scope enforcement and stop conditions added
- Planner v2 web search protocol added
- Three-attempt hard limit added to ELLIOT

---

## Architectural Gap: Operator as Orchestrator

The biggest outstanding problem: the operator is still manually managing the pipeline. Knowing which agent to invoke next, verifying operation.md reflects reality, ensuring Planner processed specialist output before ELLIOT deploys — all of this mental overhead is on the operator.

handoff.json is a partial fix. The real fix is MCP.

---

## Next Steps (Phased)

### Phase 1 — Tighten Current Agents (immediate)
**Goal:** Agents enforce their own sequencing. Operator confirms moves, doesn't manage them.

- [ ] Add handoff.json write step to Planner CLAUDE.md — Planner writes it before every ELLIOT deployment
- [ ] Update ELLIOT CLAUDE.md to read and validate handoff.json at session start
- [ ] Add `[NEW SURFACE]` handling to ELLIOT CLAUDE.md — logs, continues objective, hands off on completion
- [ ] Update new_box.sh to include elliot/ directory and template copy
- [ ] Test updated ELLIOT on VariaType — complete the portal LFI path with scoped deployment
- [ ] Commit all v2 agent files to repo

---

### Phase 2 — MCP State Layer (next major build)
**Goal:** Replace flat files and manual tracking with a proper state store. Agents read and write operation state atomically. No more stale operation.md.

**What MCP solves:**
- Single source of truth for operation state — not scattered across multiple markdown files
- Atomic reads and writes — no agent reads partial state
- Enforced sequencing — Planner cannot mark ELLIOT authorized until specialist findings are ingested
- Session resume is automatic — agents query state, not parse markdown
- Operator dashboard — one read of MCP state shows exactly where the operation is

**MCP servers to implement:**
- Filesystem MCP server — agents read/write shared intelligence files
- State MCP server — operation state, agent status, sequencing gates
- (Future) Memory MCP server — persistent context across boxes, pattern recognition

**Build order:**
1. Set up Claude Code MCP filesystem server on M4 Pro
2. Define operation state schema in MCP
3. Migrate handoff.json to MCP state
4. Migrate attack_surface.md updates to MCP writes
5. Test full Sova → Planner → Specialist → ELLIOT loop via MCP
6. Decommission flat file handoffs once MCP is stable

---

### Phase 3 — Conductor Agent (post-MCP)
**Goal:** Single agent manages the operation pipeline. Operator approves moves, doesn't manage sequencing.

The Conductor reads MCP state, determines current operation phase, tells operator which agent to invoke next and with what context, and blocks invalid transitions. ELLIOT cannot deploy if Planner re-evaluation is pending. Specialists cannot deploy if Sova is not marked COMPLETE.

Operator workflow becomes:
```bash
cd ~/Desktop/HTB/boxes/BOXNAME/conductor && claude
# "What should I do next?"
# Conductor reads state, tells you exactly one thing to do
# You confirm
# Conductor writes next deployment order to MCP
# cd to appropriate agent directory, fire
```

---

### Phase 4 — Remaining Specialists
**Goal:** Complete the squad.

- [ ] SMBREACH — SMB/file share specialist
- [ ] DNSMAP — DNS zone transfer and subdomain specialist
- [ ] Both follow same pattern as WEBDIG — context-first, adaptive, writes to shared/

---

### Phase 5 — OSAI+ Preparation Integration
**Goal:** By exam time, a proven playbook backed by a working agent system.

- Each HTB box is an integration test — does the architecture handle this attack surface?
- Gaps discovered on boxes drive agent improvements
- By May (OSAI+ target): documented methodology + working agents for recon, planning, and initial exploitation
- Exam: agents running recon and enumeration autonomously while you focus on exploitation decisions

---

## Open Questions

- Should WEBDIG get a deeper behavioral analysis phase — mapping how the application actually processes input, not just what endpoints exist? (The VariaType audit framing suggests yes)
- Should the Planner re-evaluation cycle be mandatory before any ELLIOT session, or only when new specialist findings exist?
- At what point does ELLIOT hand to a post-exploitation agent vs continuing himself?

---

## Repository State

```
~/Desktop/HTB/adversary-agents/
    ├── README.md
    ├── install.sh
    ├── new_box.sh
    └── templates/
        ├── sova/
        │   ├── CLAUDE.md                  (v1)
        │   ├── SOVA_SYSTEM_PROMPT.md     (v1)
        │   ├── SOVA_REPORT_TEMPLATE.md   (v1)
        │   └── SOVA_REPORT_SCHEMA.json   (v1)
        ├── planner/
        │   ├── CLAUDE.md                  (v2)
        │   └── PLANNER_SYSTEM_PROMPT.md   (v2 — web search added)
        └── elliot/
            ├── CLAUDE.md                  (v2)
            └── ELLIOT_SYSTEM_PROMPT.md    (v2 — scope + stop conditions + research)
```

---

## Carry Into Next Claude Code Session

When starting a new session, paste this as context:

```
I am building a multi-agent offensive security framework for HackTheBox 
called the Adversary Agent Architecture. The repo lives at 
~/Desktop/HTB/adversary-agents/. Current agents: SOVA (recon), 
PLANNER (strategy), WEBDIG (web specialist), ELLIOT (exploit specialist).

Current phase: Phase 1 — tighten agent sequencing via handoff.json, 
then Phase 2 — MCP state layer to replace manual orchestration.

Read the session writeup at: ADVERSARY_AGENT_SESSION_WRITEUP.md
Read current agent files in: templates/
```
