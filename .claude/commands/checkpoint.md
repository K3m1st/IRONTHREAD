Save a clean operational checkpoint for session rehydration.

Write `../shared/checkpoint.md` — a structured snapshot of the current operation state, optimized for Oracle to ingest on session resume. This is NOT the attack surface document (which is append-heavy history). This is a clean, current-state-only summary designed to get a fresh Oracle session to full operational awareness in one read.

Read all files in `../shared/` to build the checkpoint, but also use your current session context — that's the whole point. You know things that aren't in the files yet.

---

## Checkpoint Structure

Write `../shared/checkpoint.md` with this exact structure:

```markdown
# Checkpoint — {BOX_NAME}
> Saved: {TIMESTAMP}
> Target: {IP}
> Operation status: {RECON / WEB ENUM / EXPLOITATION / POST-ACCESS / PRIVESC / COMPLETE}
> Current phase: {exact phase and sub-step}

## Where We Are Right Now
{2-3 sentences. What just happened, what state the operation is in, what the operator should do next. A fresh Oracle session should be able to act from this paragraph alone.}

## Confirmed Facts
{Only confirmed, HIGH confidence facts. No speculation. No leads. Just what we know for certain.}
- Target: {IP}, {hostname if known}
- Services: {port: service version — one line each}
- Technology stack: {confirmed components}
- Credentials recovered: {list or NONE}
- Access obtained: {current footholds, user levels, access methods — or NONE}

## Active Attack Paths
{Ranked. Only paths that are still live — not exhausted ones.}
1. {PATH} — Confidence: {H/M/L} — Status: {where it stands} — Next step: {what to do}
2. ...

## Exhausted Paths
{What was tried and failed. Brief — just enough to prevent re-attempt.}
- {path}: {why it's dead, in one line}

## Open Questions
{Things we don't know yet that matter for the next move.}
- {question}: {why it matters}

## Vulnerability Primitives Identified
{If any CVEs are in play, document the primitive analysis here.}
- {CVE}: primitive is {X}, delivery forms tested: {list}, untested: {list}, defenses: {what blocks what}

## Current ELLIOT State
{If ELLIOT has been deployed, summarize: scope, turns used, outcome, what he returned with.}
{If not deployed yet: "ELLIOT not yet deployed."}

## Recommended Next Action
{Single, specific next step. Not a menu — one move.}
```

---

## Rules

- Write ONLY current state. No history, no decision logs, no session timelines. That's what `attack_surface.md` is for.
- Every fact must be confirmed. Mark anything uncertain with `(UNCONFIRMED)`.
- Exhausted paths get ONE line each — just enough to prevent retry.
- Active paths must include a concrete next step, not just "investigate further."
- The "Where We Are Right Now" section must be actionable enough that a fresh session can pick up without reading anything else first.
- Overwrite the previous checkpoint — there is only ever one `checkpoint.md`. It reflects NOW, not history.

After writing `checkpoint.md`, also update `../shared/operation.md`:
- Set the `Status` line to the current phase (e.g., `RECON`, `WEB ENUM`, `EXPLOITATION`, `POST-ACCESS`, `PRIVESC`, `COMPLETE`)
- Update the Agent Status table to reflect which agents are active/pending/done
- If operation.md does not exist or has no phase tracking section, add one

Then confirm:
```
[CHECKPOINT] Saved to ../shared/checkpoint.md
Operation state updated in ../shared/operation.md
Phase: {CURRENT PHASE}
Next action: {ONE LINE}
```
