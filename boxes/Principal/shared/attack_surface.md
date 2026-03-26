# Attack Surface — Principal
> Last updated: 2026-03-24T20:17Z
> Operation status: POST-ACCESS (user shell obtained, privesc next)

## Service Inventory
| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 22 | SSH | OpenSSH 9.6p1 Ubuntu 3ubuntu13.14 | HIGH | Foothold via svc-deploy |
| 8080 | HTTP | Jetty 12.x + pac4j-jwt/6.0.3 | HIGH | Java 21.0.10, H2 embedded DB |

## Current Access
- **User:** svc-deploy (uid=1001)
- **Groups:** svc-deploy(1002), deployers(1001)
- **Method:** CVE-2026-29000 → admin JWT → /api/settings cred leak → SSH
- **Shell:** stable SSH, full TTY
- **user.txt:** 87b0ca4fa422011ec548a1a36343cbb3

## Attack Paths
| Rank | Path | Confidence | Complexity | Status | Evidence |
|------|------|------------|------------|--------|----------|
| 1 | CVE-2026-29000 → admin JWT → cred harvest → SSH | HIGH | LOW | VALIDATED | Foothold achieved |
| 2 | SSH CA cert signing → root or other user pivot | HIGH | MEDIUM | UNEXPLORED | SSH CA config at /opt/principal/ssh/, svc-deploy issues SSH certs per dashboard activity |
| 3 | deployers group perms → writable files/dirs → privesc | MEDIUM | MEDIUM | UNEXPLORED | svc-deploy in deployers(1001) group |
| 4 | H2 embedded DB → additional credentials | MEDIUM | LOW | UNEXPLORED | H2 DB confirmed in /api/settings |
| 5 | Jetty process privilege → if running as root | LOW | LOW | UNEXPLORED | Unknown process owner |

## Exploit Research

### CVE-2026-29000 — VALIDATED
- PlainJWT MUST use 3-part format (header.payload. WITH trailing dot) per RFC 7519
- Role claim is singular string `role: "ROLE_ADMIN"` — NOT `$int_roles` array
- A256GCM works even though app config says A128GCM
- JWKS key IS the encryption key (kid: enc-key-1)

## Platform Intelligence (from admin panel)
**Users:** admin, svc-deploy, jthompson, amorales, bwright, kkumar, mwilson, lzhang
**Credential found:** `D3pl0y_$$H_Now42!` (from /api/settings encryptionKey field)
**SSH CA:** Keys rotated Dec 15, certs before Dec 1 revoked. CA config at /opt/principal/ssh/
**svc-deploy activity:** Issues SSH certificates, triggers deployments

## Privesc Leads (for NOIRE)
1. SSH CA at /opt/principal/ssh/ — if svc-deploy can sign certs, can forge cert for root
2. deployers group — check group-writable files, sudo rules, cron jobs
3. H2 embedded database — may contain additional credentials
4. Jetty process owner — if root, web app exploitation → root
5. /opt/principal/ — deployment infrastructure, config files, scripts

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-24T18:19Z | Full port scan | Fresh operation | 2 ports: SSH + HTTP |
| 2026-03-24T18:22Z | Skip web enum, direct CVE exploit | Pre-auth CVE with PoC | ELLIOT Session 1 failed (PoC bug) |
| 2026-03-24T19:23Z | Deep CVE research | Understand failure root cause | Found trailing dot issue |
| 2026-03-24T19:31Z | Redeploy ELLIOT with corrected format | Trailing dot fix identified | Foothold in 4 turns |
| 2026-03-24T20:17Z | Deploy NOIRE for privesc enum | Stable shell, multiple leads | Pending |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Analysis | pac4j-jwt 6.0.3 vuln, JWKS retrieved | ELLIOT deployed |
| 2 | Exploitation (ELLIOT S1) | All forms failed — Python PoC has trailing dot bug | Research pivot |
| 3 | Research + Exploitation (ELLIOT S2) | Trailing dot fix → admin JWT → cred harvest → SSH foothold | NOIRE deployment |
