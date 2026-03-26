# NOIRE Findings
> Target: 10.129.244.220 (principal)
> Current Access: svc-deploy / user (uid=1001)
> Date: 2026-03-24

## Access Context
- User: svc-deploy (uid=1001, gid=1002)
- Groups: svc-deploy(1002), deployers(1001)
- Shell: /bin/bash via SSH, full TTY, stable
- sudo: NOT permitted (`user svc-deploy may not run sudo on principal`)
- Only interactive users: root, svc-deploy (all others nologin)
- Empty bash_history, no SSH keys in ~/.ssh (only known_hosts)

## System Profile
- OS: Ubuntu 24.04.4 LTS (Noble Numbat)
- Kernel: 6.8.0-101-generic x86_64
- Hostname: principal
- Not containerized (bare metal/VM)
- Services: sshd (22), Jetty/Java app (8080, runs as `app` user), containerd, systemd-resolved (53)
- Audit: auditd + laurel active

## High-Value Findings
| Finding | Evidence | Why It Matters | Confidence |
|---------|----------|----------------|------------|
| SSH CA private key readable by svc-deploy | `/opt/principal/ssh/ca` is `rw-r-----` root:deployers (3381 bytes, RSA 4096, unencrypted) | svc-deploy is in deployers group and can read the CA key that sshd trusts for cert-based auth | HIGH |
| sshd trusts this CA with no AuthorizedPrincipalsFile | `TrustedUserCAKeys /opt/principal/ssh/ca.pub` in `60-principal.conf`, no `AuthorizedPrincipalsFile` configured anywhere | Without AuthorizedPrincipalsFile, OpenSSH accepts any cert principal matching the target username — a cert with principal "root" grants root login | HIGH |
| PermitRootLogin prohibit-password | `60-principal.conf` sets `PermitRootLogin prohibit-password` | Root can log in via pubkey/cert but not password — cert forgery bypasses this | HIGH |

## Privilege Escalation Leads
| Rank | Path | Evidence | Complexity | Confidence |
|------|------|----------|------------|------------|
| 1 | **SSH CA cert forgery → root** | CA privkey readable at `/opt/principal/ssh/ca`. sshd trusts CA via `TrustedUserCAKeys`. No `AuthorizedPrincipalsFile` restriction. `PermitRootLogin prohibit-password` allows cert login. Steps: generate keypair, sign with CA key setting principal=root, SSH as root. | LOW | HIGH |
| 2 | H2 database credential reuse | `principal / Pr1nc1p@l_Db_2025!` in application.properties. Data dir (`/opt/principal/app/data/`) owned by `app` user, not readable by svc-deploy. H2 console disabled. | MEDIUM | LOW |

## Credentials And Secrets
- **SSH CA private key**: `/opt/principal/ssh/ca` — RSA 4096, unencrypted, readable by deployers group. Can sign SSH certificates trusted by this host's sshd.
- **SSH CA public key**: `/opt/principal/ssh/ca.pub` — world-readable at `/opt/principal/ssh/ca.pub`
- **H2 database creds**: `principal / Pr1nc1p@l_Db_2025!` — in `/opt/principal/app/src/main/resources/application.properties` (world-readable source). DB at `jdbc:h2:file:/opt/principal/app/data/principal`. Data dir not accessible to svc-deploy.
- **SSH password (already known)**: `svc-deploy / D3pl0y_$$H_Now42!` — used for current access

## Misconfigurations
| Category | Summary | Evidence |
|----------|---------|----------|
| File permissions | CA private key readable by deployers group | `-rw-r----- root:deployers /opt/principal/ssh/ca` — service account in deployers group can read the signing key |
| SSH config | No AuthorizedPrincipalsFile restricting cert principals | `AuthorizedPrincipalsFile` not set in sshd_config or 60-principal.conf — any principal in a trusted cert is accepted if it matches the login username |
| SSH config | sshd config readable by deployers group | `-rw-r----- root:deployers /etc/ssh/sshd_config.d/60-principal.conf` — exposes trust configuration |

## Anomalies
- `/opt/principal/deploy/` exists (root:root rwxr-x---) but is not accessible by svc-deploy despite svc-deploy being a "deploy" service account. May contain deployment scripts referenced in README.txt (`deploy.sh`).
- No deployers-writable files found anywhere on the filesystem — the group provides read-only access to CA material and sshd config.

## Oracle Flags
1. **IMMEDIATE: Forge SSH certificate for root** — svc-deploy can read the CA private key. Generate a keypair on the attacker machine, sign it with the CA key (principal=root), and SSH as root. This is trivial complexity and high confidence. Steps:
   - `ssh-keygen -t ed25519 -f /tmp/pwn -N ""`
   - Copy CA key to attacker, or sign on target: `ssh-keygen -s /opt/principal/ssh/ca -I root-cert -n root -V +1h /tmp/pwn.pub`
   - `ssh -i /tmp/pwn -o CertificateFile=/tmp/pwn-cert.pub root@10.129.244.220`
2. **LOW PRIORITY: H2 database** — Credential `principal / Pr1nc1p@l_Db_2025!` exists but data dir is inaccessible to svc-deploy. Only useful if we gain `app` user access or find another H2 interface.

## Tools Executed
| Tool | Command | Output File |
|------|---------|-------------|
| remote_exec | id; whoami; hostname; uname -a; cat /etc/os-release | memoria action log |
| remote_exec | sudo -S -l | memoria action log |
| remote_exec | cat /etc/passwd (interactive shells) | memoria action log |
| remote_exec | ls -la /opt/principal/ssh/ | memoria action log |
| remote_exec | cat /opt/principal/ssh/README.txt | memoria action log |
| remote_exec | cat /opt/principal/ssh/ca | memoria action log |
| remote_exec | cat /etc/ssh/sshd_config.d/60-principal.conf | memoria action log |
| remote_exec | cat /etc/ssh/sshd_config (cert/CA lines) | memoria action log |
| remote_exec | find / -group deployers | memoria action log |
| remote_exec | find / -group deployers -writable | memoria action log |
| remote_exec | ps aux | memoria action log |
| remote_exec | find / -perm -4000 (SUID) | memoria action log |
| remote_exec | find / -perm -2000 (SGID) | memoria action log |
| remote_exec | crontab -l; /etc/crontab; /etc/cron.d/; systemctl list-timers | memoria action log |
| remote_exec | getcap -r /; ss -tlnp | memoria action log |
| remote_exec | cat application.properties | memoria action log |
| remote_exec | ls /home; ls /root | memoria action log |
