# Scouting Report — Principal
> Target: 10.129.244.220 | Date: 2026-03-24 | Status: COMPLETE

## Target Profile
- **IP:** 10.129.244.220
- **OS:** Ubuntu Linux (HIGH confidence)
- **Ports:** 2 open (22, 8080)

## Service Inventory
| Port | Service | Version | Confidence |
|------|---------|---------|------------|
| 22 | SSH | OpenSSH 9.6p1 Ubuntu 3ubuntu13.14 | HIGH |
| 8080 | HTTP | Jetty + pac4j-jwt/6.0.3 | HIGH |

## Web Service (8080)
- **Stack:** Java/Jetty, pac4j-jwt 6.0.3 for JWT authentication
- **Title:** Principal Internal Platform - Login
- **Auth:** JWE-encrypted JWT tokens (RSA-OAEP-256 + A128GCM, inner RS256)
- **JWKS:** Public RSA key at /api/auth/jwks (kid: enc-key-1)
- **API endpoints identified:** /api/auth/login, /api/auth/jwks, /api/dashboard, /api/users, /api/settings
- **Roles:** ROLE_ADMIN, ROLE_MANAGER, ROLE_USER
- **Platform features:** Deployment management, SSH certificate auth, access control, Prometheus monitoring

## Recommendations
1. **[CRITICAL] Exploit CVE-2026-29000** — pac4j-jwt auth bypass. Forge admin JWT using public key. Pre-auth, no creds needed.
2. After admin access, enumerate /api/users and /api/settings for SSH credentials or keys.
