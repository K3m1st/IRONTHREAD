# Scouting Report — Facts
> Target: 10.129.6.121 (facts.htb)
> Date: 2026-03-18
> Status: COMPLETE

## Service Inventory

| Port | Service | Version | Confidence |
|------|---------|---------|------------|
| 22 | SSH | OpenSSH 9.9p1 Ubuntu 3ubuntu3.2 | HIGH |
| 80 | HTTP | nginx 1.26.3 → CamaleonCMS (Rails) | HIGH |
| 54321 | HTTP | MinIO S3 API (version unknown) | HIGH (service) / MEDIUM (version) |

## Key Findings

### Port 80 — CamaleonCMS
- **CMS**: CamaleonCMS (Ruby on Rails) with `camaleon_first` theme
- **Cookie**: `_factsapp_session` (Rails session)
- **Admin panel**: `/admin/login` (username + password)
- **Registration**: `/admin/register` — **OPEN** (with CAPTCHA)
- **Contact**: contact@facts.htb
- **Images served from**: MinIO `randomfacts` bucket via nginx proxy

### Port 54321 — MinIO
- S3-compatible object storage API
- Redirects to port 9001 (console) — **not externally accessible**
- `randomfacts` bucket: publicly listable, contains only image files (18 images + thumbnails)
- Root listing: AccessDenied
- Health endpoints: responding normally
- Owner DisplayName: `minio` (default)

### Port 22 — SSH
- OpenSSH 9.9p1 — current, no known CVEs
- Auth: publickey

## Architecture Model

```
Internet → nginx:80 → CamaleonCMS (Rails app)
                    → /randomfacts/* proxied to MinIO:54321
         → MinIO:54321 (S3 API, direct access)
         → MinIO:9001 (console, localhost-only)
         → SSH:22
```

## Anomalies

1. MinIO console (9001) bound to localhost only — accessible post-foothold
2. Open registration on CamaleonCMS — unusual for production CMS
3. MinIO bucket publicly listable via S3 API but nginx blocks directory listing
