# Phase 1.5
> Web-first contract hardening — completed, now superseded by Phase 3

---

## What Phase 1.5 Was

Phase 1.5 was the bridge between prompt-only orchestration and a real state layer.

It established the web-first execution thread as operationally disciplined:

`SOVA -> ORACLE -> WEBDIG -> ORACLE -> ELLIOT -> NOIRE -> ORACLE -> ELLIOT`

The point was to reduce operator burden and model drift before investing in MCP.

---

## Status: COMPLETE — Superseded by Phase 3

Phase 1.5 exit criteria were met, and the architecture has since been refactored in Phase 3:

- **Phase 3 collapsed 5 agent sessions to 2** (Oracle + Elliot)
- SOVA, WEBDIG, and NOIRE became MCP tool servers (`mcp/sova/`, `mcp/webdig/`, `mcp/noire/`)
- PLANNER was renamed to ORACLE and absorbed the reasoning from all three specialist agents
- Deployment contracts (`deployment_webdig.json`, `deployment_noire.json`) are eliminated — Oracle calls tools directly
- `handoff.json` remains as the ELLIOT authorization gate

---

## Original Goals (all met)

- make the web thread the canonical happy path
- tighten handoffs with structured artifacts
- reduce prompt drift between specialist and exploit phases
- make phase transitions easier to validate
- create the first evaluation path for the capstone

---

## Original Deliverables (all delivered, some now superseded)

### 1. Consistent repo and box structure
- ~~`templates/webdig/` is part of the standard scaffold~~ → absorbed into Oracle + webdig-mcp
- docs reflect the real flow

### 2. Structured handoffs
- `scouting_report.json` — Oracle writes this directly via sova-mcp
- ~~`deployment_webdig.json`~~ → eliminated (Oracle calls webdig-mcp directly)
- `webdig_findings.json` — Oracle writes this directly via webdig-mcp
- `handoff.json` — still the ELLIOT authorization gate
- ~~`deployment_noire.json`~~ → eliminated (Oracle calls noire-mcp directly)
- `noire_findings.json` — Oracle writes this directly via noire-mcp

### 3. Validation mindset
- schemas for handoff artifacts
- lightweight checks via `validate_phase_artifacts.sh`

### 4. Note capture
- `shared/notes/important_notes.md` per box
- Obsidian export via `publish_obsidian_note.sh`

---

## Why Phase 1.5 Came Before MCP

If you jump directly to MCP before the contracts are stable, you risk moving ambiguity into a more complex system.

Phase 1.5 proved:
- what state actually matters
- which transitions need gates
- which outputs deserve formal schemas

Phase 3 then used MCP as a scaling step — collapsing 3 agent sessions into tool servers while preserving the contracts that Phase 1.5 established.
