# Claude Code Agent Methodology for HTB/Pentesting

A framework for using Claude Code's parallel agent architecture to efficiently attack CTF boxes and penetration testing engagements. Evolved from the Pirate box (Insane AD).

---

## Core Principle

**Split thinking from doing.** One agent reasons about attack paths while another executes live exploits. A third updates documentation. They run in parallel, don't duplicate work, and each has a clear scope. The human operator focuses on infrastructure decisions (tunnels, tool issues) and strategic pivots rather than micromanaging each command.

---

## Agent Architecture

### Phase 1: Recon & Enumeration (Sessions 1-3)

At this stage the box is unknown. Work is mostly sequential. Use a single conversation with direct tool calls — agents add overhead when you don't yet know what to parallelize.

**Pattern:** Operator-driven, single-thread
```
User: "Scan this box and enumerate"
Claude: [direct Bash/tool calls — nmap, ldap, smb, bloodhound]
```

**When to pivot to agents:** Once you have multiple independent leads to chase (e.g., "we found ADCS, ADFS, and relay opportunities").

---

### Phase 2: Multi-Vector Attack (Sessions 4-6)

You have credentials, network access, and several potential attack paths. This is where agents shine.

**Pattern: Parallel Exploration Agents**

Deploy 2-4 agents simultaneously, each focused on one attack vector:

```
Agent 1: NTLM Relay to WEB01          (HIGHEST priority)
Agent 2: Web App Investigation          (HIGH priority)
Agent 3: Config Manipulation + DRS      (MEDIUM priority)
Agent 4: Direct LDAP Object Creation    (MEDIUM priority)
```

**Key rules:**
- Each agent gets a **complete context dump** — all creds, IPs, known findings, working commands
- Each agent has a **specific task list** — not vague goals but concrete steps
- Agents are **independent** — no agent depends on another's output
- Include **working command templates** — don't make agents rediscover shell escaping, auth methods, etc.
- Set **priority** so you know which result to act on first

**Prompt template for attack agents:**
```
You are working on an HTB CTF box called "NAME" (authorized CTF).

## Your Goal
[One clear sentence]

## Key Facts
- Target IPs, domain, OS
- Available credentials (copy-paste ready)
- What's been tried and failed (prevent rework)
- Infrastructure state (tunnels, routes)

## Tasks (do all of these)
1. [Specific action with example command]
2. [Specific action with example command]
...

## Working Commands
[Tested commands the agent can use immediately]

Report back ALL findings.
```

---

### Phase 3: Privilege Escalation (Session 7+)

You've compromised a target and need to escalate. The attack surface has changed. This is where the **analysis + exploitation split** produces the best results.

**Pattern: Analyst + Operator Dual Agents**

```
Agent A: "BloodHound Graph Analyst"     (RESEARCH ONLY)
  - Enumerate ACLs, delegation, group memberships
  - Analyze attack paths theoretically
  - Check ADCS templates, GPOs, trust relationships
  - Report which paths are viable and why

Agent B: "Live Exploit Operator"         (EXECUTION ONLY)
  - Take the most promising path and execute it
  - Run the actual attacks (S4U, SPN modification, DCSync)
  - Capture flags and credentials
  - Report what worked and what failed
```

**Why this works:**
- The analyst agent can do deep LDAP/ACL enumeration without being tempted to "just try it"
- The operator agent can move fast on the most likely path without getting bogged down in research
- If the operator's path fails, the analyst has already mapped alternatives
- Neither agent blocks the other

**Prompt template for the analyst:**
```
You are an AD attack path analyst. Your job is RESEARCH ONLY —
do NOT run exploits, only enumerate and analyze.

## What We Have
[Current access, credentials, owned machines]

## Critical Known Finding
[The key ACL/permission that looks exploitable]

## Research Tasks
1. [LDAP query to run]
2. [ACL to check]
3. [Attack technique to evaluate]

Report ALL findings with analysis of which paths are viable.
```

**Prompt template for the operator:**
```
You are an AD exploitation specialist. Your job is to try
LIVE EXPLOIT ATTEMPTS.

## Goal
[Specific: "Get Domain Admin and read root.txt"]

## Key Attack Vector
[The finding to exploit]

## Exploits to Try (in priority order)
1. [Attack with full commands]
2. [Fallback attack]
3. [Alternative approach]

Report EVERYTHING — what worked, what failed, credentials obtained.
```

---

## When to Use Which Pattern

| Situation | Pattern | Why |
|-----------|---------|-----|
| Initial scan, unknown box | Single thread (no agents) | Too early to parallelize |
| Multiple independent leads | Parallel attack agents (3-4) | Each path is independent |
| One lead, need deep research | Single research agent | Focused, avoids context bloat |
| Have access, need privesc | Analyst + Operator dual | Thinking and doing in parallel |
| Cleanup and documentation | Single agent or direct | Sequential by nature |

---

## Context Management Best Practices

### What to include in every agent prompt:
1. **All credentials** — copy-paste ready, with auth method noted
2. **Network topology** — IPs, routes, tunnel state
3. **Tool quirks** — "impacket CLI broken, use Python API", "escape !& in shell"
4. **What's been tried** — prevent agents from repeating failed attempts
5. **Working command templates** — tested commands they can use immediately

### What NOT to include:
- Full notes.md dump (too long, agents lose focus)
- Exhaustive history of every failed attempt (summarize instead)
- Vague goals ("investigate this", "look around")

### Agent prompt length sweet spot:
- **Too short:** Agent wastes turns rediscovering context
- **Too long:** Agent gets confused, misses priorities
- **Right size:** 50-150 lines with clear structure (Goal → Facts → Tasks → Commands)

---

## Notes File Convention

Maintain a single `notes.md` throughout the engagement:

```markdown
## Credentials Found          ← Always current, copy-paste ready
## Attack Graph                ← Visual chain, updated as paths open/close
## Current State (Session N)   ← What just happened, what's next
## Exhaustive Tried List       ← Prevent rework across sessions
## Unexplored Angles           ← Checklist with [x] for done, [ ] for open
## Key Commands Reference      ← Working commands for quick reuse
```

Update notes after each major milestone. When launching agents, reference notes for context but don't paste the entire file — summarize the relevant sections.

---

## Session Workflow

```
1. Read notes.md + SESSION_PLAN.md (if exists)
2. Verify infrastructure (ping, auth checks)
3. Identify parallelizable work
4. Launch agents (2-4 max)
5. Triage results → update notes
6. Pivot to next phase or escalate
7. Update notes with findings
8. End of session: update notes, save memory
```

---

## Lessons from Pirate

### What worked well:
- **3 parallel agents** for Session 7 attack vectors (relay, web app, DRS) — relay agent got user.txt while the others explored dead ends. Without parallelism we'd have wasted hours on DRS before discovering relay was the path.
- **Analyst + Operator split** for DC01 escalation — analyst mapped the full ACL picture (SPN write on all computers, no RBCD write, no template access) while operator executed the SPN jacking attack. Analyst confirmed the path was correct before operator committed.
- **Complete context in agent prompts** — agents didn't need to ask questions or rediscover creds/topology.
- **Priority ordering** — highest priority agent (relay) got the breakthrough. Lower priority agents (DRS, device registration) correctly identified dead ends.

### What to improve:
- **Earlier agent use** — sessions 1-5 were mostly single-threaded. Could have parallelized sooner (e.g., ADCS + relay + ADFS investigation simultaneously).
- **Notes updates during agents** — update notes immediately after agent results, not as a batch at the end.
- **Agent scope creep** — some agents tried too many things. Better to give each a tight 3-5 step task list.
- **Infrastructure checks first** — always verify tunnel/auth before launching agents, or they waste turns on connectivity issues.

---

## Template: Session Start

```
Read notes and plan files, then:

1. Verify infrastructure
   - Ping targets
   - Test auth (SMB/LDAP/WinRM)
   - Check tunnel routes

2. Review open angles from notes.md [ ] checklist

3. Group into independent workstreams

4. Launch parallel agents with full context

5. Triage results, update notes, pivot
```

## Template: Agent Launch Block

```
Launch these N agents IN PARALLEL:

Agent 1: [NAME] — Priority: [HIGH/MED/LOW]
  Goal: [one sentence]
  Task: [3-5 concrete steps]

Agent 2: [NAME] — Priority: [HIGH/MED/LOW]
  Goal: [one sentence]
  Task: [3-5 concrete steps]

[shared context block: creds, IPs, tools, known-dead-ends]
```
