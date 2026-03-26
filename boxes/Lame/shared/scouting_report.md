# Scouting Report — Lame
> Target: 10.129.8.218 | Date: 2026-03-24 | Status: COMPLETE

## Target Profile
- **IP:** 10.129.8.218
- **Hostname:** lame (FQDN: lame.hackthebox.gr)
- **OS:** Linux (Ubuntu/Debian-based) — HIGH confidence
- **Domain:** hackthebox.gr

## Service Inventory

| Port | Service | Version | Confidence |
|------|---------|---------|------------|
| 21/tcp | FTP | vsftpd 2.3.4 | HIGH |
| 22/tcp | SSH | OpenSSH 4.7p1 Debian 8ubuntu1 | HIGH |
| 139/tcp | NetBIOS/SMB | Samba smbd 3.0.20-Debian | HIGH |
| 445/tcp | SMB | Samba smbd 3.0.20-Debian | HIGH |
| 3632/tcp | distccd | distccd v1 (GNU 4.2.4) | HIGH |

## File Sharing
- **FTP:** Anonymous login allowed (nmap code 230), but empty listing
- **SMB:** Null session successful. Shares: `print$`, `tmp` ("oh noes!"), `opt`, `IPC$`, `ADMIN$`
  - Message signing disabled
  - SMB2 negotiation failed (SMB1 only)

## Remote Access
- **SSH:** OpenSSH 4.7p1 — very old, useful for stable shell post-exploitation

## Key Findings
1. **Samba 3.0.20** — CVE-2007-2447 username map script RCE (root)
2. **vsftpd 2.3.4** — CVE-2011-2523 backdoor (may be non-functional)
3. **distccd** — CVE-2004-2687 RCE (low-priv daemon user)

## Anomalies
- SMB `tmp` share comment "oh noes!" — deliberate exposure, likely writable

## Recommendations
1. Exploit Samba CVE-2007-2447 for direct root — trivial, highest confidence
2. Test vsftpd backdoor as backup — unreliable on HTB
3. distccd RCE as last resort — user shell only, needs privesc
