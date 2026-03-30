# Attack Surface — Barrier
> Last updated: 2026-03-27T19:00Z
> Operation status: COMPLETE — ROOTED

## Service Inventory
| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 22 | SSH | OpenSSH 8.9p1 Ubuntu 3ubuntu0.13 | HIGH | RSA host key only, Ubuntu 22.04 Jammy |
| 80 | HTTP | nginx | HIGH | Redirects → https://gitlab.barrier.vl:443/ |
| 443 | HTTPS | GitLab CE 17.3.2 (rev 951fd632abf) | HIGH | SAML auth via authentik, public registration open, user satoru has SAML identity |
| 8080 | HTTP | Apache Guacamole (on Tomcat 9.0.58) | HIGH | Guacamole at /guacamole/, SAML via authentik, MySQL backend guac_user:guac2024 |
| 9000 | HTTP | authentik 2024.10.5 | HIGH | SAML IdP for GitLab, enterprise license, can_impersonate capability |
| 9443 | HTTPS | authentik 2024.10.5 | HIGH | SSL variant of 9000, wildcard cert |

## Credentials
| Username | Secret | Service | Source | Verified |
|----------|--------|---------|--------|----------|
| satoru | dGJ2V72SUEMsM3Ca | GitLab OAuth | Commit history a8e43e54 | YES (OAuth token obtained) |
| satoru | dGJ2V72SUEMsM3Ca | SSH | — | NO (denied) |
| akadmin | (session cookie — regenerable via SAML bypass) | GitLab admin | CVE-2024-45409 forged SAML | YES (is_admin=true confirmed) |
| akadmin | MqL8GPTr7y4EDMWsp7gxb2YiKEzuNpLZ2QVia8HD4MLc93vgublgL5xQEvTc | authentik superadmin API | CI/CD runner env var leak | YES |
| operator | Operator123! | authentik superadmin | Created via API | YES |
| guac_user | guac2024 | MySQL (guac_db) | guacamole.properties | YES |
| maki_adm | SSH key + passphrase 3V32FN6oViMPxyzC | SSH (host) | Guacamole MySQL connection params | YES |
| maki_adm | Va4kSjgTHSd55ZLv | sudo → root | .bash_history | YES |

## Attack Paths
| Rank | Path | Confidence | Complexity | Status | Evidence |
|------|------|------------|------------|--------|----------|
| 1 | ★ CVE-2024-45409: Ruby-SAML auth bypass → GitLab admin | HIGH | Standard | VALIDATED | Exploited — akadmin session obtained via forged SAML assertion |
| 2 | ★ GitLab admin → unpause CI/CD runner → env leak → authentik admin | HIGH | Trivial | VALIDATED | AUTHENTIK_TOKEN leaked in runner env vars |
| 3 | ★ authentik admin → Guacamole → maki_adm SSH → host shell | HIGH | Standard | VALIDATED | SSH key+passphrase from Guacamole MySQL |
| 4 | ★ maki_adm .bash_history → sudo password → root | HIGH | Trivial | VALIDATED | Password in plaintext in history file |
| 5 | CVE-2025-24813: Tomcat PUT RCE | LOW | Complex | NOT NEEDED | Fallback — never required |

## Exploit Research

### CVE-2024-45409 — Ruby-SAML / GitLab SAML Authentication Bypass

**CVE:** CVE-2024-45409
**CVSS:** 9.8 (Critical)
**Affected:** ruby-saml ≤1.12.2 and 1.13.0–1.16.0 → GitLab CE/EE < 17.3.3, 17.2.7, 17.1.8
**Target version:** GitLab CE 17.3.2 → **VULNERABLE**
**PoC:** https://github.com/synacktiv/CVE-2024-45409
**Research sources:** ProjectDiscovery blog, Synacktiv, BleepingComputer, GitLab advisory

### Vulnerability Primitive
- **Primitive:** XPath selector for DigestValue in SAML signature verification selects first matching element regardless of position. Attacker controls XML structure of SAML response.
- **Delivery forms:** Inject forged `<ds:DigestValue>` inside `<samlp:Extensions>` before the signed assertion. The forged digest is selected first by XPath, bypassing signature verification on the real assertion.
- **Defenses observed:** None — the vulnerability is in the ruby-saml library's core signature verification logic.
- **Untested forms:** N/A — single well-documented exploit path.
- **Prerequisites:** (1) SAML authentication must be configured ✅ (confirmed). (2) Need a legitimately signed SAML response from the IdP — obtainable by authenticating as satoru through authentik. (3) Know the extern_uid of the target user — admin is likely `root` or user ID 1.

### Attack Chain (EXECUTED)
1. ✅ satoru creds from GitLab commit history (a8e43e54) → GitLab OAuth access
2. ✅ Authenticated as satoru via authentik SAML flow → captured signed SAML response (operator assisted via Burp)
3. ✅ synacktiv CVE-2024-45409 PoC forged assertion with NameID=akadmin → submitted to GitLab callback
4. ✅ Authenticated as akadmin (ID 1, is_admin=true, email=admin@barrier.vl)
5. ✅ Unpaused runner → pipeline env dump → AUTHENTIK_TOKEN leaked
6. ✅ authentik superadmin → discovered Guacamole → created operator account
7. ✅ Guacamole MySQL → maki_adm SSH key + passphrase → SSH to host
8. ✅ .bash_history → sudo password → root

### CVE-2025-24813 — Apache Tomcat Partial PUT RCE
- **Affected range:** 9.0.0–9.0.98 (target is 9.0.58)
- **Prerequisites (ALL required, none default):** readonly=false, file-based session persistence, vulnerable deserialization library on classpath
- **Assessment:** LOW confidence — unlikely all three non-default conditions are met on a standard Tomcat install. Keep as fallback.

## Anomalies
- SSH only offers ssh-rsa host key algorithm (unusual for modern Ubuntu 22.04)
- authentik has `is_enterprise` and `can_impersonate` capabilities — if we get authentik admin, we can impersonate any SAML user

## Flags
| Flag | Hash |
|------|------|
| user.txt | `0f811384aa0148c7f1fe68ff77af0054` |
| root.txt | `3ea64e4e730c763d192d9e88ff8466e9` |

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-27T02:06Z | Start full scan | Standard Phase 1 | 6 services identified |
| 2026-03-27T02:10Z | Check GitLab commit history | Public repo with OAuth script — likely credential leak | Password recovered and verified |
| 2026-03-27T02:13Z | Prioritize CVE-2024-45409 | GitLab 17.3.2 + SAML + signed response available = textbook fit | HIGH confidence attack path |
| 2026-03-27T17:00Z | Capture SAML response via Burp | Automated capture (Playwright/requests) failed on consent flow | Operator captured via Burp, decoded XML manually |
| 2026-03-27T17:17Z | Forge SAML for akadmin | Admin user is akadmin (ID 1), not root — discovered via user enum | CVE-2024-45409 exploit successful, admin session obtained |
| 2026-03-27T17:37Z | Next: unpause runner for RCE | Shared runner (ID 1) is paused, akadmin can unpause | Runner unpaused, pipeline executed |
| 2026-03-27T17:43Z | CI/CD env dump instead of reverse shell | Operator suggestion — simpler, read output from job log | AUTHENTIK_TOKEN discovered in env |
| 2026-03-27T18:13Z | Use authentik admin to access Guacamole | Guacamole discovered as SAML app, Tomcat:8080 = Guacamole | Operator created admin account, accessed Guacamole |
| 2026-03-27T18:30Z | Extract creds from Guacamole MySQL | Connection params stored in guac_db | maki_adm SSH key + passphrase recovered |
| 2026-03-27T18:43Z | SSH + privesc | .bash_history leaked sudo password | Root achieved, both flags captured |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Exploitation → Root | Full chain: git creds → SAML bypass → CI/CD env leak → Guacamole → SSH → root | COMPLETE |
