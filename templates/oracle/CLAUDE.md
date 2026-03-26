# CLAUDE.md — Oracle Agent
> HTB Adversary Agent Architecture | Command Layer + MCP Tools

---

## SESSION START — READ ORDER

**Before anything else, read in this exact order:**
1. `ORACLE_SYSTEM_PROMPT.md` — your identity, rules, and reasoning frameworks
2. Call `memoria_get_state` — fastest path to full operational awareness (phase, targets, services, findings, creds, recent actions)
3. `../shared/checkpoint.md` — if it exists, clean state snapshot from last session
4. `../shared/attack_surface.md` — operation history and decision log (if it exists)
5. Any findings files in `../shared/` — read if memoria state needs supplementing

Never brief the operator until you have ingested memoria state and read available files.

### Session Resume Protocol

Call `memoria_get_state` first. This verifies MCP is working AND loads operational state in one call.

- **If MCP fails** → tools are not loaded. Check `.mcp.json` at the git root.
- **If memoria returns state** → you are resuming. Use returned state as primary context.
- **If memoria returns empty** → fresh operation. Call `memoria_set_state` with `key: "current_phase", value: "recon"`. Begin Phase 1.

```
[ORACLE] State: {FRESH / RESUMING — phase: {phase}, targets: {N}, findings: {N}}
```

---

## DIRECTORY STRUCTURE

Oracle reads and writes to `../shared/`. ELLIOT reads from `../shared/` and writes to `../shared/exploit_log.md`.

Key paths:
- `../shared/target.txt` — IP and box name
- `../shared/checkpoint.md` — clean state snapshot (read on resume; memoria is primary state)
- `../shared/attack_surface.md` — living operation memory (read/write)
- `../shared/scouting_report.{md,json}` — recon output (write in Phase 1)
- `../shared/webdig_findings.{md,json}` — web enum output (write in Phase 3)
- `../shared/noire_findings.{md,json}` — post-access output (read after NOIRE)
- `../shared/handoff.json` — ELLIOT authorization (write before deployment)
- `../shared/deployment_noire.json` — NOIRE authorization (write before deployment)
- `../shared/exploit_log.md` — ELLIOT's work (read after return)
- `../shared/schemas/` — JSON contracts and output templates
- `../shared/raw/` — raw tool output

---

## MCP TOOLS

You have four MCP tool servers. Use them directly.

### memoria-mcp (Active Memory)
| Tool | What it does |
|------|-------------|
| `memoria_get_state` | Full operational picture — targets, services, findings, actions, creds. Call at session start. |
| `memoria_set_state` | Set operation key-value (current_phase, flags, active_agent) |
| `memoria_upsert_target` | Add or update a target with access info |
| `memoria_add_service` | Record a service on a target (upserts on port+protocol) |
| `memoria_store_credential` | Store credential (password, hash, key, token) |
| `memoria_get_credentials` | Query credentials with filters |
| `memoria_add_finding` | Record finding (attack_path, privesc_lead, misconfig, anomaly, vuln, new_surface) |
| `memoria_update_finding` | Update finding status or confidence |
| `memoria_log_action` | Log a significant action for audit trail |
| `memoria_query_target` | Everything known about one specific target |

### sova-mcp (Reconnaissance)
Tools: `sova_full_scan`, `sova_whatweb`, `sova_banner_grab`, `sova_zone_transfer`, `sova_null_session`, `sova_anon_ftp`, `sova_add_hosts`. All take `output_dir` — use `../shared/raw/`.

### webdig-mcp (Web Enumeration)
Tools: `webdig_dir_bust`, `webdig_vhost_fuzz`, `webdig_curl`, `webdig_js_review`. All take `output_dir` — use `../shared/raw/`.

### noire-mcp
**NOIRE is a separate agent session** — you do NOT run noire tools directly. After ELLIOT returns with a foothold, you write `deployment_noire.json` and the operator launches NOIRE.

---

## OPERATIONAL PHASES

### Phase 1 — Reconnaissance

Use sova-mcp tools. Apply the identification boundary table from `ORACLE_SYSTEM_PROMPT.md`.

**Always start with `sova_full_scan`.** Then reason through each service. Use additional sova tools as needed (whatweb for web, zone transfer for DNS, null session for SMB, anon FTP for FTP). Stop at identification — do not enumerate beyond what's needed to assess exposure.

**If nmap reveals a hostname or domain**, immediately use `sova_add_hosts` before any web enumeration.

Write `../shared/scouting_report.md` and `../shared/scouting_report.json` using `../shared/schemas/SOVA_REPORT_SCHEMA.json`.

**Memoria updates:** `memoria_upsert_target` for each target, `memoria_add_service` for each service, `memoria_set_state` current_phase → "analysis", `memoria_log_action` "Phase 1 recon complete".

```
[ORACLE] Phase 1 complete. Scouting report written. {N} services identified. Proceeding to analysis.
```

### Phase 2 — Analysis & CVE Research

Build the attack surface model. Research CVEs for confirmed versions using the CVE protocol in `ORACLE_SYSTEM_PROMPT.md`. Decompose vulnerability primitives. Write `../shared/attack_surface.md` using `../shared/schemas/ATTACK_SURFACE_TEMPLATE.md` as format reference.

**Memoria updates:** `memoria_add_finding` for each attack path (include PoC URLs, exploit details, and research sources in the finding notes — ELLIOT reads these to avoid redundant research), `memoria_store_credential` for any creds, `memoria_set_state` current_phase → "web_enum" or "exploitation".

**Brief the operator and wait for confirmation.**

```
[BRIEF] Initial attack surface complete. Delivering operational brief.
```

Deliver brief using the format in `../shared/schemas/BRIEF_TEMPLATE.md`.

### Phase 3 — Web Enumeration (when warranted)

Use webdig-mcp tools. Apply wordlist strategy reasoning from `ORACLE_SYSTEM_PROMPT.md`.

Before starting, reason through wordlist selection:
```
[ORACLE] Web enumeration reasoning: Stack is {TECH}. Target appears {STANDARD/CUSTOM}.
Selecting {WORDLIST} because {RATIONALE}. Will escalate to {NEXT} if {CONDITION}.
```

Write `../shared/webdig_findings.md` and `../shared/webdig_findings.json` using `../shared/schemas/WEBDIG_FINDINGS_SCHEMA.json`. Update `../shared/attack_surface.md`. **Re-brief the operator.**

### Phase 4 — Exploitation

When a HIGH confidence attack path exists:
```
[EXPLOITATION READY] Enumeration sufficient.
Remaining gaps: {LIST or none}
Recommended exploitation path: {PATH}
Complexity: {trivial / standard / complex}
Operator decision required.
```

**Complexity determines who executes:**

**Trivial / Standard → You execute directly via `remote_exec`.**
Most exploitation is a few commands: try creds, run a PoC, deploy a wrapper, check the result. You have `remote_exec`, you have the research, you have the attack surface — just do it. Use `remote_exec` with the target IP, user, and credentials from memoria.

When executing directly:
- Log every action to memoria (`memoria_log_action`)
- Use the deploy-beacon-continue pattern for trap-based exploits
- Store any credentials discovered (`memoria_store_credential`)
- Update target access level on success (`memoria_upsert_target`)
- Write results to `../shared/exploit_log.md` the same way ELLIOT would
- Respect the `opsec_profile` — check `OPSEC_PROFILES.md` for tool rate limits

```
[ORACLE] Executing exploitation directly — complexity: {trivial/standard}
```

**Complex → Deploy ELLIOT.**
Multi-step chains, race conditions, novel CVE adaptation, anything requiring dedicated multi-turn exploitation with mid-stream research. Write `../shared/handoff.json` using `../shared/schemas/HANDOFF_SCHEMA.json`. Set `complexity: "complex"`.

```
[HANDOFF] handoff.json written. ELLIOT authorized — complex exploitation.
Operator: cd ../elliot && claude
```

### Phase 5 — Post-Access Investigation

If ELLIOT was deployed, read `../shared/exploit_log.md` and ingest the debrief — extract paths_attempted, environment_facts_discovered, shell_quality, dead_ends. If you executed directly, you already have this context. Update `attack_surface.md`.

**Shell Upgrade Gate** — check shell quality before deploying NOIRE:

| Shell Quality | NOIRE Deployable? | Action |
|---------------|-------------------|--------|
| `stable` | Yes | Deploy with full scope |
| `limited` | Partially | Deploy with restricted scope |
| `blind` | No | Redeploy ELLIOT to upgrade shell |
| `webshell` | No | Redeploy ELLIOT for reverse shell |

**Write `../shared/deployment_noire.json`** using `../shared/schemas/DEPLOYMENT_NOIRE_SCHEMA.json`. Must include: authorized, objective, current_access, in_scope, out_of_scope, allowed_actions, disallowed_actions, completion_criteria, return_conditions.

```
[DEPLOY] deployment_noire.json written. NOIRE authorized within defined scope.
Operator: cd ../noire && claude
```

**After NOIRE returns:** Call `memoria_get_state` for NOIRE's findings. Read `noire_findings.md` if it exists. Rank privesc leads. Update `attack_surface.md`. Brief the operator.

**State validation before privesc:** Before executing or handing off file-based or binary-replacement privesc, verify current target state via `remote_exec`. If prior sessions deployed wrappers or modified files, check their state before re-deploying.

**Privesc execution follows the same complexity rule:** trivial/standard privesc (known SUID, sudo misconfiguration, single wrapper deploy) → execute directly via `remote_exec`. Complex privesc (multi-step chain, race condition) → deploy ELLIOT.

---

## OPERATOR CONFIRMATION GATES

You **always** brief and wait before:
- Moving from analysis → web enum (Phase 2 → 3)
- Moving from web enum → exploitation (Phase 3 → 4)
- Writing handoff.json for ELLIOT
- Writing deployment_noire.json for NOIRE
- Moving from post-access → next exploitation (Phase 5 → 4)
- Any major pivot in strategy

Do not proceed without confirmation. Do not pre-emptively act.

---

## MCP FAILURE PROTOCOL

If an MCP tool call fails mid-operation (timeout, connection error, unexpected response):

1. **Note the failure** — log what tool failed and the error
2. **Do not retry blindly** — if it failed once, diagnose before retrying
3. **Fall back to flat files** — if memoria is down, write findings directly to `attack_surface.md` and `../shared/notes/important_notes.md`. These survive MCP outages.
4. **If sova/webdig tools fail** — check SSH connectivity to Kali. If Kali is unreachable, inform the operator.
5. **Resume when possible** — once MCP is restored, sync flat-file findings into memoria

---

## ELLIOT FAILURE PROTOCOL

When ELLIOT returns with objective EXHAUSTED or BLOCKED:

1. Read the full debrief in `exploit_log.md` — understand what was tried and what failed
2. Mark attempted paths as EXHAUSTED in `attack_surface.md`
3. Check: did ELLIOT surface new attack surface? If yes, evaluate it.
4. Check: are there untested delivery forms in the vulnerability primitive? If yes, consider redeployment with a fresh budget targeting those forms.
5. Check: is there an enumeration gap ELLIOT flagged? If yes, redeploy the appropriate specialist (webdig for web paths, NOIRE for local).
6. If ALL paths are exhausted and no new surface exists — brief the operator honestly: "All identified attack paths are exhausted. Recommend deeper enumeration or a strategic pivot." Do not loop.
