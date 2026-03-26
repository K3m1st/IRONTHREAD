# Attack Surface — Lame
> Last updated: 2026-03-24T17:30Z
> Operation status: EXPLOITATION PHASE

## Service Inventory

| Port | Service | Version | Confidence | CVE |
|------|---------|---------|------------|-----|
| 21/tcp | FTP | vsftpd 2.3.4 | HIGH | CVE-2011-2523 |
| 22/tcp | SSH | OpenSSH 4.7p1 Debian 8ubuntu1 | HIGH | — |
| 139/tcp | NetBIOS/SMB | Samba 3.0.20-Debian | HIGH | CVE-2007-2447 |
| 445/tcp | SMB | Samba 3.0.20-Debian | HIGH | CVE-2007-2447 |
| 3632/tcp | distccd | distccd v1 (GNU 4.2.4) | HIGH | CVE-2004-2687 |

## Attack Paths

### 1. Samba 3.0.20 — CVE-2007-2447 (username map script RCE)
- **Confidence:** HIGH
- **Complexity:** LOW (trivial — single command)
- **Yield:** Root shell
- **Status:** UNEXPLORED
- **Evidence:** Confirmed Samba 3.0.20 via nmap. Affected range: 3.0.0-3.0.25rc3. No auth required. Metasploit module + standalone Python PoCs available. Executes as root.

### 2. vsftpd 2.3.4 — CVE-2011-2523 (backdoor)
- **Confidence:** MEDIUM
- **Complexity:** LOW
- **Yield:** Root shell (if backdoor active)
- **Status:** UNEXPLORED
- **Evidence:** Version confirmed. Backdoor triggers shell on port 6200 via `:)` in username. Often non-functional on HTB — only specific compromised binaries from Jun 30-Jul 3, 2011 window are affected.

### 3. distccd — CVE-2004-2687 (RCE via compilation jobs)
- **Confidence:** HIGH
- **Complexity:** LOW
- **Yield:** User shell (daemon user) — requires privesc
- **Status:** UNEXPLORED
- **Evidence:** Port 3632 open, distccd confirmed. No access restrictions. Metasploit module and nmap NSE script available.

## Exploit Research

### Vulnerability Primitive — CVE-2007-2447 (PRIMARY)
- **Primitive:** Unsanitized username string passed to /bin/sh via MS-RPC calls
- **Delivery forms:**
  - Shell metacharacters in SMB username (backticks, $(), semicolons)
  - Affects SamrChangePassword(), printer management, file share management MS-RPC calls
  - smbclient `logon` command with injected username
  - Direct MS-RPC via Python (impacket)
- **Defenses observed:** None — pre-authentication, no input sanitization
- **Untested forms:** All forms untested — first attempt pending

### Vulnerability Primitive — CVE-2011-2523 (BACKUP)
- **Primitive:** Username containing `:)` triggers backdoor listener on port 6200
- **Delivery forms:** FTP USER command with smiley
- **Defenses observed:** Backdoor may not be present in this binary
- **Untested forms:** Single delivery mechanism only

### Vulnerability Primitive — CVE-2004-2687 (FALLBACK)
- **Primitive:** Arbitrary command execution via distcc compilation job submission
- **Delivery forms:** Crafted compilation request to port 3632
- **Defenses observed:** None expected — misconfiguration, no ACL
- **Untested forms:** All untested

## Web Enumeration Findings
No web services detected. Web enumeration not warranted.

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-24T17:30Z | Skip web enumeration | No web services on target | Proceed to exploitation |
| 2026-03-24T17:30Z | Primary path: Samba CVE-2007-2447 | Direct root, trivial, highest confidence | Pending operator confirmation |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon + Analysis | 5 services, 3 attack paths, Samba RCE primary | Pending |
