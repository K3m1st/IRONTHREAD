# Pterodactyl -- Internal Debrief
> For: Operator + AI Crew
> Box: Pterodactyl | Completed: 2026-03-19 | Sessions: 4 ELLIOT + 1 Oracle | Elliot turns: ~21/80 (across 4 sessions)

## Operation Timeline

| Session | Phase | Duration | What Happened |
|---------|-------|----------|---------------|
| Oracle 1 | Recon + Analysis | ~20min | Full scan, vhost discovery, phpinfo/changelog intelligence, CVE-2025-49132 identified, handoff written |
| ELLIOT 1 | Foothold | 5/15 turns | LFI validated, creds extracted, pearcmd RCE, reverse shell, user flag |
| Oracle (cont) | Post-Access Investigation | ~90min | Webshell-based enum (narrow output channel), DB creds, Wings config, hash cracking, SSH as phileasfogg3, discovered targetpw, panel admin access |
| ELLIOT 2 | Privesc attempt 1 | 5/20 turns | CVE-2025-32463 sudo chroot -- FAILED (no gcc, as+ld .so not loadable by dlopen) |
| Oracle (cont) | Research + retool | ~30min | Found precompiled .so, discovered CVE-2025-6018/6019, verified udisks2/libblockdev installed |
| ELLIOT 3 | Privesc attempt 2 | 12/25 turns | CVE-2025-32463 with precompiled .so -- DEAD (SUSE backport). Pivoted to CVE-2025-6018+6019. PAM bypass worked, udisks2 race won, but SUID "not working" (misdiagnosis) |
| Oracle (cont) | Retool | ~15min | Built ext4 image with proper SUID on attack box. Identified xfs_db approach might have CRC issues. |
| ELLIOT 4 | Privesc -- ROOT | 4/20 turns | Identified foreground/background bug from Session 3. XFS image from Session 3 was valid all along. Ran catcher in foreground. Root flag captured. |

## What Worked Well

**Recon was surgical.** Oracle identified all three vhosts, found phpinfo.php and changelog.txt, confirmed every CVE prerequisite, and delivered a complete brief -- all before asking the operator to confirm. The phpinfo intelligence (register_argc_argv, PEAR path, empty disable_functions) was the key that made the exploit path certain rather than speculative.

**ELLIOT Session 1 was flawless.** 5 turns, clean exploitation, user flag, credential extraction, new surface discovery. The hex-encoding technique for pearcmd payloads handled all special characters cleanly. This is the model for future ELLIOT deployments.

**Handoff quality was high.** The vulnerability primitive documentation (what the attacker controls, all delivery forms, defenses observed, untested forms) gave ELLIOT enough context to execute without back-and-forth. The pearcmd handoff was textbook.

**The CVE-2025-6018 PAM bypass was instant.** Two lines in `~/.pam_environment`, re-login, done. This should be in our standard SUSE privesc playbook.

## What We Got Wrong (And What It Cost)

### 1. Spent ~90 minutes on post-access investigation through a narrow webshell output channel
**What happened:** Oracle tried to run noire-style enumeration through the PEAR config webshell, which only returns one line of output embedded in serialized PHP data. Multiple find commands hung and killed PHP-FPM.
**Root cause:** No MCP tools available in session (sova/webdig/noire servers didn't load). Fell back to manual webshell, which was too constrained for multi-line output.
**Cost:** ~90 minutes of painful one-command-at-a-time enumeration. One `find /` command took down the web server entirely.
**Fix:** Establish a proper reverse shell or SSH session BEFORE running post-access investigation. The webshell should be a stepping stone, not the investigation platform. Also: fix MCP tool loading.

### 2. Didn't check sudo version until after exhausting password-cracking approaches
**What happened:** After finding `sudo (ALL) ALL` with `targetpw`, Oracle spent time cracking bcrypt hashes, exploring the panel admin, resetting DB passwords, checking Redis, and investigating Wings -- before checking `sudo --version` against CVEs.
**Root cause:** Standard privesc methodology checks `sudo -l` but not `sudo --version`. The unusual `targetpw` config was treated as "need to find a password" rather than "signal to look for sudo vulnerabilities."
**Cost:** ~60 minutes of hash cracking and panel exploration that produced no viable privesc path.
**Fix:** Add `sudo --version` to standard noire checklist immediately after `sudo -l`. When sudo config is unusual, research CVEs for the specific version before pursuing credential attacks.

### 3. Relied on web search that surfaced writeup hints
**What happened:** When stuck on privesc, a web search for sudo targetpw bypass returned writeup links for this exact box, revealing that the intended path involved PAM + udisks2/libblockdev.
**Root cause:** Web search queries weren't scoped to exclude HTB writeup sites.
**Cost:** Partial integrity of the solve. The foothold was clean; the privesc direction came from external hints.
**Fix for Pro Labs:** Operator plans to add guardrails. Oracle should scope CVE searches to NVD, vendor advisories, and security research blogs -- not generic searches that may return writeups. Use `blocked_domains` parameter on WebSearch.

### 4. CVE-2025-32463 red herring consumed an entire ELLIOT session
**What happened:** ELLIOT spent 5 turns fighting the sudo chroot exploit with hand-assembled .so files, then Oracle found a precompiled .so, and ELLIOT spent 2 more turns before discovering the SUSE backport.
**Root cause:** Didn't check `rpm -q sudo --changelog` to verify whether SUSE had backported the patch. Version number alone (1.9.15p5) suggested vulnerability, but SUSE patched it in their package build.
**Cost:** 7 ELLIOT turns + Oracle research time wasted on a patched vulnerability.
**Fix:** On RPM-based systems, always run `rpm -q --changelog <package> | grep CVE` before attempting exploitation. This is a 5-second check that would have saved an entire session.

### 5. Foreground/background process management bug cost an entire session
**What happened:** In ELLIOT Session 3, the CVE-2025-6019 exploit mechanism worked perfectly (mount without nosuid, race won, SUID binary found) but the catcher was backgrounded. `os.execv(bash -p)` replaced the background Python process with a root bash that nobody could interact with. `id` in the foreground shell showed uid=1002.
**Root cause:** The PoC reference material wasn't carefully analyzed for process management details. The MichaelVenturella PoC runs the catcher in the foreground and the trigger in the background.
**Cost:** 10 ELLIOT turns debugging a "SUID not working" issue that was actually a process management bug. Plus Oracle time building an ext4 image as an alternative (unnecessary).
**Fix:** For race condition exploits, always analyze which component needs the foreground (the one that executes the payload) vs background (the trigger). Document this in the handoff explicitly.

## Technical Lessons Learned

### PEAR pearcmd.php Exploitation
- Hex-encoding commands via `system(hex2bin('...'))` is the reliable payload format -- avoids all URL encoding issues
- PEAR `config-create` writes to arbitrary paths, but the output is embedded in serialized PHP config data -- not suitable as an investigation shell
- The webshell output channel is: `sed -n 's/.*pearcmd&\/\(.*\)/\1/p' | head -1 | sed 's|/pear/php.*||'` -- single line only

### SUSE-specific Behaviors
- SUSE backports security patches into stable package versions. `sudo-1.9.15p5-150600.3.9.1` has CVE-2025-32463 patched despite upstream 1.9.15p5 being vulnerable
- `rpm -q --changelog` is the authoritative source for what's patched
- SUSE's PAM config has `user_readenv=1` by default -- `~/.pam_environment` is processed on every login
- PHP-FPM runs as `wwwrun:www` (not `www-data` like Debian)

### CVE-2025-6019 Race Condition Details
- `xfs_db` metadata modifications (uid, gid, mode on inodes) ARE valid and kernel-honored. CRCs are updated correctly.
- ext4 `Filesystem.Check` and `Filesystem.Resize` do NOT trigger temporary mounts in libblockdev -- they use `e2fsck`/`resize2fs` which don't mount
- Only XFS operations trigger the vulnerable temporary mount path
- The temporary mount appears at `/tmp/blockdev.XXXXXX` with mount options lacking `nosuid`
- Race window is generous -- the Python catcher with 1ms polling wins every time

### targetpw Sudoers Behavior
- `Defaults targetpw` makes sudo require the target user's password, not the invoking user's
- `(ALL) ALL` with `targetpw` means you can sudo as any user IF you know their password
- `sudo -u phileasfogg3 command` with your own password just runs as yourself -- no escalation
- This config is a deliberate CTF signal: "password cracking won't work, find a different vector"

## Methodology Wins

**Handoff system proved its value.** The structured handoff with vulnerability primitive, delivery forms, defenses, and untested forms gave ELLIOT clear fallback paths. When CVE-2025-32463 failed, the backup path (CVE-2025-6018+6019) was already documented.

**Turn budgets prevented runaway sessions.** ELLIOT Session 1 finished in 5/15 turns. Session 2 stopped at 5/20 when blocked. The budget system forced clean returns to Oracle for re-evaluation rather than thrashing.

**Credential harvest as standard procedure.** Extracting DB credentials, APP_KEY, Wings tokens, and user hashes as part of post-access created multiple attack vectors. The phileasfogg3 hash crack was the key that unlocked SSH access and eventually the privesc chain.

## IRONTHREAD Iteration Notes

### 1. MCP Tool Loading (Critical)
MCP servers (sova, webdig, noire) didn't load in this session. Oracle fell back to manual tool execution via Bash, which was significantly slower and more error-prone. The noire investigation should have taken 5 minutes with MCP tools; it took 90 minutes with webshell hacks.
**Action:** Debug MCP server initialization. Check if the servers start correctly when Claude Code launches from the oracle/ directory.

### 2. Add `sudo --version` + RPM Changelog to Noire Checklist
**File:** `ORACLE_SYSTEM_PROMPT.md`, Post-Access Investigation Framework section
**Change:** Add to Investigation Areas:
```
10. **Binary version auditing** -- `sudo --version`, `pkexec --version`, kernel version.
    On RPM systems: `rpm -q --changelog <pkg> | grep CVE` to verify patch status.
    Version numbers alone are unreliable on distros that backport patches.
```

### 3. Add WebSearch Domain Blocking for Active Box Operations
**File:** `ORACLE_SYSTEM_PROMPT.md`, Web Search Protocol section
**Change:** Add rule:
```
**During active operations on CTF/HTB boxes**, always use `blocked_domains` to exclude
writeup sites: writeups.htb, 0xdf.gitlab.io, medium.com, dollarboysushil.com,
hackthebox.eu (X/Twitter), thecybersecguru.com, havocsec.me, 1337sheets.com,
ibrahimisiaqbolaji.com, 4xura.com, and any domain containing "writeup" or "walkthrough".
Only reference NVD, vendor advisories, exploit-db, GitHub security advisories, and
security research blogs for CVE intelligence.
```

### 4. Handoff Should Document Process Management for Race Conditions
**File:** Schema or system prompt for handoff
**Change:** When the exploit involves race conditions, the handoff should explicitly specify which process runs in foreground vs background and why. Add an optional `process_model` field to the handoff schema.

### 5. Post-Access Investigation Should Not Use Webshells
**File:** `ORACLE_SYSTEM_PROMPT.md`
**Change:** Add rule: "If the foothold is a webshell or constrained RCE, the FIRST post-access action is to upgrade to a proper interactive shell (reverse shell, SSH key, credential reuse). Do not attempt multi-command enumeration through a webshell."

## What We'd Do Differently Next Time

1. **Establish SSH or stable reverse shell BEFORE post-access investigation** -- not fight with a one-line-at-a-time webshell
2. **Check `sudo --version` and `rpm -q --changelog sudo` immediately after `sudo -l`** -- this one check would have saved 60+ minutes
3. **On RPM systems, never trust upstream version numbers** -- always verify patch status via changelog
4. **Block writeup domains in web searches during active operations** -- preserve solve integrity
5. **For race condition exploits, study the reference PoC's process model** (foreground vs background) before writing the handoff
6. **When ELLIOT reports "mechanism works but payload doesn't fire," question the observation setup** -- was the payload checked in the right process context?

## Stats

| Metric | Value |
|--------|-------|
| Total ELLIOT turns | ~21 across 4 sessions |
| ELLIOT turn budget allocated | 80 (15+20+25+20) |
| ELLIOT efficiency | 26% of budget used |
| CVEs researched | 4 (CVE-2025-49132, CVE-2025-32463, CVE-2025-6018, CVE-2025-6019) |
| CVEs exploited successfully | 3 (49132, 6018, 6019) |
| CVEs that were dead ends | 1 (32463 -- SUSE backport) |
| Time recon to foothold | ~25 minutes |
| Time foothold to user flag | ~5 minutes (5 ELLIOT turns) |
| Time user flag to root flag | ~5 hours (multiple sessions, debugging) |
| Credentials harvested | 7 (DB, APP_KEY, salt, Wings token, 2 panel hashes, 1 cracked SSH) |
| Operator confirmation gates | 3 (exploitation, privesc session 2, privesc session 3) |

## CVE Reference Card

| CVE | Product | Primitive | How We Used It |
|-----|---------|-----------|----------------|
| CVE-2025-49132 | Pterodactyl Panel <= 1.11.10 | Unsanitized file path to PHP include() | LFI on /locales/locale.json -> pearcmd.php config-create -> webshell -> reverse shell as wwwrun |
| CVE-2025-32463 | sudo 1.9.14-1.9.17 | NSS library loading from chroot before auth | DEAD END -- SUSE backported patch. Spent 7 turns before discovering via rpm changelog |
| CVE-2025-6018 | PAM on openSUSE Leap 15 | ~/.pam_environment injection -> Active=yes session | Wrote XDG_SEAT/XDG_VTNR to .pam_environment, re-logged, gained allow_active polkit |
| CVE-2025-6019 | libblockdev (via udisks2) | Filesystem.Resize temp mount without nosuid | XFS image with SUID root bash -> udisksctl loop-setup -> gdbus Resize -> race catch -> euid=0 root shell |

## Flags

- **User**: `17b264159068601f09dfbca0685c60ad`
- **Root**: `23a028f57158b735838c675007307f8d`
