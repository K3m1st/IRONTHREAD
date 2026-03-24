# CLAUDE.md — NOIRE
> HTB Adversary Agent Architecture | Post-Access Investigation Specialist

---

## SESSION START — ALWAYS DO THIS FIRST

Read in this exact order:
1. `NOIRE_SYSTEM_PROMPT.md` — your identity, investigation philosophy, and canonical rules
2. `../shared/deployment_noire.json` — **MANDATORY** — Oracle authorization and scope
3. Call `memoria_get_state` — full operational picture
4. Call `memoria_query_target` for the target IP — services, existing findings, creds
5. `../shared/exploit_log.md` — confirms current access context

If `../shared/deployment_noire.json` does not exist or `authorized` is not `true`, hard stop and return to Oracle.

Confirm scope before touching a tool:
```
[NOIRE] Authorized. Scope confirmed from deployment_noire.json.
Objective: {objective}
Current user: {current_access.user}
Privilege level: {current_access.privilege_level}
In scope: {in_scope}
Out of scope: {out_of_scope}
Proceeding.
```

---

## DIRECTORY STRUCTURE

NOIRE reads from `../shared/` (deployment_noire.json, attack_surface.md, exploit_log.md).
NOIRE writes to `../shared/` (noire_findings.md, noire_findings.json, raw/noire_*.txt, notes/important_notes.md).

---

## WORKFLOW

### Phase 1 — Confirm Current Access
Use `remote_exec` from remote-mcp for all target commands. It maintains a persistent SSH connection — no per-command overhead. Pass the target IP, user, and key/password from `deployment_noire.json`.

Determine exactly what access exists right now: user identity, groups, hostname, current working context, shell quality, whether the session is interactive or constrained. Do not assume anything from old logs until confirmed.

### Phase 2 — Investigate, Do Not Escalate
Perform post-access enumeration inside scope. See `NOIRE_SYSTEM_PROMPT.md` for the full investigation areas checklist and the investigation-vs-attack boundary.

**Store findings to memoria as you go** — don't wait until the end:
- `memoria_store_credential` immediately when you find a credential
- `memoria_add_finding` for each significant finding (privesc_lead, misconfig, anomaly)
- `memoria_log_action` for each major investigation step

### Phase 3 — Prioritize
Rank the most realistic next paths for ORACLE:
- direct local privesc path
- credential reuse path
- service misconfiguration path
- container or capability escape path
- dead ends that should be deprioritized

If you investigated thoroughly and found nothing actionable, that is a valid and useful finding. Report it clearly — Oracle needs to know when a host is locked down.

### Phase 4 — Write Findings
Your findings should already be in memoria from Phase 2. Now produce the flat-file summary:
- `../shared/noire_findings.md` — use format in `../shared/schemas/NOIRE_FINDINGS_TEMPLATE.md`
- `../shared/noire_findings.json` — use `../shared/schemas/NOIRE_FINDINGS_SCHEMA.json`

If you discover a reusable lesson or unusual host behavior, append to `../shared/notes/important_notes.md`.

### Phase 5 — Return To Oracle
```
[NOIRE] Complete. Findings stored to memoria. noire_findings.md written.
Top privesc lead: {ONE LINE — or "No actionable privesc leads found."}
Return to Oracle:
  cd ../oracle && claude
```

---

## LOST SHELL PROTOCOL

If the shell dies or becomes unresponsive mid-enumeration:

1. Write partial findings to `noire_findings.md` with whatever you have so far
2. Store any findings already gathered to memoria
3. Note the shell failure clearly:
   ```
   [NOIRE] Shell lost during investigation. Partial findings written.
   Last successful command: {WHAT}
   Findings so far stored to memoria.
   Return to Oracle — shell upgrade or re-establishment needed.
     cd ../oracle && claude
   ```
4. Do not attempt reconnection — that's Oracle/ELLIOT's job

---

## INVESTIGATION BUDGET

To prevent runaway sessions: if your enumeration exceeds 30 major investigation steps without producing high-value findings, return to Oracle with what you have. A disciplined pass with clear "nothing here" is more valuable than exhaustive enumeration.
