# Facts — Internal Debrief
> For: Operator + AI Crew
> Box: Facts | Completed: 2026-03-18 | Sessions: 1 | Elliot turns: 1/10

## Operation Timeline

| Session | Phase | Duration (approx) | What Happened |
|---------|-------|--------------------|---------------|
| 1 | Recon (Phase 1) | ~5 min | nmap full scan, whatweb, manual inspection. CamaleonCMS + MinIO identified. Open registration found. |
| 1 | CVE Research | ~3 min | Web search for CamaleonCMS and MinIO CVEs. Three CamaleonCMS CVEs identified with public PoCs. |
| 1 | Brief + Decision | ~1 min | Operator confirmed skip Phase 3 (web enum), proceed to exploitation. |
| 1 | Registration | ~8 min | CAPTCHA solving. 3 failed attempts before success on 4th try. |
| 1 | CVE-2024-46987 | ~3 min | Path traversal confirmed. Massive file extraction: /etc/passwd, nginx config, systemd units, Rails configs, database. |
| 1 | CVE-2025-2304 | ~2 min | Mass assignment privesc confirmed. oracletest user escalated to admin. |
| 1 | S3 Enumeration | ~3 min | S3 credentials from DB. boto3 bucket listing. `internal` bucket with SSH key found. |
| 1 | Dead Ends | ~8 min | S3 bucket write (didn't sync), CVE-2024-46986 file write (patched), MinIO admin API exploration. |
| 1 | SSH Key Crack | ~4 min (john background) | Passphrase cracked: `dragonballz`. SSH as trivia confirmed. User flag read. |
| 1 | Privesc | ~2 min | sudo -l → facter NOPASSWD. Web search for technique. Custom fact → root. |
| 1 | Handoff + Execution | ~2 min | Handoff written (ended up executing privesc in Oracle session directly). |

**Total wall-clock time: ~40 minutes.**

## What Worked Well

### Recon → CVE Mapping
Oracle identified the CMS (CamaleonCMS) from asset paths and Rails indicators within the first minute of web fingerprinting. The immediate CVE research against exact product name yielded three high-severity CVEs with public PoCs. The decision to skip Phase 3 web enum and go straight to exploitation was correct — the CVE surface was strong enough.

### Path Traversal Intelligence Extraction
Once CVE-2024-46987 was confirmed, the systematic file extraction was highly efficient. Oracle prioritized:
1. `/etc/passwd` → user enumeration
2. nginx config → architecture understanding
3. systemd services → process ownership and paths
4. Rails config files → database, master.key, credentials
5. SQLite database → credentials, S3 keys

This yielded the S3 credentials in a single extraction pass. The decision to query `cama_metas` for S3 config rather than searching filesystem configs was a shortcut that paid off — CMS databases are the canonical source for integration credentials.

### Parallel Cracking
Starting john in the background while continuing to explore other paths (S3 bucket write, file upload traversal, MinIO admin API) was efficient. The passphrase cracked in ~4 minutes against rockyou while Oracle was testing alternatives.

### Privesc Identification
The `sudo -l` → facter → custom fact chain was identified and executed cleanly. Web search for "facter sudo privilege escalation" confirmed the technique immediately.

## What We Got Wrong (And What It Cost)

### 1. CAPTCHA Solving — 3 Failed Attempts
**What happened:** First three CAPTCHA submissions failed. The session cookie was not properly maintained between fetching the CAPTCHA image and submitting the form.
**Root cause:** Initial attempts used separate curl commands or separate Python processes for GET (page + CAPTCHA) and POST (registration). The CAPTCHA answer is bound to the server-side session, so the session cookie must be identical across all requests.
**Cost:** ~8 minutes and several tool calls wasted.
**Fix for next time:** Always use a single `requests.Session()` object for the entire CAPTCHA flow (page load → CAPTCHA fetch → form submit). Save the session to a pickle between the "view CAPTCHA" and "submit answer" steps. Or better: build a reusable CAPTCHA registration script as a tool.

### 2. S3 Bucket Write Dead End
**What happened:** Wrote an SSH authorized_keys entry to the `internal` bucket, then tested SSH — failed. The S3 bucket is not filesystem-mounted; it's just object storage.
**Root cause:** Assumed the `internal` bucket might be FUSE-mounted or synced to the filesystem. Checked `/etc/fstab` and `/proc/mounts` only AFTER the failed SSH attempt.
**Cost:** ~3 minutes and several tool calls.
**Fix for next time:** Check for FUSE mounts / S3 sync mechanisms BEFORE attempting S3-to-filesystem writes. The presence of a home directory in an S3 bucket is more likely a backup than a live mount.

### 3. CVE-2024-46986 Testing (Already Patched)
**What happened:** Tested the file upload traversal (CVE-2024-46986) against CamaleonCMS 2.9.0. Got "Invalid file path" — the fix is in place.
**Root cause:** The advisory says "fixed in 2.8.2" and the target runs 2.9.0. Should have recognized this was likely patched before testing.
**Cost:** ~2 minutes, 2 tool calls.
**Fix for next time:** When a CVE advisory says "fixed in version X" and the target runs version Y > X, deprioritize testing it. Focus on CVEs known to affect the exact target version.

### 4. Handoff Written but Not Used
**What happened:** Wrote handoff.json for ELLIOT's privesc deployment, then executed the privesc directly from Oracle's session instead of launching ELLIOT.
**Root cause:** The privesc was trivial (single command) and context-switching to ELLIOT would have been slower than just running it.
**Cost:** Time writing the handoff (~2 min). No real harm, and the handoff document is useful for the writeup.
**Fix for next time:** For trivial exploitation (single well-understood command), skip the handoff and execute directly. Reserve ELLIOT for multi-step or uncertain exploitation paths. Add heuristic: if estimated turns < 3, execute in Oracle.

## Technical Lessons Learned

### CamaleonCMS Internals
- **Database**: SQLite3 in `storage/production.sqlite3`. All CMS settings (including S3 credentials) stored in `cama_metas` table as JSON blobs in the `value` column.
- **Session cookie**: `_factsapp_session` (Rails convention: `_{appname}_session`)
- **Admin paths**: `/admin/login`, `/admin/register`, `/admin/profile/edit`, `/admin/users/{id}/updated_ajax`
- **Version disclosure**: Footer `div.pull-right` inside `footer#main-footer` on admin pages
- **CVE-2024-46987**: Path traversal in `download_private_file` works on 2.9.0 despite "fixed in 2.8.2" advisory. The vulnerability is in how `fetch_file` processes the `file` parameter with `private/` prefix — traversal escapes the base directory.
- **CVE-2025-2304**: Mass assignment via `permit!` in `UsersController#updated_ajax`. Payload is `password[role]=admin` sent to the password change endpoint. The `_method=patch` field is required.
- **CVE-2024-46986**: File write traversal IS patched in 2.9.0. Returns "Invalid file path" on traversal attempts in the `folder` parameter.

### Facter Privesc
- Facter 4.10.0 accepts `--custom-dir` flag when run with sudo
- Custom fact files are standard Ruby with `Facter.add(:name) { setcode { ... } }` structure
- `Facter::Core::Execution.execute()` runs shell commands and returns stdout
- No restrictions on what the Ruby code can do — full code execution at the sudo privilege level
- `env_reset` in sudoers does NOT prevent `--custom-dir` from working since it's a command-line argument, not an environment variable

### MinIO / S3
- MinIO version: `2025-09-07T16:13:09Z` (obtained via `mc admin info`)
- The CMS's S3 credentials had full admin access (not just read/write to the bucket)
- `mc admin info` succeeded, confirming root-level MinIO credentials
- Service is called "ministack" internally but runs standard MinIO
- Health endpoints (`/minio/health/live`, `/minio/health/cluster`) respond on the API port without authentication

## Methodology Wins

### Skip-Phase-3 Decision
The operator's decision to skip web enumeration and go straight to exploitation was validated by the results. With HIGH confidence CVEs, open registration, and public PoCs, web enum would have been redundant overhead.

### Systematic File Extraction
The path traversal was used surgically — each file read was chosen to answer a specific question (architecture, credentials, access paths). The extraction order (passwd → nginx → systemd → rails config → database) built understanding progressively.

### Dual-Path Approach
While john cracked the SSH passphrase in the background, Oracle explored alternative paths (S3 write, file upload, MinIO admin). This parallel approach ensured no time was wasted waiting.

### Attack Surface Documentation
The living `attack_surface.md` document accurately tracked the operation's evolving state. Every credential, every path, every decision was logged in real time.

## IRONTHREAD Iteration Notes

### 1. MCP Tools Not Available
**Issue:** sova-mcp, webdig-mcp, and noire-mcp tool servers were not connected for this session. All reconnaissance was done via native Bash commands.
**Impact:** No impact on capability (nmap, whatweb, curl work fine), but the MCP tools would have provided structured output and automated the scouting report generation.
**Suggestion:** Add a pre-flight check in CLAUDE.md or session startup that warns if MCP servers are not connected.

### 2. CAPTCHA Handling Needs a Standard Pattern
**Issue:** Took 3 failed attempts to get CAPTCHA submission right due to session management issues.
**Suggestion:** Create a reusable CAPTCHA registration script template in `scripts/` or as a code snippet in the ORACLE system prompt. Pattern: single requests.Session → GET page → GET CAPTCHA → pickle session → [operator reads CAPTCHA] → load session → POST.

### 3. Handoff Threshold Heuristic
**Issue:** Wrote a full handoff.json for a 1-turn privesc. Unnecessary overhead.
**Suggestion:** Add guidance to ORACLE system prompt: "If the exploitation path is a single well-understood command (< 3 estimated turns), execute directly from Oracle session. Reserve ELLIOT deployment for multi-step, uncertain, or tool-heavy exploitation."

### 4. operation.md Not Updated
**Issue:** `operation.md` still shows both agents as PENDING after operation completion. Should reflect final state.
**Suggestion:** Add operation.md update to the checkpoint/completion workflow.

### 5. important_notes.md Underutilized
**Issue:** important_notes.md was never written to during the operation. Technical insights (CamaleonCMS database structure, facter privesc pattern) would be valuable for future boxes.
**Suggestion:** Add a step in the brief/decision workflow: "After each phase, append any transferable lessons to important_notes.md."

## What We'd Do Differently Next Time

1. **Validate session management before CAPTCHA attempts.** Use a single Python `requests.Session()` from the start, pickle it between steps.
2. **Check filesystem mounts before attempting S3-to-filesystem writes.** Read `/etc/fstab` and `/proc/mounts` first.
3. **Don't test CVEs that are documented as patched in older versions** when the target runs a newer version, unless there's specific evidence of regression.
4. **Skip ELLIOT handoff for trivial privesc.** If `sudo -l` returns a single exploitable binary with a well-known technique, execute directly.
5. **Write to important_notes.md during the operation**, not just at the end. Capture transferable patterns as they emerge.
6. **Update operation.md status** at each phase transition.

## Stats

| Metric | Value |
|--------|-------|
| Total time (wall clock) | ~40 minutes |
| Sessions | 1 |
| Elliot turns used / budget | 1 / 10 |
| CVEs exploited | 2 (CVE-2024-46987, CVE-2025-2304) |
| CVEs tested but patched | 1 (CVE-2024-46986) |
| Credentials recovered | 7 (CMS admin hash, S3 access/secret key, Rails master.key, secret_key_base, SSH key, SSH passphrase) |
| Files read via path traversal | ~15 |
| Dead ends explored | 3 (S3 bucket write, file upload traversal, MinIO admin config) |
| CAPTCHA attempts | 4 (3 failed, 1 success) |

## CVE Reference Card

| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| CVE-2024-46987 | CamaleonCMS 2.9.0 | Unsanitized file path in `download_private_file` → arbitrary file read | Extracted /etc/passwd, Rails configs, master.key, SQLite DB, SSH authorized_keys. Database yielded S3 credentials. |
| CVE-2025-2304 | CamaleonCMS 2.9.0 | Mass assignment via `permit!` in `updated_ajax` → role escalation | Escalated registered user to CMS admin. (Bonus — not required for the foothold path.) |
| CVE-2024-46986 | CamaleonCMS < 2.8.2 | File write via upload path traversal → RCE | Tested on 2.9.0 — **patched**. Not exploitable on this target. |

## Flags

| Flag | Value |
|------|-------|
| User | `c9c893330f8a88c388745862a2ccd223` |
| Root | `6af031dd9e664c8e9ec6383ba8308a2e` |
