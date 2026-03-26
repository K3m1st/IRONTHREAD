# Attack Surface — Snapped (10.129.9.2)
**Last Updated:** 2026-03-25T17:37Z | **Phase:** Exploitation Handoff

## Executive Summary
Critical vulnerability chain identified. CVE-2026-27944 provides unauthenticated backup download from Nginx UI, which leaks encryption keys, user hashes, JWT secrets, and the node authentication secret. The node secret grants full admin API access without credentials. From admin access, nginx config editing + reload provides RCE.

## Attack Chain

```
CVE-2026-27944 (unauth backup)
  → Decrypt backup (AES-256-CBC key leaked in X-Backup-Security header)
  → Extract node secret from app.ini
  → Authenticate to all API endpoints via X-Node-Secret header
  → Edit nginx config (POST /api/config or POST /api/sites/:name/advance)
  → Inject reverse shell payload into nginx config
  → Trigger reload (POST /api/nginx/reload)
  → RCE as nginx worker user
```

## Vulnerability Details

### CVE-2026-27944 — Unauthenticated Backup Download (CVSS 9.8)
- **Status:** VALIDATED — backup downloaded and decrypted
- **Endpoint:** GET http://admin.snapped.htb/api/backup
- **Encryption:** AES-256-CBC, key+IV leaked in `X-Backup-Security` response header
- **Key:** `ZB/MIdQu8dThXmLgVWG6BW6g/Vg0HDUILCP6rWe7OUk=`
- **IV:** `/B35epWGfuT812NbIwWdWg==`
- **Backup contains:** app.ini (all secrets), database.db (user hashes), full nginx config

### Node Secret Authentication Bypass
- **Status:** VALIDATED — full admin API access confirmed
- **Header:** `X-Node-Secret: c64d7ca1-19cb-4ebe-96d4-49037e7df78e`
- **Scope:** Bypasses AuthRequired() middleware, grants admin-equivalent access
- **Source code ref:** internal/middleware/middleware.go:72

### Authenticated RCE via Config Edit
- **Status:** UNTESTED — requires ELLIOT
- **Method:** Edit nginx config to inject malicious directive, then reload
- **Endpoints:** POST /api/config (edit any config file), POST /api/nginx/reload
- **Neither requires RequireSecureSession()**

## Vulnerability Primitive
- **Primitive:** Authenticated arbitrary file write to nginx config directory + service reload trigger
- **Delivery forms:**
  1. Direct config edit via POST /api/config with `path` and `content` fields
  2. Site config edit via POST /api/sites/:name/advance
  3. Settings CRLF injection (CVE-2024-23828) — requires RequireSecureSession, less likely
- **Defenses observed:** RequireSecureSession on terminal and settings-save. Config edit is NOT protected.
- **Untested forms:** Site advanced edit, stream config edit

## Credentials Recovered

| Username | Type | Hash/Secret | Context |
|----------|------|-------------|---------|
| admin | bcrypt | $2a$10$8YdBq4e.WeQn8gv9E0ehh.quy8D/4mXHHY4ALLMAzgFPTrIVltEvm | Nginx UI |
| jonathan | bcrypt | $2a$10$8M7JZSRLKdtJpx9YRUNTmODN.pKoBsoGCBi5Z8/WVGO2od9oCSyWq | Nginx UI + possible SSH |
| (app) | JWT Secret | 6c4af436-035a-4942-9ca6-172b36696ce9 | Token signing |
| (app) | Crypto Secret | 5c942292647d73f597f47c0be2237bf7347cdb70a0e8e8558e448318862357d6 | OTP encryption |
| (app) | Node Secret | c64d7ca1-19cb-4ebe-96d4-49037e7df78e | Admin API bypass |

## Nginx Config (from backup)
- snapped.htb: static site at /var/www/html/snapped
- admin.snapped.htb: proxy to 127.0.0.1:9000 (Nginx UI)
- Nginx UI runs on port 9000, config dir /etc/nginx, PID at /run/nginx.pid
- Reload cmd: `nginx -s reload`
- Restart cmd: `start-stop-daemon --start --quiet --pidfile /run/nginx.pid --exec /usr/sbin/nginx`

## Decision Log
1. Full scan → 2 ports (SSH + HTTP)
2. Vhost fuzz → discovered admin.snapped.htb (Nginx UI)
3. CVE research → CVE-2026-27944 identified
4. Backup download + decrypt → all secrets extracted
5. Node secret auth → admin API access validated
6. Source code review → config edit + reload = RCE path confirmed
7. **Decision: proceed to exploitation handoff**

---

## Privilege Escalation — CVE-2026-3888

### Summary
snapd 2.63.1 snap-confine TOCTOU race condition. SUID-root snap-confine creates "mimics" using /tmp/.snap/ as safe-keeping. systemd-tmpfiles deletes /tmp/.snap after 30 days. Attacker recreates with malicious content. Next mimic creation bind-mounts attacker files as root.

### Target State
- snapd 2.63.1 (vuln, patch 2.73+)
- snap-confine: SUID root at /usr/lib/snapd/snap-confine
- /tmp/.snap: ABSENT (exploit ready)
- Firefox snap rev 4793 (triggers mimics for /usr/lib/x86_64-linux-gnu)
- Namespace cached at /run/snapd/ns/firefox.mnt
- No gcc on target, no sudo

### Attack Vectors
1. **Primary**: AF_UNIX backpressure race — single-step snap-confine via debug output, replace /tmp/.snap dir during pause
2. **Simpler**: Pre-stage ld.so.preload inside sandbox, trigger fresh namespace
3. **Sandbox escape**: SUID bash at /var/snap/firefox/common/ (shared inside/outside sandbox)

### Compilation
- Kali is ARM, target is x86_64
- x86_64-linux-gnu-gcc installed and verified
- Cross-compile librootshell.so and race helper, upload via SCP

### Decision Log (continued)
8. CVE-2026-3888 identified via box name hint + snapd version
9. /tmp/.snap absent confirmed — exploit in ready state
10. Firefox fstab confirms mimic creation for /usr/lib/x86_64-linux-gnu
11. x86_64 cross-compiler installed on Kali
12. **Decision: ELLIOT privesc handoff with full exploit guide**
