# Kobold — Internal Debrief
> For: Operator + AI Crew
> Box: Kobold | Completed: 2026-03-21 | Sessions: 3 (Oracle x2, ELLIOT x2, NOIRE x1) | ELLIOT turns: 23/28 total (4/8 foothold + 19/20 privesc)

## Operation Timeline

| Session | Phase | Duration (approx) | What Happened |
|---------|-------|--------------------|---------------|
| 1 (Oracle) | Recon + Analysis | ~2h | Nmap, vhost fuzz, MCPJam discovery, attack surface built. Box reset before exploitation. |
| 2 (Oracle + ELLIOT) | Re-exploit + Foothold | ~30m | ELLIOT deployed for MCPJam RCE. SSH key planted. User flag captured in 4/8 turns. |
| 2 (Oracle) | Post-access (inline) | ~1h | Oracle ran noire-equivalent checks inline. Discovered Arcane, operator group, PrivateBin data. Started rabbit-holing on Arcane JWT. |
| 2 (Oracle) | Arcane JWT rabbit hole | ~1.5h | Forged 20+ JWT variants across 4 secret candidates. Researched CVE-2026-23944 and CVE-2026-23520. Downloaded Arcane source code. All dead ends. |
| 3 (NOIRE) | Post-access investigation | ~20m | Disciplined full-surface sweep. Found /usr/bin/bash 0777 (158 bytes). Reported pre-staged artifacts in /tmp. Did NOT check file contents. |
| 3 (Oracle) | Brief + ELLIOT handoff | ~15m | Built handoff for bash replacement privesc. Did not validate that bash was already replaced. |
| 3 (ELLIOT) | Privesc attempt | 19/20 turns | Deployed wrapper. Searched for trigger. Exhausted Arcane auth. Returned BLOCKED. |
| 3 (Oracle) | Brute force pivot | ~15m | Launched hydra against alice. Running at 66/min. |
| 3 (Operator) | Catches the miss | ~2m | Operator notices 158 bytes, runs `cat /usr/bin/bash`. Wrapper already deployed. `/tmp/rootbash` exists SUID. Root flag captured in one command. |

**Total wall-clock: ~6 hours. Optimal path would have been ~45 minutes.**

## What Worked Well

### Recon Phase
- Sova full scan + vhost fuzzing correctly identified the attack surface
- MCPJam Inspector was immediately recognized as high-value
- SSL wildcard cert observation led to productive vhost enumeration

### ELLIOT Session 1 (Foothold)
- Clean 4-turn execution: keygen, RCE, failed echo, successful curl download
- Correctly identified that base64 echo through JSON was unreliable and pivoted to HTTP hosting
- SSH persistence was solid — never lost access after that

### NOIRE Investigation
- Disciplined full-surface sweep as designed
- Found the 0777 bash finding that Oracle's inline enumeration missed
- Correctly mapped all services, users, groups, and the Arcane API surface
- Reported pre-staged /tmp artifacts (even if it didn't fully investigate them)

### IRONTHREAD Infrastructure
- Handoff schema forced clear scope definition for ELLIOT
- Turn budgets prevented infinite loops (ELLIOT returned at 19/20 with a clear debrief)
- Checkpoint system enabled clean session resumption after box reset
- NOIRE as separate agent produced a cleaner investigation than Oracle doing it inline

## Critical Failure — The 777 Bash That Nobody Investigated

This deserves its own section above the rest because it was the defining failure of the operation.

`/usr/bin/bash` was **mode 0777.** This is a free, obvious path to root. We found it. We even exploited it — **in session 1, WE replaced bash with a SUID-dropping wrapper and WE backed up the real binary to /tmp/bash_orig.** Then I created a new session. we re-established the foothold, and we completely forgot about our own work. When we came back and NOIRE found the 0777 bash again, nobody recognized that this was OUR setup from the prior session. Nobody checked if the wrapper was already deployed. Nobody checked if root had already triggered it.

Three agents saw the 0777 bash. None treated it as the free root it was:

- **Oracle** (inline enum): Found `/usr/bin/bash` in writable path results. Logged it. Immediately pivoted to Arcane JWT research — spending 1.5 hours on a complex path while a trivial one was sitting right there.
- **NOIRE**: Reported it as the #1 privesc lead with HIGH confidence. Noted `/tmp/bash_wrapper` and `/tmp/bash_orig` existed. Classified them as "prior player breadcrumbs" — **they were our own artifacts from session 1.** Did not run `file /usr/bin/bash`. Did not check if `/tmp/rootbash` already existed.
- **ELLIOT**: Received a handoff to "deploy the wrapper." Did deploy it (overwriting our prior wrapper). Spent 18 more turns searching for a trigger — but root had already executed bash, and `/tmp/rootbash` was sitting there with SUID set the entire time.

**The operator had to manually jump between agent sessions** because Oracle refused to use NOIRE as designed — Oracle kept enumerating inline and rabbit-holing on Arcane instead of deploying the investigation agent. When NOIRE was finally deployed (at operator insistence), it found the 777 bash but still didn't investigate it properly.

### The Core Lesson

**0777 on a system shell interpreter is not a "ranked finding." It is a free path to root.** The moment any agent sees `bash`, `sh`, `dash`, or `zsh` as world-writable, the operation pivots to that immediately:

1. Replace it with a SUID-dropping wrapper
2. Trigger root to execute it (root's login shell, cron, service restart — anything)
3. Run the SUID copy with `-p`
4. Root.

We did step 1 in session 1. Root did step 2 on its own. Steps 3 and 4 were one command: `/tmp/rootbash -p`. Instead we spent 3 hours on Arcane JWT forgery, NOIRE deployment, ELLIOT trigger-hunting, and an SSH brute force.

### What This Means for IRONTHREAD

We need a **"critical binary" alert pattern** baked into every agent's system prompt. When enumeration finds a writable file in `/usr/bin/`, `/usr/sbin/`, `/bin/`, or `/sbin/` — especially shell interpreters — the agent must STOP ranking and START exploiting. This is not a lead. This is the answer.

We also need better **session continuity for our own exploitation work.** The checkpoint from session 1 should have said "we replaced /usr/bin/bash with a wrapper — validate on re-entry." It didn't, and we lost track of our own progress.

---

## What We Got Wrong (And What It Cost)

### 1. Oracle rabbit-holed on Arcane JWT instead of completing enumeration
**What happened:** After inline noire checks found the Arcane service, Oracle immediately started forging JWTs, researching CVEs, fetching source code, and trying 20+ token variants.
**Root cause:** Oracle treated the first interesting finding as the path instead of completing the surface map. The CLAUDE.md says "complete CVE research before surfacing exploit paths" but doesn't say "complete ALL enumeration before deep-diving ANY path."
**Cost:** ~1.5 hours, 10+ web searches, extensive token generation — all wasted.
**Fix:** Oracle's system prompt should enforce: "Complete full enumeration sweep BEFORE deep-diving any single path. If a finding is interesting, log it and continue the sweep."

### 2. Oracle did post-access enumeration inline instead of using NOIRE
**What happened:** Oracle ran noire-equivalent SSH commands directly, creating a new SSH connection for every check. The operator had to explicitly request NOIRE deployment.
**Root cause:** NOIRE was originally an MCP tool set, not a separate agent. The architecture change to make NOIRE an agent happened mid-operation. Oracle defaulted to the old pattern.
**Cost:** ~1 hour of slower, less disciplined enumeration. Multiple SSH connections. Operator frustration.
**Fix:** Oracle's CLAUDE.md should say: "After foothold, deploy NOIRE for investigation. Do NOT enumerate inline."

### 3. Nobody validated the state of /usr/bin/bash
**What happened:** NOIRE reported `/usr/bin/bash` as mode 0777, 158 bytes. Oracle built a handoff to "deploy the wrapper." ELLIOT deployed a wrapper (which overwrote the existing wrapper). Nobody ran `file /usr/bin/bash` or `cat /usr/bin/bash`.
**Root cause:** Everyone treated the finding as "permissions are wrong" and planned exploitation. Nobody asked "what IS this file right now?" A 158-byte bash is not a bash binary. This is a one-command check that was never performed.
**Cost:** ELLIOT burned 19/20 turns deploying and trigger-hunting. Oracle launched a brute force attack. Total: ~3 hours of wasted effort after the answer was already on disk.
**Fix:**
- NOIRE should run `file` on any binary it reports as misconfigured, and flag size anomalies (158 bytes vs expected ~1.4MB)
- Oracle should validate key claims from NOIRE before writing handoffs
- ELLIOT's first turn on a binary-replacement privesc should include `file` and `wc -c` checks
- Add to all agent system prompts: "When a writable system binary is found, check whether it has ALREADY been replaced (file type, byte size, contents)."

### 4. ELLIOT's "no rootbash found" was a false negative
**What happened:** ELLIOT turn 1 said "No rootbash exists yet." But ELLIOT also re-deployed the wrapper, which may have overwritten the prior wrapper and required a fresh root trigger. It's possible rootbash DID exist before ELLIOT's session started, and ELLIOT's wrapper redeployment reset the state.
**Root cause:** ELLIOT's first turn verified md5 of bash_orig but not whether /tmp/rootbash already existed BEFORE replacing bash.
**Cost:** If rootbash existed at session start, ELLIOT could have finished in turn 1.
**Fix:** Add to privesc handoffs: "Before modifying anything, check if the attack has ALREADY BEEN COMPLETED."

### 5. Brute force was the wrong next step
**What happened:** After ELLIOT returned blocked, Oracle authorized a hydra brute force against alice's SSH password.
**Root cause:** The operator and Oracle both assumed all technical paths were exhausted. They were — except for the one sitting in /tmp.
**Cost:** ~15 minutes of compute, false confidence that we were doing the right thing.
**Fix:** Before pivoting to brute force, always re-verify the state of the primary path. `ls -la /tmp/rootbash` would have ended the operation.

## Technical Lessons Learned

### MCPJam Inspector stdio Transport
- The stdio transport spawns commands as a child process of the Inspector's Node.js server
- The HTTP response always reports failure (not a real MCP server) — this is expected and should not be interpreted as "exploit failed"
- JSON encoding makes it difficult to pass complex bash payloads through the `args` array — base64 encoding can get corrupted. Hosting payloads on an HTTP server and curling them is more reliable
- The Inspector runs as whatever user started the Node process (ben in this case)

### World-Writable Binary Exploitation
- ETXTBSY prevents writing to a running binary — kill all instances first, or use a non-bash shell (dash via MCPJam RCE) for the replacement operation
- The wrapper MUST use a different interpreter (dash) to avoid recursion
- The SUID bit only works on ELF binaries, not shell scripts — that's why we copy the real bash and SUID it, rather than making the wrapper SUID
- `/tmp/rootbash -p` is needed — without `-p`, bash drops privileges

### Arcane Docker Management v1.13.0
- ENCRYPTION_KEY and JWT_SECRET are separate configuration values
- JWT_SECRET is auto-generated at first run if not provided (stored in BoltDB in the working directory)
- CVE-2026-23944 (auth bypass) only affects remote environments — useless if only local environment exists
- CVE-2026-23520 (lifecycle label RCE) was patched in v1.13.0
- The OpenAPI spec at `/api/openapi.json` is fully accessible without auth — useful for mapping the API surface

## Methodology Wins

### Turn Budget System
ELLIOT's 8-turn budget for the foothold was perfect — completed in 4. The 20-turn budget for privesc was appropriate even though the path was blocked — ELLIOT exhausted every reasonable avenue before returning.

### Handoff Schema
The handoff.json forced Oracle to articulate the vulnerability primitive, delivery forms, and backup paths before deploying ELLIOT. This prevented ELLIOT from wandering.

### NOIRE as Separate Agent
When deployed, NOIRE produced a much cleaner, more disciplined investigation than Oracle's inline enumeration. The separate session context prevented rabbit-holing.

### Checkpoint System
Session resumption after the box reset was seamless. Checkpoint.md got the new session to full awareness in one read.

## IRONTHREAD Iteration Notes

### 1. Add "state validation" step to privesc handoffs
**File:** `templates/oracle/ORACLE_SYSTEM_PROMPT.md`
**Change:** In the privesc handoff section, add: "Before writing a handoff for a file-based privesc, validate the current state of the target file: run `file`, check byte size, and check if attack artifacts already exist."

### 2. NOIRE must run `file` on anomalous binaries
**File:** `templates/noire/NOIRE_SYSTEM_PROMPT.md`
**Change:** In the investigation areas section, add: "For any binary reported as writable or misconfigured, run `file <binary>` and compare byte size to expected values. A 158-byte /usr/bin/bash is a shell script, not a binary — report this immediately as 'already replaced.'"

### 3. Oracle should not enumerate inline after foothold
**File:** `templates/oracle/CLAUDE.md`
**Change:** In Phase 5, replace the inline noire-mcp investigation with: "Deploy NOIRE agent for post-access investigation. Do not run enumeration commands inline — NOIRE exists for this purpose."

### 4. Add "check completion" to ELLIOT's privesc workflow
**File:** `templates/elliot/ELLIOT_SYSTEM_PROMPT.md`
**Change:** Add to the first-turn checklist: "Before modifying any target file for privesc, check whether the attack has ALREADY BEEN COMPLETED. For bash replacement: check if /tmp/rootbash (or similar SUID artifact) already exists."

### 5. NOIRE deployment_noire.json should include "already_exploited_checks"
**File:** `templates/noire/CLAUDE.md` or deployment schema
**Change:** Add a field or instruction: "If you find pre-staged attack artifacts (wrapper scripts, SUID copies, backup binaries), check whether the attack has already succeeded BEFORE ranking it as a future path."

### 6. Add "critical binary alert" pattern to ALL agent system prompts
**Files:** `templates/oracle/ORACLE_SYSTEM_PROMPT.md`, `templates/noire/NOIRE_SYSTEM_PROMPT.md`, `templates/elliot/ELLIOT_SYSTEM_PROMPT.md`
**Change:** Add a boxed rule:
```
CRITICAL BINARY ALERT: If any enumeration reveals a writable file in /usr/bin/, /usr/sbin/,
/bin/, or /sbin/ — especially shell interpreters (bash, sh, dash, zsh) — STOP RANKING AND
INVESTIGATE IMMEDIATELY:
  1. file <binary> — is it still a real binary or a script?
  2. ls -la <binary> — byte size (real bash is ~1.4MB, not 158 bytes)
  3. cat <binary> — if small, read the contents
  4. ls -la /tmp/*bash* /tmp/*root* — has the attack already been executed?
This is not a lead to rank. This is the answer. Pounce on it.
```

### 7. Oracle must deploy NOIRE, not enumerate inline
**File:** `templates/oracle/CLAUDE.md`
**Change:** Phase 5 should be a hard gate: "After ELLIOT returns with a foothold, deploy NOIRE for post-access investigation. Do NOT run enumeration commands inline. If NOIRE does not exist as an agent directory, create it from templates before proceeding. Oracle's job is to brief, not to enumerate."
**Why this matters:** On Kobold, the operator had to manually jump sessions and force NOIRE deployment because Oracle kept running SSH commands inline and rabbit-holing. The whole point of NOIRE is disciplined, scoped investigation — Oracle doing it inline defeats that purpose.

## What We'd Do Differently Next Time

1. **Deploy NOIRE immediately after foothold** — not inline Oracle enumeration
2. **NOIRE runs `file` on every anomalous binary** — catches replaced binaries instantly
3. **Check attack completion before planning execution** — `ls -la /tmp/rootbash` before writing a handoff
4. **Complete the full surface sweep before deep-diving** — no Arcane JWT rabbit hole until NOIRE finishes
5. **When ELLIOT returns blocked on a binary privesc, re-check the binary state** — it may have changed since deployment
6. **Treat file size anomalies as critical signals** — 158 bytes is never a real bash binary

## Stats

| Metric | Value |
|--------|-------|
| Total wall-clock time | ~6 hours |
| Optimal time (hindsight) | ~45 minutes |
| ELLIOT turns (foothold) | 4/8 |
| ELLIOT turns (privesc) | 19/20 |
| NOIRE deployment | 1 (post-architecture change) |
| Oracle sessions | 2 |
| Web searches | 12+ |
| JWT forgery attempts | 20+ |
| Wasted effort on Arcane | ~3 hours |
| Time from rootbash existing to flag capture | ~2 hours (the miss) |
| Commands that would have ended it | `file /usr/bin/bash` or `ls -la /tmp/rootbash` |

## CVE Reference Card

| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| N/A (design flaw) | MCPJam Inspector | stdio transport spawns arbitrary commands without auth | Foothold: reverse shell as ben |
| CVE-2026-23944 | Arcane v1.13.0 | Auth bypass on remote environment proxy middleware | Investigated but UNUSABLE — no remote environments configured |
| CVE-2026-23520 | Arcane <v1.13.0 | Command injection via lifecycle labels | Investigated but PATCHED in target version |

## Flags

| Flag | Value |
|------|-------|
| User | `f1057924705f1ae16e6b57d59b439aeb` |
| Root | `98c2e7694dba838e4d28cf913f178fd0` |
