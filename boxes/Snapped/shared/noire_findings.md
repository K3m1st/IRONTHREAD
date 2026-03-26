# NOIRE Findings
> Target: Snapped (10.129.9.2)
> Current Access: jonathan / user (uid=1000)
> Date: 2026-03-25

## Access Context
- **User:** jonathan (uid=1000, gid=1000, groups=jonathan only)
- **Shell:** /bin/bash via SSH (password: linkinpark)
- **Shell quality:** Full interactive bash, no restrictions
- **Sudo:** Not permitted — "jonathan may not run sudo on snapped"
- **No other human users** — only jonathan has a home directory

## System Profile
- **Hostname:** snapped
- **OS:** Ubuntu 24.04.4 LTS (Noble Numbat)
- **Kernel:** 6.17.0-19-generic (very recent HWE kernel)
- **Containerization:** None — bare metal/VM
- **Key services:**
  - Nginx 1.24.0 — master runs as **root** (PID 1888), workers as www-data
  - Nginx UI 2.3.2 — runs as **www-data** (PID 1858), listening on 127.0.0.1:9000
  - CUPS 2.4.7 / cups-browsed 2.0.0 — listening on 127.0.0.1:631
  - SSH OpenSSH 9.6p1

## High-Value Findings
| Finding | Evidence | Why It Matters | Confidence |
|---------|----------|----------------|------------|
| No OTP/2FA on any Nginx UI account | Database: otp_secret=None for admin (id=1) and jonathan (id=2) | JWT forgery only needs correct claims — no TOTP bypass required | HIGH |
| Nginx UI app.ini + database world-readable | 644 www-data:www-data at /usr/local/etc/nginx-ui/ | Any local user can read JWT secret, crypto secret, node secret, all bcrypt hashes | HIGH |
| Nginx master runs as root | ps aux: root 1888 nginx: master process | If www-data shell obtained, nginx restart path could lead to root code execution | HIGH |
| Terminal StartCmd = login | app.ini [terminal] section | Nginx UI terminal feature spawns `login` binary — could authenticate system users | MEDIUM |

## Privilege Escalation Leads
| Rank | Path | Evidence | Complexity | Confidence |
|------|------|----------|------------|------------|
| 1 | JWT forgery → Nginx UI authenticated access → terminal/settings | JWT secret known, no OTP required. Need correct claim structure from source code. Terminal gives www-data context. Settings modification (restart_cmd) needs SecureSession which JWT may provide. | MEDIUM | HIGH |
| 2 | www-data → root via nginx control | Nginx master is root. If www-data obtained, nginx-ui can restart nginx. If config write is possible from www-data context (app.ini writable by www-data), manipulating RestartCmd or nginx config could yield root exec. | HIGH | MEDIUM |
| 3 | Crack admin bcrypt hash | $2a$10$8YdBq4e.WeQn8gv9E0ehh.quy8D/4mXHHY4ALLMAzgFPTrIVltEvm — cost 10. If cracked, admin may have a different system password or provide Nginx UI panel access. | MEDIUM | LOW |

## Credentials And Secrets
- **JWT Secret:** 6c4af436-035a-4942-9ca6-172b36696ce9 (from /usr/local/etc/nginx-ui/app.ini, world-readable)
- **Crypto Secret:** 5c942292647d73f597f47c0be2237bf7347cdb70a0e8e8558e448318862357d6 (same file)
- **Node Secret:** c64d7ca1-19cb-4ebe-96d4-49037e7df78e (same file)
- **Admin bcrypt hash:** $2a$10$8YdBq4e.WeQn8gv9E0ehh.quy8D/4mXHHY4ALLMAzgFPTrIVltEvm (database.db)
- **Jonathan bcrypt hash:** $2a$10$8M7JZSRLKdtJpx9YRUNTmODN.pKoBsoGCBi5Z8/WVGO2od9oCSyWq → cracked: linkinpark
- **Cert email:** admin@test.htb (from app.ini [cert] section)

## Misconfigurations
| Category | Summary | Evidence |
|----------|---------|----------|
| File permissions | Nginx UI config and database world-readable (644) | /usr/local/etc/nginx-ui/app.ini and database.db owned www-data:www-data with 644 perms |
| .bash_history | Owned by root, 0 bytes — deliberately locked | -rw-r--r-- 1 root jonathan 0 .bash_history |

## Anomalies
- **Nginx UI binary owned by uid 1001** — no user with uid 1001 exists in /etc/passwd. Binary at /usr/local/bin/nginx-ui is 755 UNKNOWN:UNKNOWN. Suggests it was copied from a build system or container with a different user mapping.
- **Database path mismatch** — app.ini [database] says Path=/var/lib/nginx-ui/database.db but that directory is empty. Active database is at /usr/local/etc/nginx-ui/database.db (same directory as app.ini). Nginx UI may use a relative path fallback.

## Oracle Flags
1. **CRITICAL: Research Nginx UI JWT claim structure** — The JWT secret is known and no OTP is required. Oracle needs the exact JWT payload format from Nginx UI source code (GitHub: 0xJacky/nginx-ui). Key questions: What field identifies the user (uid? user_id? sub?)? What constitutes a SecureSession token vs regular auth?
2. **Research Nginx UI v2.3.2 CVEs** — Version now confirmed. Check for template injection (CVE-2024-22197 and similar), terminal WebSocket auth bypass, or config write bypasses specific to this version.
3. **Consider www-data → root chain** — If www-data shell is obtained, investigate: Can www-data write to app.ini to change RestartCmd? Can www-data write nginx configs via a path ELLIOT didn't try? Does the nginx restart (start-stop-daemon) execute RestartCmd as root or www-data?
4. **Admin hash cracking** — Low priority but run in background. Cost factor 10 bcrypt.

## Dead Ends
- sudo: jonathan has no sudo privileges at all
- SUID/SGID: all standard Ubuntu binaries, nothing custom
- Capabilities: only ping, mtr-packet, gst-ptp-helper (standard)
- Writable files: none outside /home/jonathan, /tmp, /var/tmp
- SSH keys: empty authorized_keys, no private keys
- Cron/timers: all standard system timers, no custom jobs
- Kernel: 6.17.0-19-generic is very recent — unlikely exploitable
- Sudo version: 1.9.15p5 — current

## Tools Executed
| Tool | Command | Output File |
|------|---------|-------------|
| remote_exec | id; hostname; uname -a; cat /etc/os-release | inline |
| remote_exec | sudo -S -l | inline |
| remote_exec | find / -perm -4000/-2000 | inline |
| remote_exec | getcap -r / | inline |
| remote_exec | ps aux | inline |
| remote_exec | ss -tlnp/-ulnp | inline |
| remote_exec | cat app.ini; ls nginx-ui dir | inline |
| remote_exec | systemctl cat nginx-ui.service/nginx.service | inline |
| remote_exec | python3 sqlite3 database query | inline |
| remote_exec | find writable files/dirs | inline |
| remote_exec | cat /etc/nginx configs | inline |
| remote_exec | /proc/1858/status (caps check) | inline |
