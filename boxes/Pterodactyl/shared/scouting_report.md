# Scouting Report — Pterodactyl
> Date: 2026-03-18 | Target: 10.129.6.130 | Status: COMPLETE

## Target Profile
- **IP**: 10.129.6.130
- **Hostname**: pterodactyl.htb (+ panel.pterodactyl.htb, play.pterodactyl.htb)
- **OS**: Linux (SUSE-based), kernel 6.4.0-150600.23.65-default x86_64
- **OS Confidence**: HIGH (confirmed via phpinfo)

## Open Ports

| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 22 | SSH | OpenSSH 9.6 | HIGH | Protocol 2.0, ECDSA + ED25519 |
| 80 | HTTP | nginx 1.21.5 | HIGH | Redirects to pterodactyl.htb, multiple vhosts |

Closed: 443 (https), 8080 (http-proxy)

## Web Services

### pterodactyl.htb (port 80)
- **Stack**: nginx 1.21.5 + PHP 8.4.8 (FPM/FastCGI)
- **Content**: "MonitorLand" Minecraft community landing page
- **Notable**: phpinfo.php exposed, changelog.txt accessible
- **Server IP reference**: play.pterodactyl.htb

### panel.pterodactyl.htb (port 80)
- **Application**: Pterodactyl Panel v1.11.10
- **Framework**: Laravel (React SPA frontend)
- **Cookies**: XSRF-TOKEN, pterodactyl_session
- **Recaptcha**: Disabled
- **Auth**: Redirects unauthenticated to /auth/login

### play.pterodactyl.htb (port 80)
- 302 redirects to pterodactyl.htb (main landing page)

## Critical Intelligence from phpinfo.php

| Setting | Value | Significance |
|---------|-------|--------------|
| disable_functions | (empty) | No function restrictions — full RCE if code execution achieved |
| open_basedir | (empty) | No path restrictions — full filesystem access |
| register_argc_argv | On | Required for pearcmd.php exploitation |
| include_path | .:/usr/share/php8:/usr/share/php/PEAR | PEAR in include path |
| allow_url_fopen | On | Can read remote URLs |
| file_uploads | On | File uploads enabled |
| PHP-FPM user | wwwrun:www | Service account context |

## Critical Intelligence from changelog.txt

- Pterodactyl Panel **v1.11.10** installed
- **MariaDB 11.8.3** backend
- **PHP-PEAR** explicitly installed for package management
- **phpinfo()** intentionally added as "temporary PHP debugging"
- PHP-FPM enabled across all domains

## Anomalies
1. phpinfo.php left exposed — massive information disclosure
2. changelog.txt publicly accessible with exact version details

## Recommendations
1. **PRIMARY**: Exploit CVE-2025-49132 on panel.pterodactyl.htb (unauthenticated LFI→RCE, CVSS 10.0)
2. **SECONDARY**: Extract .env credentials via LFI before RCE
