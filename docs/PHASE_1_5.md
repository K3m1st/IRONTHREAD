# Phase 1.5
> Web-first contract hardening before MCP

---

## What Phase 1.5 Means

Phase 1.5 is the bridge between prompt-only orchestration and a real state layer.

It is not full MCP yet.

It is the stage where the web-first execution thread becomes operationally disciplined:

`SCOUT -> PLANNER -> WEBDIG -> PLANNER -> ELLIOT -> NOIRE -> PLANNER -> ELLIOT`

The point is to reduce operator burden and model drift before investing in a heavier coordination layer.

---

## Goals

- make the web thread the canonical happy path
- tighten handoffs with structured artifacts
- reduce prompt drift between specialist and exploit phases
- make phase transitions easier to validate
- create the first evaluation path for the capstone

---

## Deliverables

### 1. Consistent repo and box structure
- `templates/webdig/` is part of the standard scaffold
- docs reflect the real flow, not the older partial flow

### 2. Structured handoffs
- `scouting_report.json`
- `deployment_webdig.json`
- `webdig_findings.json`
- `handoff.json`
- `deployment_noire.json`
- `noire_findings.json`

### 3. Validation mindset
- schemas for handoff artifacts
- lightweight checks before next-phase execution

### 4. Note capture
- a dedicated place for durable notes per box
- an easy export path into Obsidian

---

## Why Not MCP First

If you jump directly to MCP before the contracts are stable, you risk moving ambiguity into a more complex system.

Phase 1.5 keeps the coordination simple enough to reason about while proving:
- what state actually matters
- which transitions need gates
- which outputs deserve formal schemas

Once those are clear, MCP becomes a scaling step instead of a guessing step.

---

## Exit Criteria

Phase 1.5 is complete when:
- a new box scaffolds `scout`, `planner`, `webdig`, and `elliot`
- the README reflects the web-first workflow
- Planner and WEBDIG have a defined structured handoff
- ELLIOT authorization is schema-backed
- important notes can be captured and exported without extra manual work
- a validator can check WEBDIG and ELLIOT artifacts before phase transitions
- NOIRE exists as the post-access investigation layer between foothold and privesc
