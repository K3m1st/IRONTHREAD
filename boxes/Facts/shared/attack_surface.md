# Attack Surface — Facts
> Last updated: 2026-03-18T19:28:00-05:00
> Operation status: **COMPLETE** — both flags captured

## Service Inventory

| Port | Service | Version | Confidence | Exposure |
|------|---------|---------|------------|----------|
| 22 | SSH | OpenSSH 9.9p1 Ubuntu 3ubuntu3.2 | HIGH | Medium — SSH key recovered (encrypted) |
| 80 | HTTP | nginx 1.26.3 → CamaleonCMS 2.9.0 (Rails 8.0.2.1) | HIGH | **Critical** — CVEs confirmed and exploited |
| 54321 | HTTP | MinIO/LocalStack S3 API | HIGH | **Compromised** — S3 credentials extracted |

## Architecture

```
Internet → nginx:80 → CamaleonCMS (Rails 8.0.2.1) on 127.0.0.1:3000 [user: trivia]
                    → /randomfacts/* proxied to MinIO:54321
         → MinIO:54321 (S3 API, direct access) [service: ministack, user: root]
         → MinIO:9001 (console, localhost-only)
         → SSH:22
```

- App directory: `/opt/factsapp`
- App runs as user **trivia** (uid 1000)
- ministack.service runs as **root** from `/root/ministack/staging/start.sh`
- Database: SQLite3 at `/opt/factsapp/storage/production.sqlite3`
- Users with shells: **trivia** (1000), **william** (1001)

## Confirmed Exploits

### ★ CVE-2024-46987 — Path Traversal (CONFIRMED WORKING)
- Endpoint: `/admin/media/download_private_file?file=../../../../../../{path}`
- Status: **EXPLOITED** — arbitrary file read confirmed
- Files extracted: /etc/passwd, nginx config, systemd services, Rails config, master.key, credentials.yml.enc, SQLite DB, SSH keys

### ★ CVE-2025-2304 — Mass Assignment Privesc (CONFIRMED WORKING)
- Endpoint: `/admin/users/5/updated_ajax`
- Payload: `password[role]=admin`
- Status: **EXPLOITED** — our user `oracletest` is now Administrator

## Credentials Recovered

| Type | Value | Source |
|------|-------|--------|
| CMS Admin hash | `$2a$12$9lLBXaBzcTxohKjxX08aR.WmE7qyhwpl0NGGBLbKDi6t.PB5zdJcK` | SQLite DB |
| CMS Admin user | admin / admin@local.com | SQLite DB |
| S3 Access Key | `AKIA1F2BD38BAB3EADE7` | CamaleonCMS DB (cama_metas) |
| S3 Secret Key | `KKHqSdHmMeAkiIryZZaSbTyTH92t7Zb7XWB31g9q` | CamaleonCMS DB (cama_metas) |
| S3 Endpoint | `http://localhost:54321` | CamaleonCMS DB |
| S3 Bucket | `randomfacts` | CamaleonCMS DB |
| Rails master.key | `b0650437b2208a9fab449fb92f67bc40` | Path traversal |
| Rails secret_key_base | `885783371cea8f8cd...` (128 char) | Decrypted credentials.yml.enc |
| SSH private key (trivia) | Encrypted (aes256-ctr/bcrypt) | MinIO `internal` bucket |
| SSH authorized_keys (trivia) | ed25519 public key | Path traversal + MinIO |
| CMS registered user | `oracletest` / `P@ssw0rd123!` (admin role) | Self-registered |

## MinIO/S3 Findings

Two buckets discovered:
- `randomfacts` — public, images only
- `internal` — **contains trivia's home directory** including SSH keys, .bashrc, .bundle cache

## Attack Paths (updated)

### Path A — SSH Key Passphrase Crack → Shell as trivia
- **Confidence**: MEDIUM (depends on passphrase strength)
- **Complexity**: LOW (if cracked)
- **Status**: IN PROGRESS — john running against rockyou

### Path B — CamaleonCMS File Write (CVE-2024-46986) → RCE as trivia
- **Confidence**: MEDIUM
- **Complexity**: MEDIUM
- **Status**: UNEXPLORED
- **Note**: CVE-2024-46986 affects < 2.8.2, but target is 2.9.0. The fix may have been applied. Need to test if the upload traversal still works on 2.9.0 or if there's a bypass.

### Path C — Rails Secret Key Base → Session Forgery / Deserialization
- **Confidence**: MEDIUM
- **Complexity**: HIGH
- **Status**: UNEXPLORED
- **Note**: Rails 8.0.2.1 with known secret_key_base. Could forge session cookies or attempt deserialization attack. Rails 8 uses newer serialization which may limit this.

### Path D — S3 Bucket Write → Drop SSH Key / Overwrite Config
- **Confidence**: HIGH
- **Complexity**: LOW
- **Status**: UNEXPLORED
- **Note**: The `internal` bucket contains trivia's home directory. If we can **write** to it, we could drop an authorized_keys or modify .bashrc. The S3 credentials likely have write access since the CMS uses them for media uploads.

## Vulnerability Primitive

**Primary primitive**: Unsanitized file path control in MediaController
- **What the attacker controls**: File path parameter in download and upload endpoints
- **Delivery forms**: Relative traversal confirmed working
- **Defenses observed**: None at application level
- **Untested forms**: Upload traversal on 2.9.0

**Secondary primitive**: S3 bucket write access
- **What the attacker controls**: Object creation/modification in MinIO buckets
- **Delivery forms**: PutObject via S3 API with extracted credentials
- **Defenses observed**: None — credentials extracted
- **Untested forms**: Write to `internal` bucket to plant SSH key or backdoor

## Decision Log

| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-18 19:00 | Full port scan | Standard Phase 1 | 3 ports: 22, 80, 54321 |
| 2026-03-18 19:01 | WhatWeb + manual | Identify stack | CamaleonCMS 2.9.0 on Rails |
| 2026-03-18 19:05 | Skip Phase 3, go to exploitation | HIGH confidence CVEs + open registration | Operator confirmed |
| 2026-03-18 19:10 | Register + test CVE-2024-46987 | Path traversal for file read | CONFIRMED — arbitrary file read |
| 2026-03-18 19:12 | Extract configs | Identify app architecture and creds | Rails config, S3 creds, SSH key extracted |
| 2026-03-18 19:15 | Exploit CVE-2025-2304 | Escalate to admin | CONFIRMED — admin access |
| 2026-03-18 19:16 | S3 bucket enumeration | Use extracted creds | `internal` bucket contains trivia's home dir + SSH key |
| 2026-03-18 19:20 | Crack SSH key + plan S3 write | Dual-path approach | Cracking in progress |

## Session Log

| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Exploitation → Privesc | Both CVEs confirmed. S3 creds → SSH key from MinIO bucket → cracked passphrase → SSH as trivia → sudo facter → root | Complete |

## Flags

| Flag | Value | Method |
|------|-------|--------|
| User | `c9c893330f8a88c388745862a2ccd223` | SSH as trivia → read /home/william/user.txt |
| Root | `6af031dd9e664c8e9ec6383ba8308a2e` | sudo facter --custom-dir with malicious Ruby fact |

## Full Attack Chain

1. **Recon**: nmap → 3 ports (22, 80, 54321). CamaleonCMS 2.9.0 on port 80, MinIO on 54321
2. **Registration**: Open registration at /admin/register (CAPTCHA solved manually)
3. **CVE-2024-46987**: Path traversal → read Rails config, database, master.key
4. **CVE-2025-2304**: Mass assignment → escalated to CMS admin (bonus, not needed for foothold)
5. **S3 Credential Extraction**: CamaleonCMS database contained MinIO access/secret keys
6. **MinIO Enumeration**: Found `internal` bucket containing trivia's home directory + encrypted SSH key
7. **SSH Key Crack**: john + rockyou → passphrase `dragonballz`
8. **SSH Foothold**: SSH as trivia → user flag in /home/william/user.txt
9. **Privesc**: `sudo /usr/bin/facter --custom-dir /tmp/facts/` with malicious Ruby fact → root
