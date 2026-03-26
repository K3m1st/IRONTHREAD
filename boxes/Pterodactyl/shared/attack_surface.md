# Attack Surface — Pterodactyl
> Last updated: 2026-03-18T23:50:00-05:00
> Operation status: POST-ACCESS — user flag obtained, privesc in progress

## Service Inventory

| Service | Port | Version | Confidence | Exposure |
|---------|------|---------|------------|----------|
| SSH | 22 | OpenSSH 9.6 | HIGH | Low — modern, no known CVEs |
| HTTP | 80 | nginx 1.21.5 + PHP 8.4.8 FPM | HIGH | **Critical** — multiple vhosts, vulnerable app |

### Virtual Hosts
| Hostname | Purpose | Status |
|----------|---------|--------|
| pterodactyl.htb | Landing page (MonitorLand) | phpinfo.php + changelog.txt exposed |
| panel.pterodactyl.htb | Pterodactyl Panel v1.11.10 | **Vulnerable to CVE-2025-49132** |
| play.pterodactyl.htb | Redirects to main | Low value |

## Attack Paths

### 1. CVE-2025-49132: Pterodactyl Panel Unauthenticated LFI→RCE
- **Confidence**: HIGH
- **Complexity**: LOW
- **Status**: UNEXPLORED — ready for exploitation
- **Evidence**:
  - Pterodactyl Panel v1.11.10 confirmed (changelog.txt)
  - Panel accessible at panel.pterodactyl.htb (confirmed)
  - All prerequisites confirmed via phpinfo: register_argc_argv=On, PEAR installed at /usr/share/php/PEAR, no disable_functions, no open_basedir
  - Public exploit available (exploit-db #52341, GitHub PoC)
  - CVSS 10.0 — unauthenticated, network-accessible, no user interaction

### 2. Credential Extraction via LFI (.env / config files)
- **Confidence**: HIGH
- **Complexity**: LOW
- **Status**: UNEXPLORED
- **Evidence**: LFI from CVE-2025-49132 can read Laravel .env (APP_KEY, DB creds, mail creds)

## Exploit Research

### CVE-2025-49132 — Pterodactyl Panel ≤ 1.11.10 Unauthenticated RCE
- **CVE**: CVE-2025-49132
- **CVSS**: 10.0 (AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:H/A:H)
- **Affected**: Pterodactyl Panel ≤ 1.11.10
- **Fixed in**: 1.11.11
- **Vulnerable endpoint**: `/locales/locale.json`
- **Parameters**: `locale`, `namespace` — passed to PHP `include()` unsanitized
- **Authentication**: None required
- **PoC available**: Yes — exploit-db #52341, GitHub (YoyoChaud/CVE-2025-49132)

### Vulnerability Primitive
- **Primitive**: Unsanitized file path passed to PHP `include()` — arbitrary local file inclusion
- **Delivery forms**:
  1. **pearcmd.php config-create** — write PHP webshell to disk via PEAR, then include it. Hex-encode commands to bypass URL encoding. PEAR path: `/usr/share/php/PEAR/pearcmd.php`
  2. **PHP filter chains** — use `php://filter` chains to achieve RCE without writing to disk
  3. **Laravel APP_KEY deserialization** — extract APP_KEY from .env via LFI, craft serialized gadget chain via phpggc
- **Defenses observed**: None — no WAF detected, no `hash` parameter enforcement, no input sanitization
- **Untested forms**: All three delivery forms are available and untested. pearcmd.php is highest reliability given confirmed PEAR installation and register_argc_argv=On.

### Environmental Fit Assessment
- ✅ Pterodactyl Panel v1.11.10 (exact vulnerable version)
- ✅ PHP 8.4.8 with FPM (compatible)
- ✅ register_argc_argv = On (required for pearcmd method)
- ✅ PEAR installed at /usr/share/php/PEAR (confirmed via phpinfo include_path)
- ✅ disable_functions = empty (no restrictions on system/exec/etc)
- ✅ open_basedir = empty (no path restrictions)
- ✅ No WAF or rate limiting detected
- **Reliability assessment**: VERY HIGH — all prerequisites confirmed, multiple RCE methods available

## Post-Access Attack Paths (Privesc)

### 1. Crack headmonitor bcrypt hash → SSH password reuse → sudo as root
- **Confidence**: MEDIUM
- **Complexity**: MEDIUM (hash not in rockyou)
- **Status**: IN PROGRESS — john running, need better wordlist
- **Evidence**: phileasfogg3's panel password = SSH password (confirmed reuse pattern). If headmonitor follows same pattern, cracking the hash gives SSH access. From headmonitor, sudo as root may be possible (targetpw means we need root's password, but headmonitor being admin may have it).

### 2. Pterodactyl Panel admin → discover headmonitor's credentials
- **Confidence**: MEDIUM
- **Complexity**: LOW
- **Status**: ACTIVE — logged in as admin headmonitor (password reset to 'Hacked123')
- **Evidence**: Admin access to panel, can view server configs, API keys, etc.

### 3. Wings daemon abuse → root
- **Confidence**: LOW (currently blocked)
- **Complexity**: HIGH
- **Status**: BLOCKED — Docker not installed
- **Evidence**: Wings runs as root, but requires Docker which is absent

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-18 21:21 | Full TCP scan + whatweb | Standard Phase 1 recon | 2 open ports, web stack identified |
| 2026-03-18 21:23 | Add pterodactyl.htb + play.pterodactyl.htb to /etc/hosts | nmap redirect + page content revealed subdomains | Enabled vhost enumeration |
| 2026-03-18 21:24 | Check phpinfo.php + changelog.txt | Standard web recon on landing page | Critical intel: exact versions, PEAR, no security restrictions |
| 2026-03-18 21:24 | Check panel.pterodactyl.htb | Pterodactyl box + panel install in changelog | Confirmed Pterodactyl Panel v1.11.10 |
| 2026-03-18 21:25 | CVE research for Pterodactyl Panel 1.11.10 | Known version, likely CVEs | CVE-2025-49132 — CVSS 10.0 unauthenticated RCE |
| 2026-03-18 21:30 | Deploy ELLIOT for CVE-2025-49132 | Operator confirmed, all prereqs met | RCE as wwwrun in 5 turns, user flag captured |
| 2026-03-18 21:35 | Post-access investigation via webshell | ELLIOT returned with foothold | Full enumeration: DB creds, Wings config, user hashes |
| 2026-03-18 23:35 | Crack bcrypt hashes with john | Need passwords for SSH/privesc | phileasfogg3 cracked: !QAZ2wsx. headmonitor NOT in rockyou. |
| 2026-03-18 23:48 | SSH as phileasfogg3, check sudo | Cracked password, test access | sudo (ALL) ALL but targetpw — need target's password |
| 2026-03-18 23:50 | Reset headmonitor panel password via DB | Need admin panel access | Success — admin access obtained |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Exploitation → Post-Access | CVE-2025-49132 RCE, user flag, DB creds, Wings config, cracked phileasfogg3, SSH access, sudo (ALL) ALL w/targetpw | Privesc blocked — need headmonitor's password |
