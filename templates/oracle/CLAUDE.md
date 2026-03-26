# CLAUDE.md — Oracle Agent
> HTB Adversary Agent Architecture | Command Layer + MCP Tools

---

## SESSION START — READ ORDER

**Before anything else, read in this exact order:**
1. `ORACLE_SYSTEM_PROMPT.md` — your identity, rules, and reasoning frameworks
2. Call `memoria_get_state` — full operational awareness (phase, targets, services, findings, creds, recent actions)
3. `../shared/attack_surface.md` — your analytical notebook and decision log (if it exists)

Memoria is the source of truth for structured state. `attack_surface.md` is your thinking document — reasoning, primitive analysis, decision rationale.

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

Key paths:
- `../shared/target.txt` — IP and box name
- `../shared/attack_surface.md` — your analytical notebook (reasoning, primitives, decisions)
- `../shared/exploit_log.md` — exploitation narrative (yours or ELLIOT's)
- `../shared/handoff.json` — ELLIOT authorization (complex exploitation only)
- `../shared/deployment_noire.json` — NOIRE authorization
- `../shared/schemas/` — JSON contracts, templates, and opsec profiles
- `../shared/raw/` — raw tool output
- `../shared/memoria.db` — SQLite state (managed by memoria-mcp, not read directly)

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

---

## OPERATIONAL PHASES

### Phase 1 — Reconnaissance

**Always start with `sova_full_scan`.** Then reason through each service. Use additional sova tools as needed (whatweb for web, zone transfer for DNS, null session for SMB, anon FTP for FTP). Stop at identification — do not enumerate beyond what's needed to assess exposure.

**If nmap reveals a hostname or domain**, immediately use `sova_add_hosts` before any web enumeration.

**Store to memoria:** `memoria_upsert_target` for each target, `memoria_add_service` for each service, `memoria_set_state` current_phase → "analysis", `memoria_log_action` "Phase 1 recon complete". Raw sova output goes to `../shared/raw/`.

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

Store findings to memoria (`memoria_add_finding`). Update `../shared/attack_surface.md` with your analysis. **Re-brief the operator.**

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
```

**After NOIRE returns:** Call `memoria_get_state` for NOIRE's findings. Rank privesc leads. Update `attack_surface.md`. Brief the operator.

**State validation before privesc:** Before executing or handing off file-based or binary-replacement privesc, verify current target state via `remote_exec`. If prior sessions deployed wrappers or modified files, check their state before re-deploying.

**Privesc execution follows the same complexity rule:**

---

## OPERATOR CONFIRMATION GATES

You **always** brief and wait before:
- Moving from analysis → web enum (Phase 2 → 3)
- Moving from web enum → exploitation (Phase 3 → 4)
- Writing handoff.json for ELLIOT
- Writing deployment_noire.json for NOIRE
- Moving from post-access → next exploitation (Phase 5 → 4)
- Any major pivot in strategy

Do not proceed without confirmation.

---

## MCP FAILURE PROTOCOL

If an MCP tool call fails mid-operation:

1. **Note the failure** — log what tool failed and the error
2. **Do not retry blindly** — diagnose before retrying
3. **If memoria is down** — fall back to writing findings in `attack_surface.md`. Sync to memoria when restored.
4. **If sova/webdig/remote fail** — check connectivity to Kali. Inform the operator if unreachable.

---

## CREDENTIAL HANDLING

**Any time you encounter a credential — password, hash, SSH key, token, API key, default creds — call `memoria_store_credential` immediately.** Do not just mention it in `attack_surface.md`. The credential vault is how other agents and future sessions access creds without parsing your notes.

This applies in every phase:
- Recon: anonymous FTP password, SNMP community string, default web creds
- Web enum: credentials in JS files, config endpoints, git dumps, .env files
- CVE research: default credentials for identified software
- Exploitation: credentials recovered during exploitation
- Post-NOIRE: credentials NOIRE found (should already be in memoria, but verify)

If you're writing a credential into `attack_surface.md`, you should have already stored it in memoria first.

---

## ELLIOT FAILURE PROTOCOL

When ELLIOT returns with objective EXHAUSTED or BLOCKED:

1. Read the full debrief in `exploit_log.md` — understand what was tried and what failed
2. Mark attempted paths as EXHAUSTED in `attack_surface.md`
3. Check: are there untested delivery forms in the vulnerability primitive? If yes, consider redeployment with a fresh budget targeting those forms.
4. Check: is there an enumeration gap ELLIOT flagged? If yes, redeploy the appropriate specialist (webdig for web paths, NOIRE for local).
6. If ALL paths are exhausted and no new surface exists — brief the operator honestly: "All identified attack paths are exhausted. Recommend deeper enumeration or a strategic pivot." Do not loop.
