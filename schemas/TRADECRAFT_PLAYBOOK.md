# IRONTHREAD Tradecraft Playbook
> Operational discipline reference for all agents. Derived from public APT tradecraft analysis.
> This document is prescriptive — agents MUST follow these patterns when opsec_profile is MODERATE or GHOST.

---

## Philosophy

**Think like Volt Typhoon, not like a CTF speedrunner.**

The difference between a pentest tool dump and a red team operation is *discipline*:
- Every command has a purpose. If you can't articulate why you're running it, don't.
- Never run a command whose output you already have in memoria.
- Prefer reading files over executing binaries. `/proc` reads don't generate `execve` audit events.
- Batch related checks into single commands. Each SSH command is a separate log entry.
- Spread activity over time. Burst patterns are the #1 correlation signal for SIEM rules.

---

## 1. Post-Access Enumeration Discipline

### 1.1 The Golden Rule: Query Memoria First

Before running ANY enumeration command on target, check what's already known:
```
memoria_query_target(target_id) → existing services, findings, credentials
```

If memoria already has the OS, hostname, user context — **do not re-run** `id`, `whoami`, `uname -a`.
The previous agent already captured this. Use it.

### 1.2 Enumeration Sequence (Ordered by Noise Level)

Run in this order. Stop when you have enough to identify a privesc path.
Do NOT run the full checklist on every host — adapt based on what you learn.

**Tier 1 — Silent (no execve, pure file reads)**
These generate zero audit events on most configurations:

| Intent | Command | Why it's quiet |
|--------|---------|----------------|
| Current user context | `cat /proc/self/status` | File read, no binary execution |
| Hostname | `cat /proc/sys/kernel/hostname` | File read |
| OS/kernel | `cat /proc/version` | File read |
| Network connections | `cat /proc/net/tcp` | File read, replaces `ss`/`netstat` |
| Network interfaces | `cat /proc/net/if_inet6` or `ip -br a` | File read or low-noise binary |
| ARP neighbors | `cat /proc/net/arp` | File read, discover adjacent hosts |
| DNS config | `cat /etc/resolv.conf` | File read |
| Memory info | `cat /proc/meminfo` | File read |
| Process list | `ls /proc/[0-9]*/cmdline` | Directory listing |

**Tier 2 — Low Noise (standard binaries, individually unremarkable)**
Run these with 15-30s spacing when profile is MODERATE, 60-120s for GHOST:

| Intent | Command | Notes |
|--------|---------|-------|
| User context (if /proc insufficient) | `id` | Single command, covers uid/gid/groups |
| Group memberships | `groups` | Check for sudo/wheel/docker/lxd |
| Users with shells | `getent passwd \| grep -v nologin \| grep -v false` | Prefer `getent` over `cat /etc/passwd` |
| Sudo privileges | `sudo -n -l 2>/dev/null` | `-n` = non-interactive, fails silently if password needed |
| Home directories | `ls /home/` | Just list, don't recurse |
| Listening services | `ss -tlnp` | One command, captures all listeners |

**Tier 3 — Moderate Noise (triggers specific detection rules)**
Only run when Tier 1-2 didn't reveal a clear path. Space by 60s+ minimum:

| Intent | Command | Detection Risk |
|--------|---------|---------------|
| SUID binaries | `find /usr/bin /usr/sbin /usr/local/bin -perm -4000 -type f 2>/dev/null` | Elastic `5b06a27f` — scoped to binary dirs, not `/` |
| Capabilities | `getcap /usr/bin/python3 /usr/bin/perl /usr/bin/vim /usr/bin/ruby /usr/sbin/tcpdump 2>/dev/null` | Targeted, not `getcap -r /` (Sigma `fe10751f`) |
| Cron jobs | `cat /etc/crontab; ls /etc/cron.d/` | Single read, don't enumerate all cron dirs |
| Running processes | `ps -eo user,pid,ppid,comm --no-headers` | Minimal output format |
| Writable paths | `stat -c '%a %U %G %n' /tmp /var/tmp /dev/shm /opt` | Targeted checks, not `find / -writable` |
| SSH authorized keys | `cat ~/.ssh/authorized_keys 2>/dev/null` | Only current user's, targeted |

**Tier 4 — Noisy (only with explicit justification)**
Document WHY before running these. Each one should be logged as a deliberate decision:

| Intent | Command | Why it's noisy |
|--------|---------|----------------|
| Full SUID scan | `find / -perm -4000 -type f 2>/dev/null` | Recursive traversal, massive syscall volume, Elastic rule fires |
| Full capability scan | `getcap -r / 2>/dev/null` | Recursive, Sigma rule fires |
| Writable file discovery | `find / -writable -type f ...` | Recursive traversal |
| Config password grep | `find /etc -name "*.conf" -exec grep -l password {} \;` | Recursive + content scan |
| Shadow file | `cat /etc/shadow` | auditd file watch fires (Splunk `0419cb7a`) |

### 1.3 Command Batching Rules

**DO batch** related file reads into one command:
```bash
# Good: one SSH log entry, three file reads
cat /proc/self/status; cat /proc/sys/kernel/hostname; cat /proc/version
```

**DO NOT batch** unrelated enumeration that creates a discovery signature:
```bash
# Bad: this is a linpeas fingerprint
id; whoami; hostname; uname -a; cat /etc/os-release; sudo -l; find / -perm -4000
```

**Batch by intent:**
- System context: `cat /proc/version; cat /proc/sys/kernel/hostname` (one command)
- User context: `id` (one command — covers uid, gid, groups)
- Network: `cat /proc/net/tcp; cat /proc/net/arp; cat /etc/resolv.conf` (one command)
- Services: `ss -tlnp` (one command)
- Privesc checks: individual commands with spacing

### 1.4 Inter-Command Timing

| Profile | Min Delay | Max Delay | Jitter |
|---------|-----------|-----------|--------|
| LOUD | 0s | 0s | None |
| MODERATE | 15s | 45s | Random |
| GHOST | 60s | 180s | Gaussian |

Implementation: agents should note the opsec_profile from the operation config
and pace their `remote_exec` calls accordingly. When profile is MODERATE or GHOST,
every command gap should include a deliberate pause.

---

## 2. Credential Handling Discipline

### 2.1 Never Echo Passwords

**Forbidden:**
```bash
echo 'password' | sudo -S -l          # password in /proc/PID/cmdline + auditd EXECVE
echo 'password' | su - root            # same exposure
```

**Correct approach — check group membership first:**
```bash
# Step 1: Do you even need to test sudo?
id | grep -qE 'sudo|wheel|admin' && echo "HAS_SUDO_GROUP"

# Step 2: If you must test, use non-interactive check
sudo -n -l 2>/dev/null

# Step 3: If password is required and you have it, test via SSH
# (from attack box, not on target): ssh user@target "sudo -l"
```

### 2.2 Credential Storage

Store to memoria immediately upon discovery. Include:
- Where found (file path, config name)
- What it authenticates to (service, host)
- Whether verified (tested=true/false)
- Don't test credentials yourself (NOIRE). Log and hand back to Oracle.

---

## 3. File Operations Discipline

### 3.1 Artifact Naming

**Forbidden:** `/tmp/pwn`, `/tmp/exploit`, `/tmp/shell`, `/tmp/hack`

**Correct:** Use names that blend with the target environment:
- `.cache-session-XXXX` (looks like app cache)
- `.tmp.XXXXXX` (looks like mktemp output)
- Match naming patterns already present in the directory

### 3.2 Artifact Cleanup

After any file operation on target:
```bash
# Remove artifacts
shred -u /tmp/.cache-session-* 2>/dev/null

# If shred unavailable
dd if=/dev/urandom of=/tmp/artifact bs=1 count=$(stat -c%s /tmp/artifact) 2>/dev/null && rm /tmp/artifact
```

Clean up BEFORE disconnecting, not as an afterthought.

### 3.3 Key Generation

**Prefer generating keys locally (attack box) and delivering via the session.**

If you must generate on target:
- Use innocuous filenames
- Minimize validity period (`-V +1h` for certs — already good practice)
- Clean up immediately after use

---

## 4. Lateral Movement Discipline

### 4.1 SSH to Localhost

Localhost SSH connections are anomalous and easy to detect in auth.log.

**If you must:**
- Use `-o LogLevel=QUIET` to suppress client-side logging
- Clean auth.log entries if you have root (only with operator approval)
- Consider whether the same result can be achieved without a new SSH session

### 4.2 Credential Reuse

When Oracle authorizes credential testing:
- Test one service at a time
- Space attempts by 3+ minutes (under fail2ban default threshold of 5/600s)
- Never spray the same password across multiple hosts simultaneously
- Log every attempt to memoria

---

## 5. Reconnaissance Discipline (Pre-Access)

### 5.1 Scan Strategy by Profile

**LOUD:** `nmap -sS -sV -sC -T4 -p-` — full coverage, speed priority

**MODERATE:**
- Phase 1: `nmap -sS -T2 --max-rate 20 --top-ports 1000 --data-length 24` (no version detection yet)
- Phase 2: Targeted version detection only on open ports: `nmap -sV --version-intensity 0 -p <open_ports>`
- Phase 3: Script scan only on interesting services: `nmap --script <specific_script> -p <port>`
- Custom User-Agent for all HTTP probes

**GHOST:**
- Phase 1: Passive only — crt.sh, DNS records, OSINT
- Phase 2: `nmap -sS -T1 --max-rate 1 --top-ports 20 --data-length 32 --source-port 53`
- Phase 3: Manual banner grabs with `curl` / `nc` using browser User-Agent
- No NSE scripts (signature: SID 2024897)

### 5.2 Web Enumeration

**MODERATE:**
- Custom User-Agent matching a real browser
- gobuster: `-t 1 --delay 2s --no-error`
- Focus on technology-specific wordlists, not mega-lists
- Check `robots.txt` and `sitemap.xml` first — free intel

**GHOST:**
- Manual only. `curl` with full browser header set
- One request every 3-10 seconds
- No automated directory brute-forcing

---

## 6. Decision Framework: When to Stop Enumerating

### The "Three Leads" Rule

Once you have **three actionable privesc leads**, stop enumerating and return to Oracle.
Continuing beyond this point is noise for diminishing returns.

**Exceptions:**
- None of the three leads are HIGH confidence — continue to find a stronger path
- Operator explicitly requests exhaustive enumeration
- The host is unusually locked down and you need to be thorough

### The "Already Know This" Check

Before every `remote_exec`, ask:
1. Is this information already in memoria? → Skip
2. Did a previous agent already run this command? → Skip
3. Will this command's output change my ranked privesc leads? → If no, skip
4. Is this command in Tier 3 or 4? → Document justification before running

---

## 7. APT Tradecraft Patterns Worth Adopting

### From Volt Typhoon: Sequence Discipline
Their observed enumeration follows a logical progression:
**Identity → Context → Network → Domain → Targets**

Never jump ahead. Each phase informs the next. If you don't know the network layout,
don't start enumerating domain resources.

### From APT29: Patience
- Commands spaced minutes to hours apart, not seconds
- Each action has a clear purpose tied to the objective
- They sit on access before acting — "observe first, act later"

### From APT41: Persist First, Enumerate Later
- Establish a reliable way back before doing anything noisy
- If your shell dies mid-enumeration, you lose everything
- On real engagements: consider dropping a minimal persistence mechanism before broad enum

### From Scattered Spider: Know When You're Watched
- Search for evidence of monitoring before proceeding
- Check for EDR processes (`ps aux | grep -iE 'falcon|sentinel|defender|carbon|cylance|crowdstrike|splunk|ossec|wazuh'`)
- Check for auditd rules: `auditctl -l 2>/dev/null` (if accessible)
- Adapt behavior based on what's watching

### General: The /proc Filesystem Is Your Best Friend
Almost everything you need for initial enumeration lives in `/proc`:
- `/proc/self/status` — your uid, gid, groups, capabilities
- `/proc/version` — kernel version
- `/proc/sys/kernel/hostname` — hostname
- `/proc/net/tcp` — listening ports and connections
- `/proc/net/arp` — network neighbors
- `/proc/*/cmdline` — running processes
- `/proc/*/environ` — environment variables (credential goldmine)

Reading from `/proc` generates standard file-read syscalls. No `execve` events.
Most auditd configurations do not watch `/proc` reads.

---

## 8. Post-Access Noise Ratings (Updated)

The OPSEC_PROFILES.md rates most post-access commands as NONE. This is incorrect
for environments with EDR, auditd, or SIEM. Updated ratings:

| Technique | Noise (No EDR) | Noise (auditd) | Noise (EDR/SIEM) | Key Detection |
|-----------|----------------|-----------------|-------------------|---------------|
| `cat /proc/*` reads | NONE | NONE | NONE | Not monitored anywhere |
| `id` | NONE | LOW | LOW | Splunk `d1ff2e22` (informational) |
| `whoami` | NONE | LOW | MEDIUM | Splunk `d1ff2e22`, FortiSIEM `PH_RULE_TH_Linux_whoami` |
| `sudo -n -l` | NONE | LOW | LOW | auth.log entry but non-interactive |
| `sudo -l` (interactive) | NONE | MEDIUM | MEDIUM | auth.log + potential password prompt log |
| `echo pass \| sudo -S` | NONE | HIGH | HIGH | Password in EXECVE record, auditd + SIEM |
| `cat /etc/passwd` | NONE | LOW | MEDIUM | Splunk `0419cb7a` if auditd file watch |
| `cat /etc/shadow` | NONE | HIGH | HIGH | auditd file watch always fires |
| `getent passwd` | NONE | NONE | LOW | NSS lookup, not file access |
| `find / -perm -4000` | NONE | MEDIUM | HIGH | Elastic `5b06a27f`, Sigma, recursive I/O |
| `find /usr/bin -perm -4000` | NONE | LOW | LOW | Scoped, no detection rule matches |
| `getcap -r /` | NONE | LOW | MEDIUM | Sigma `fe10751f` |
| `getcap /usr/bin/python3` | NONE | NONE | NONE | Targeted, no rule |
| `ps aux` | NONE | NONE | LOW | Normal admin activity |
| `ls /proc/[0-9]*/cmdline` | NONE | NONE | NONE | File read |
| `ss -tlnp` | NONE | NONE | LOW | Normal admin activity |
| `cat /proc/net/tcp` | NONE | NONE | NONE | File read |
| `ssh-keygen` on target | NONE | LOW | MEDIUM | Elastic SSH key generation rule |
| Discovery burst (5+ cmds <60s) | NONE | MEDIUM | HIGH | SIEM correlation rules |
| `strings` on databases | NONE | NONE | LOW | Unusual but no specific rule |
| `hexdump` on files | NONE | NONE | LOW | Unusual process |
| `find / -writable` | NONE | MEDIUM | HIGH | Massive syscall volume, correlation |

**Key insight:** Individual commands are rarely the problem. It's the **burst pattern** —
5+ discovery commands within 60 seconds from the same session — that triggers SIEM correlation.
Adding jitter between commands is the single highest-impact change.
