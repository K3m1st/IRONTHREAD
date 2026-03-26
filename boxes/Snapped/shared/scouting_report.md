# Scouting Report — Snapped (10.129.9.2)
**Generated:** 2026-03-25T17:37Z | **Agent:** ORACLE

## Target Summary
- **IP:** 10.129.9.2
- **Hostname:** snapped.htb
- **OS:** Ubuntu Linux (OpenSSH 9.6p1 Ubuntu 3ubuntu13.15)

## Services

| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 22/tcp | SSH | OpenSSH 9.6p1 | HIGH | ECDSA + ED25519 keys |
| 80/tcp | HTTP | nginx 1.24.0 | HIGH | Redirects to snapped.htb |

## Virtual Hosts Discovered

| Hostname | Response | Notes |
|----------|----------|-------|
| snapped.htb | 200, 20199 bytes | Static corporate landing page |
| admin.snapped.htb | 200, 1407 bytes | **Nginx UI** web management panel |

## Web Stack
- **snapped.htb:** Pure static HTML, no backend, no CMS
- **admin.snapped.htb:** Nginx UI (Go backend, Vue.js SPA), proxied from 127.0.0.1:9000

## Key Observations
1. Only 2 TCP ports — minimal surface, web-focused box
2. Nginx UI is the primary attack surface
3. No robots.txt, no additional directories on main domain
