# Kali Migration Note
> Moving a live box from V1 workflow to current V2-style Phase 1.5 workflow

---

## Purpose

Use this when a box is already in progress on Kali and you want Claude Code there to stop using the older V1 assumptions and resume under the current web-first V2-style control model.

The goal is:
- keep the box intelligence
- replace the box-local agent instructions
- resume cleanly from Planner

---

## Do Not Delete

Preserve these box files:

- `shared/target.txt`
- `shared/scouting_report.md`
- `shared/scouting_report.json`
- `shared/attack_surface.md`
- `shared/webdig_findings.md`
- `shared/webdig_findings.json` if present
- `shared/handoff.json` if present
- `shared/exploit_log.md` if present
- `shared/raw/`

If useful notes only exist in chat or scratch files, copy them into:

- `shared/notes/important_notes.md`

---

## Migration Steps

### 1. Update the repo on Kali

Get the latest repo state onto the Kali VM so it includes:
- updated `templates/`
- `schemas/`
- `scripts/`
- new docs

### 2. Identify the live box path

Example:

```bash
~/Desktop/HTB/boxes/BOXNAME
```

### 3. Create missing V2 support directories inside the box

Make sure these exist:

```bash
mkdir -p ~/Desktop/HTB/boxes/BOXNAME/webdig
mkdir -p ~/Desktop/HTB/boxes/BOXNAME/elliot
mkdir -p ~/Desktop/HTB/boxes/BOXNAME/shared/notes
mkdir -p ~/Desktop/HTB/boxes/BOXNAME/shared/schemas
```

### 4. Copy latest agent files into the live box

Refresh:
- `scout/`
- `planner/`
- `webdig/`
- `elliot/`

from the latest repo `templates/`.

### 5. Copy shared schemas into the live box

Copy:
- `schemas/DEPLOYMENT_WEBDIG_SCHEMA.json`
- `schemas/HANDOFF_SCHEMA.json`
- `schemas/WEBDIG_FINDINGS_SCHEMA.json`

into:

```bash
shared/schemas/
```

### 6. Create `important_notes.md` if missing

If it does not exist, create:

```markdown
# Important Notes — BOXNAME
```

Then paste in:
- key pivots
- oddities
- partial conclusions
- lessons worth carrying forward

### 7. Resume from Planner

Do not jump straight back into WEBDIG or ELLIOT after migration.

Start from:

```bash
cd ~/Desktop/HTB/boxes/BOXNAME/planner && claude
```

Planner should:
- read the existing `shared/` intelligence
- rebuild the current state
- issue a fresh `deployment_webdig.json` or `handoff.json` under the new model

---

## Unplugging From V1

In practice, "unplugging from V1" means:

- stop relying on informal specialist handoffs
- stop launching WEBDIG without a scoped deployment file
- stop launching ELLIOT without a scoped handoff file
- stop treating chat memory as the source of truth

The source of truth should now be `shared/`.

---

## Re-entry Rule

If the box is mid-stream and the path is unclear:

- preserve `shared/`
- update box-local agent files
- resume from Planner

That is the safest V1 -> V2 migration pattern.
