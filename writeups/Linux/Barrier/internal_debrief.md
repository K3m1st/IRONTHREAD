# Barrier — Internal Debrief
> For: Operator + AI Crew
> Box: Barrier | Completed: 2026-03-27 | Sessions: 1 | Elliot turns: 0 (not deployed) | NOIRE turns: 0 (not deployed)

## Operation Timeline

| Time | Phase | What Happened |
|------|-------|---------------|
| 02:06Z | Recon | Full scan, 6 services identified |
| 02:08Z | Recon | Hosts added, whatweb fingerprinting, service version confirmation |
| 02:10Z | Enumeration | GitLab public repo found, commit history leaked satoru's password |
| 02:13Z | Analysis | CVE research: CVE-2024-45409 identified as primary path |
| 02:15Z | Analysis | Attack surface document written, operator brief delivered |
| 02:15Z–17:00Z | (Gap) | Session pause between analysis and exploitation |
| 17:00Z–17:15Z | Exploitation | Multiple failed attempts to capture SAMLResponse programmatically |
| 17:15Z | Exploitation | Operator captured SAMLResponse via Burp, decoded manually |
| 17:17Z | Exploitation | SAML bypass: NameID=root → logged in as satoru (wrong target) |
| 17:17Z | Exploitation | SAML bypass: NameID=akadmin + email changed → rejected |
| 17:24Z | Exploitation | SAML bypass: NameID=akadmin (no email change) → admin session |
| 17:37Z | Post-exploit | Memoria audit, state update |
| 17:43Z | Exploitation | Runner unpaused, CI pipeline with reverse shell → connected but ephemeral |
| 17:44Z | Exploitation | CI pipeline failed: alpine/helper images not cached, pull_policy=never rejected |
| 17:45Z | Exploitation | CI pipeline with gitlab-ce image → reverse shell connected (root in container) |
| 17:47Z | Exploitation | Shell died on job timeout. Session cookie expired. Multiple regen cycles. |
| 17:48Z–18:10Z | Exploitation | Repeated project creation failures (box resets), session expiry, PAT creation failures |
| 18:10Z | Pivot | Operator: "just build and read env." Simplified CI YAML → AUTHENTIK_TOKEN leaked |
| 18:13Z | Post-exploit | authentik superadmin confirmed. Guacamole discovered. User maki found. |
| 18:20Z | Post-exploit | Created operator account in authentik. Operator logged into Guacamole. |
| 18:30Z | Post-exploit | MySQL creds from guacamole.properties. maki_adm SSH key+passphrase from guac_db. |
| 18:40Z | Privesc | SSH as maki_adm. .bash_history leaked sudo password. Root. Flags captured. |
| 18:43Z–19:00Z | Documentation | Memoria sync, attack_surface update, exploit_log written |

## What Worked Well

**Recon was fast and thorough.** Phase 1 (scan → service identification → version confirmation → credential recovery) completed in under 10 minutes. The commit history check was the right instinct — OAuth scripts in public repos almost always have credential hygiene issues.

**CVE research was accurate.** CVE-2024-45409 was correctly identified as the primary path based on version matching (17.3.2 < 17.3.3 fix) and SAML configuration confirmation. The vulnerability primitive analysis (XPath element ordering) was correct and helped explain the exploit to the operator.

**The synacktiv PoC worked cleanly.** Once we had the raw XML, the exploit tool ran without issues. The forged assertion was accepted by GitLab on the first valid attempt.

**authentik API enumeration was efficient.** After obtaining the AUTHENTIK_TOKEN, we quickly mapped users, applications, and the Guacamole SAML provider — which was the critical pivot that revealed Tomcat:8080 was actually a Guacamole gateway.

## What We Got Wrong (And What It Cost)

### 1. SAMLResponse Capture Automation — ~90 minutes wasted

**What happened:** Wrote 5+ versions of a Python script to capture the SAMLResponse through the authentik SAML flow. Every approach failed — requests-based consent API, Playwright browser automation (3 iterations), deflate decompression of copy-pasted data.

**Root cause:** Over-engineering. The authentik consent flow API has undocumented behavior that we couldn't replicate. The Playwright SPA timing was fragile. The deflate data corrupted during terminal copy-paste.

**Cost:** ~90 minutes of operator time. This was the single largest time sink.

**Fix for next time:** When an automated approach fails twice, switch to manual tooling immediately. Burp Suite solved the problem in 30 seconds. Rule: *2 automated failures on the same step → go manual.*

### 2. Wrong SAML Target — 2 wasted attempts

**What happened:** First forged with `NameID=root` (GitLab default admin). Got satoru. Then forged with `NameID=akadmin` but also changed the email attribute to `akadmin@barrier.vl`. Got rejected.

**Root cause:** Assumed GitLab default admin was `root`. Had already enumerated users via API and saw `akadmin` (ID 1) but didn't connect it to the admin role early enough. The email change was an unnecessary modification that broke the assertion — the PoC handles NameID correctly; the email attribute should have been left alone.

**Cost:** 2 extra SAML bypass cycles (~5 minutes each including session setup).

**Fix for next time:** Before forging, explicitly confirm the target: `GET /api/v4/users` → find ID 1 → that's the admin. Don't modify assertion fields beyond what the PoC changes.

### 3. Reverse Shell Overcomplexity — ~20 minutes wasted

**What happened:** Spent time setting up netcat listeners, troubleshooting Docker image pulls, fighting session expiry, and recovering from a dead shell — all to get an interactive container shell that died on job timeout anyway.

**Root cause:** Defaulted to "get a reverse shell" when the actual need was "read what's in the CI environment." The operator's suggestion to just `env | sort` and read the job log was the correct approach.

**Cost:** ~20 minutes of fighting Docker images, listeners, and session cookies.

**Fix for next time:** In CI/CD exploitation, default to *reading job output* not *establishing shells*. A reverse shell from a CI runner is almost never the final objective — it's a container, not the host. Extract data from the build environment first.

### 4. Tomcat Not Enumerated — Blind Spot

**What happened:** Port 8080 was identified as Tomcat 9.0.58 from the default page. We researched CVE-2025-24813 as a fallback and never directory-enumerated it. Guacamole at `/guacamole/` was only discovered indirectly through the authentik SAML provider configuration.

**Root cause:** Accepted "default Tomcat page" as "nothing deployed here" without verification. Started a dir bust once but it was rejected by the operator (rightfully — we had stronger paths).

**Cost:** Not directly costly since the authentik pivot found it anyway, but this could have been an independent path discovered much earlier. If the SAML bypass had failed, we would have been stuck without knowing Guacamole existed.

**Fix for next time:** Always run a quick directory check on web services showing default pages. Even a manual check of `/guacamole/`, `/manager/`, `/webapps/` takes 10 seconds.

### 5. Session Cookie Instability — Ongoing Friction

**What happened:** GitLab session cookies from the SAML bypass expired rapidly. Every write API operation needed a CSRF token. We never successfully created a Personal Access Token for stable API access (404 from API, 422 from web form, 401 from impersonation token endpoint).

**Root cause:** Session-based auth isn't designed for API automation. The PAT creation failure was never diagnosed — could be a GitLab configuration issue or an auth scope limitation of session cookies.

**Cost:** ~15 minutes of cumulative session regeneration and failed PAT attempts. Operator eventually used browser session directly.

**Fix for next time:** After getting admin session in browser, immediately create a PAT through the web UI (Admin Area → Users → akadmin → Impersonation Tokens). Don't try to do it via API with session cookies.

### 6. ELLIOT/NOIRE Never Deployed

**What happened:** The entire operation was run by ORACLE + operator. ELLIOT was never handed off for complex exploitation. NOIRE was never deployed for post-access investigation.

**Root cause:** The exploitation path never reached "complex" threshold. The CVE-2024-45409 PoC was run directly. Post-access on the host was two commands (.bash_history → sudo).

**Cost:** No direct cost — the operation completed efficiently without them. But the SAML response capture struggle is exactly the kind of multi-attempt, mid-stream adaptation that ELLIOT is designed for. Deploying ELLIOT for the SAML capture might have been more efficient than 5 script rewrites.

**Fix for next time:** Consider ELLIOT deployment when automated scripting fails twice on the same exploitation step. ELLIOT's multi-turn budget and research capability is better suited for "figure out why this API isn't working" than Oracle rewriting scripts in-conversation.

## Technical Lessons Learned

### CVE-2024-45409 — ruby-saml XPath Bypass
- The exploit requires a **legitimately signed** SAML document — any document from the IdP works, it doesn't need to be for the target user
- The PoC modifies NameID only — don't touch other assertion attributes (email, etc.) unless you know the target's exact values
- authentik uses HTTP-Redirect binding for SAMLResponse (uncommon — most IdPs use HTTP-POST). This means deflate compression in transit but the exploit works on the raw XML regardless
- GitLab matches users by NameID/extern_uid first, email attribute second. If the NameID matches an extern_uid, the email attribute is ignored

### authentik API Behavior
- The flow executor API at `/api/v3/flows/executor/<slug>/` works for authentication stages but the consent stage POST consistently fails with `ak-stage-flow-error`
- authentik cookies (`authentik_session`, `authentik_csrf`) are scoped to the port — cookies from :9443 don't apply to :9000 API calls
- The `set_password` endpoint is at `/api/v3/core/users/<pk>/set_password/` (POST), separate from the user PATCH endpoint which ignores password fields
- `is_superuser` cannot be set directly via user create or PATCH — must be done by adding to the "authentik Admins" group

### GitLab CI/CD Runner Constraints
- `run_untagged: false` means jobs MUST include the runner's tag (`auto_5e7f`)
- `access_level: ref_protected` means jobs only run on protected branches (main by default)
- `allowed_pull_policies: [if-not-present]` means `pull_policy: never` in CI YAML is rejected
- On air-gapped Docker runners, use images from the running infrastructure: the gitlab-ce image, postgres, redis, etc. are always cached

### SSH on This Box
- Only offered `ssh-rsa` host key algorithm — required `HostKeyAlgorithms=+ssh-rsa` and `PubkeyAcceptedAlgorithms=+ssh-rsa`
- Password auth for satoru was denied despite valid GitLab creds — SSH uses local auth, not authentik
- The encrypted RSA key required `sshpass -P "Enter passphrase"` flag (capital -P for passphrase prompt matching, not -p)

## Methodology Wins

**Commit history check during recon** — checking Git history for credential leaks should be standard for every GitLab/Gitea/GitHub instance. The two-commit pattern (add creds → redact creds) is extremely common.

**CVE version matching** — confirming GitLab 17.3.2 against the 17.3.3 fix version was quick and definitive. The vulnerability primitive analysis (XPath ordering) helped explain the exploit clearly.

**Operator-driven simplification** — three key operator interventions improved the operation:
1. "Use Burp" — solved the SAML capture after 90 minutes of scripting failures
2. "Just run env | sort" — replaced complex reverse shell approach with a 2-line CI file
3. "Create an authentik account" — instead of resetting maki's password, create our own admin

## IRONTHREAD Iteration Notes

### Oracle System Prompt
- **Add:** "When automated exploitation scripting fails twice on the same step, consider: (a) switching to manual tools, (b) deploying ELLIOT, or (c) asking the operator for hands-on assistance. Do not rewrite the same script more than twice."
- **Add:** "For CI/CD exploitation, default to reading job output (env dump, file reads) rather than establishing reverse shells. CI runner shells are ephemeral and containerized — extract data, don't establish persistence."
- **Clarify:** The Phase 4 exploitation section says ORACLE executes trivial/standard exploits directly. The SAML bypass was standard but the SAML response *capture* was complex. Consider: complexity should factor in the full chain, not just the final exploit step.

### MCP Tools — Gaps Identified
- **webdig_curl lacks `-k` flag:** All HTTPS curls to self-signed certs failed via webdig_curl (return code 60). Had to fall back to bash curl. webdig_curl should support an `insecure` parameter.
- **sova_add_hosts timeout:** The tool returned a timeout error but the entries were actually added (or not — unclear). Needs better error handling and verification.
- **No remote-mcp usage:** Despite being available, remote-mcp was never used. The SAML bypass required browser-level interaction that remote-mcp can't provide. For future boxes with direct SSH/shell access earlier in the chain, remote-mcp would be the right tool.

### Workflow
- **PAT creation should be step 1 after admin access.** Before doing anything else as GitLab admin, create a Personal Access Token through the web UI. Session cookies are too fragile for sustained API work.
- **Directory enumeration on ALL web ports.** The Tomcat/Guacamole miss could have been avoided by a quick gobuster on :8080 during Phase 1. Even if we don't fully enumerate, checking 3-4 common paths (`/guacamole/`, `/manager/`, `/webapps/`) takes seconds.

## What We'd Do Differently Next Time

1. **Capture SAML response via Burp from the start** — don't attempt programmatic capture unless the target uses HTTP-POST binding (form-based, not redirect)
2. **Enumerate all GitLab users and confirm admin identity before forging** — check `/api/v4/users` for ID 1
3. **Create a PAT immediately after getting admin browser session** — before any API automation
4. **Run basic dir checks on every web port during recon** — even just `/guacamole/`, `/manager/`, `/admin/`
5. **Default to job log output for CI/CD exploitation** — reverse shells from Docker runners are almost never the right approach
6. **Deploy ELLIOT earlier for multi-attempt exploitation steps** — the SAML capture struggle was ELLIOT-shaped work
7. **Don't modify assertion fields beyond what the PoC changes** — understand the target's user matching logic first

## Stats

| Metric | Value |
|--------|-------|
| Total time (approximate) | ~4 hours active |
| Session count | 1 |
| Services discovered | 6 |
| CVEs exploited | 1 (CVE-2024-45409) |
| Credentials recovered | 7 |
| Findings logged | 7 |
| Dead ends documented | 12 |
| ELLIOT deployments | 0 |
| NOIRE deployments | 0 |
| Operator interventions (critical) | 3 (Burp capture, env dump suggestion, create-not-reset) |
| SAML bypass attempts | 3 (1 wrong user, 1 email mismatch, 1 success) |
| CI pipeline failures | 4 (3 image pulls, 1 pull policy) |
| Session regenerations | 5+ |

## CVE Reference Card

| CVE | Product | Version | Primitive | How We Used It |
|-----|---------|---------|-----------|----------------|
| CVE-2024-45409 | ruby-saml / GitLab CE | ≤1.16.0 / <17.3.3 | XPath selects first DigestValue in document order, not the one in the signed Reference | Forged SAML assertion as akadmin → GitLab admin |
| CVE-2025-24813 | Apache Tomcat | 9.0.0–9.0.98 | Partial PUT + deserialization of session files | Identified but not exploited — 3 non-default prerequisites |

## Flags

```
user.txt: [REDACTED]
root.txt: [REDACTED]
```
