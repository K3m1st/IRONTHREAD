# Session Sync Plan
> Keeping Codex, Claude Code, and the Kali VM aligned during the V1 -> V2 transition

---

## Goal

Move active work toward the Phase 1.5 / V2-style workflow without losing box-specific intelligence that already exists in V1 sessions.

The priority is continuity, not a perfect reset.

---

## Current Truth Sources

Use these as the canonical references when syncing other sessions:

- [README.md](/Users/kenn3/Desktop/IRONTHREAD/README.md)
- [docs/PHASE_1_5.md](/Users/kenn3/Desktop/IRONTHREAD/docs/PHASE_1_5.md)
- [docs/INFRA_WIREFRAME.md](/Users/kenn3/Desktop/IRONTHREAD/docs/INFRA_WIREFRAME.md)
- [docs/WEB_FIRST_CONTROL_STRATEGY.md](/Users/kenn3/Desktop/IRONTHREAD/docs/WEB_FIRST_CONTROL_STRATEGY.md)
- [schemas/DEPLOYMENT_WEBDIG_SCHEMA.json](/Users/kenn3/Desktop/IRONTHREAD/schemas/DEPLOYMENT_WEBDIG_SCHEMA.json)
- [schemas/HANDOFF_SCHEMA.json](/Users/kenn3/Desktop/IRONTHREAD/schemas/HANDOFF_SCHEMA.json)
- [schemas/WEBDIG_FINDINGS_SCHEMA.json](/Users/kenn3/Desktop/IRONTHREAD/schemas/WEBDIG_FINDINGS_SCHEMA.json)

---

## Session Roles

Use a simple split so sessions do not fight each other:

- `Claude Code live box session`
  Focus: active box work, tool execution, per-box state, exploitation progress

- `Codex architecture session`
  Focus: repo structure, contracts, prompts, docs, validators, migration planning

- `Kali VM Claude session`
  Focus: syncing latest repo shape into the environment where boxes are actually being worked

---

## What Must Stay Preserved From V1

When migrating a live box from V1-style workflow to V2-style workflow, preserve:

- `shared/target.txt`
- `shared/scouting_report.md`
- `shared/scouting_report.json`
- `shared/attack_surface.md`
- any existing `shared/*_findings.md`
- `shared/exploit_log.md`
- raw outputs under `shared/raw/`
- high-signal notes that should live in `shared/notes/important_notes.md`

These are the operation memory. Do not throw them away.

---

## Sync Order

### 1. Sync repo docs and templates first

Before updating a live box, ensure the repo copy on the target machine includes:
- latest `templates/`
- latest `schemas/`
- latest `scripts/`
- latest docs needed for migration

### 2. Snapshot the live box state

Before changing any box-local agent files:
- note current box path
- confirm `shared/` contents
- confirm raw files exist
- preserve current reports and logs

### 3. Replace agent instructions, not operation memory

Update the box-local agent directories:
- `scout/`
- `planner/`
- `webdig/`
- `elliot/`

Do not replace or wipe `shared/`.

### 4. Backfill new V2-era support files

Ensure the live box now has:
- `shared/schemas/`
- `shared/notes/important_notes.md`

If WEBDIG is the active thread, add:
- `shared/deployment_webdig.json` when Planner next deploys WEBDIG

If ELLIOT is the active thread, ensure the next Planner cycle writes:
- `shared/handoff.json`

### 5. Resume from Planner

After migration, the safest re-entry point is usually Planner.

Planner can:
- read the existing `shared/` state
- rebuild current context
- issue the next scoped deployment under the new contracts

---

## Recommended Operating Rhythm

When multiple sessions are active:

1. Make repo-level changes in one place.
2. Summarize them in a short sync brief.
3. Update the live environment on Kali.
4. Resume from Planner on the box.
5. Keep notes in `shared/notes/important_notes.md`.

This minimizes drift and reduces re-explaining.

---

## Practical Rule

If you are unsure whether a file is "code" or "memory":

- `templates/`, `schemas/`, `scripts/`, docs = replaceable
- `shared/` = preserve unless intentionally superseded

That rule alone will prevent most migration mistakes.
