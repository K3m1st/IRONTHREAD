# Post-Access Investigation Findings — Pterodactyl
> Date: 2026-03-18 | Shell: wwwrun@pterodactyl + SSH phileasfogg3@pterodactyl

## Access Context
- **wwwrun** (uid=474, gid=477 www) — webshell via CVE-2025-49132
- **phileasfogg3** (uid=1002, gid=100 users) — SSH with cracked password `!QAZ2wsx`

## System Profile
- **OS**: openSUSE Leap (SUSE-based), kernel 6.4.0-150600.23.65-default x86_64
- **Hostname**: pterodactyl
- **Filesystem**: btrfs with snapper (not configured)

## Users with Login Shells
| User | UID | Home | Notes |
|------|-----|------|-------|
| root | 0 | /root | Standard |
| nobody | 65534 | /var/lib/nobody | Standard |
| headmonitor | 1001 | /home/headmonitor (drwxr-x---) | **Privesc target**, restricted home, Wings system user |
| phileasfogg3 | 1002 | /home/phileasfogg3 (drwxr-xr-x) | Cracked: `!QAZ2wsx`, has sudo (ALL) ALL but targetpw |

## Sudo
- **wwwrun**: requires password (no passwordless sudo)
- **phileasfogg3**: `(ALL) ALL` — but `targetpw` is set globally, meaning sudo requires the TARGET user's password, not phileasfogg3's

## SUID Binaries
Standard binaries only: sudo, chfn, chsh, expiry, gpasswd, newgidmap, newgrp, newuidmap, passwd, mount, su, umount, fusermount, crontab. No custom SUID.

## Listening Services
| Port | Service | Bind | Notes |
|------|---------|------|-------|
| 22 | SSH | 0.0.0.0 | OpenSSH 9.6 |
| 25 | SMTP | 127.0.0.1 | Postfix |
| 80 | HTTP | 0.0.0.0 | nginx |
| 3306 | MariaDB | 127.0.0.1 | Panel DB |
| 6379 | Redis | 127.0.0.1 | No auth |
| 9000 | PHP-FPM | 127.0.0.1 | Panel backend |

## Credential Harvest
| Credential | Value | Source |
|-----------|-------|--------|
| MariaDB panel | pterodactyl:PteraPanel | .env |
| APP_KEY | base64:UaThTPQnUjrrK61o+Luk7P9o4hM+gl4UiMJqcbTSThY= | .env |
| HASHIDS_SALT | pKkOnx0IzJvaUXKWt2PK | .env |
| Wings token | fyqnJBhstNPUR8lN / nrV4yF4x7e0KkVaab4ptA1XZJwlExVJzUJnWqOeczWfTZnOb5avVzE9CynifW4ax | /etc/pterodactyl/config.yml |
| headmonitor panel hash | $2y$10$3WJht3/5GOQmOXdljPbAJet2C6tHP4QoORy1PSj59qJrU0gdX5gD2 | MariaDB |
| phileasfogg3 panel pass | !QAZ2wsx (cracked bcrypt) | MariaDB → john |
| phileasfogg3 SSH pass | !QAZ2wsx (confirmed via SSH) | Password reuse |

## Wings Daemon
- **Binary**: /usr/local/bin/wings
- **Config**: /etc/pterodactyl/config.yml
- **Runs as**: root
- **Status**: INACTIVE (dead) — Docker not installed
- **System user UID**: 1001 = headmonitor
- **API port**: 8080 (bound 0.0.0.0 but firewalled)
- **SFTP port**: 2022

## Panel Database Intel
- headmonitor = admin (root_admin=1)
- phileasfogg3 = regular user (root_admin=0)
- Server "MonitorLand" (Bungeecord) owned by headmonitor, status=installing
- Node deployment API key: ptla_tA4XuTcamhI
- user_ssh_keys table: empty

## Writable Paths (wwwrun)
- /var/www/pterodactyl/ (entire application)
- /var/lib/wwwrun/.bash_history, .viminfo

## Processes of Interest
- **laurel** (PID 723) — audit log enrichment tool
- **auditd** (PID 720) — audit daemon (high CPU)
- **cron** (PID 3070) — running as root
- **PHP-FPM master** — running as root, workers as wwwrun

## What is NOT Present
- No custom SUID binaries
- No Docker (Wings dead)
- No capabilities on files
- No writable files in /etc (as wwwrun)
- No SSH keys for headmonitor
- /opt is empty
- /etc/cron.d is empty
- No snapper configured
- headmonitor's password NOT in rockyou.txt

## Privesc Lead Ranking

### 1. Crack headmonitor's panel hash → test for SSH password reuse
- **Status**: IN PROGRESS — not in rockyou, need different wordlist
- **Rationale**: If headmonitor reuses panel password for SSH, we get headmonitor. From headmonitor, phileasfogg3 can sudo -u headmonitor with headmonitor's password (targetpw), but direct SSH is simpler.

### 2. targetpw sudo abuse — find any password for root or headmonitor
- **Status**: BLOCKED — need target user's password
- **Rationale**: phileasfogg3 has (ALL) ALL sudo but targetpw means we need the target's password

### 3. Abuse Pterodactyl Panel as admin headmonitor
- **Status**: ACTIVE — We reset headmonitor's panel password to 'Hacked123' and have admin access
- **Rationale**: Admin panel might reveal hidden functionality or allow starting Wings

### 4. Wings daemon — if we can start it, it runs as root
- **Status**: BLOCKED — Docker not installed, can't start Wings
