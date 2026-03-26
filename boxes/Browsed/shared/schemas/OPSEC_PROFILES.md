# IRONTHREAD Opsec Profiles & Noise Ratings
> Reference for all agents. Oracle selects the profile at operation start.

---

## Opsec Profiles

### LOUD (Pentest Mode)
Goal: Coverage and speed. Detection is acceptable.

| Parameter | Value |
|-----------|-------|
| Port scan rate | 50-100 probes/sec (nmap -T4) |
| Web request rate | 10-30 req/sec |
| Login attempt rate | 1 attempt/sec per host |
| Jitter | 0-10% |
| Phase timing | Immediate progression |
| Nmap flags | `-sS -T4 --min-rate 100` |
| Web tools | Default gobuster/ffuf settings |
| Password spray | Unrestricted (lockout is acceptable) |

### MODERATE (Red Team — Avoid Automation)
Goal: Avoid triggering automated IDS/WAF alerts. Manual SOC review is acceptable risk.

| Parameter | Value |
|-----------|-------|
| Port scan rate | 1 probe every 3-5 sec (`--max-rate 20`) |
| Web request rate | 1-2 req/sec with 20-40% jitter |
| Login attempt rate | 1 per 3 min per source IP |
| Jitter | 20-40% random variation |
| Phase timing | 15-30 min between phases |
| Nmap flags | `-sS -T2 --max-rate 20 --randomize-hosts --data-length 24` |
| Web tools | Custom UA, `-t 1 --delay 2s` (gobuster), `-t 1 -rate 1 -p "1-3"` (ffuf) |
| Password spray | 1 password per 35 min across all users |
| Kerberoast | Max 3 TGS requests per 5 min |

### GHOST (Maximum Stealth)
Goal: Zero automated detection. Accept operations take days/weeks.

| Parameter | Value |
|-----------|-------|
| Port scan rate | 1 probe every 30-60 sec; top 20 ports only |
| Web request rate | 0.1-0.3 req/sec (1 every 3-10 sec) |
| Login attempt rate | 1 per 10 min per source IP |
| Jitter | 40-80% random (Gaussian) |
| Phase timing | Hours to days between phases |
| Nmap flags | `-sS -T1 --max-rate 1 --randomize-hosts --data-length 32 --source-port 53` |
| Web tools | Custom script with real browser UA, TLS fingerprint matching, referrer spoofing |
| Password spray | 1 password per 4+ hours; max 10-20 high-value accounts |
| DNS | Passive only (crt.sh, SecurityTrails) |
| Additional | LOTL exclusively; no external tooling until certain |

---

## Detection Threshold Cheat Sheet

| System | Threshold | Safe Rate (under threshold) |
|--------|-----------|---------------------------|
| Suricata portscan (default) | 25 ports/60s from one source | <20 ports/min (1 per 3s) |
| Suricata network sweep | 5 hosts/60s on same port | <4 hosts/min |
| ET SCAN SSH rule (SID 2001219) | 5 connections/120s | 1 per 30s |
| ET SCAN Nmap SYN (SID 2009582) | Window size 1024 match | Use `--data-length 24` |
| ET SCAN Nmap NSE UA (SID 2024897) | Single request match | Custom User-Agent always |
| ModSecurity CRS DOS (912100) | 100 requests/60s | <80 req/min (1.3/sec) |
| ModSecurity CRS scanner (913100) | Known UA match (single req) | Custom UA always |
| ModSecurity CRS PL2 | 20-30 error req/min | <15 req/min |
| Cloudflare bot detection | JA3/JA4 fingerprint | Browser-impersonation or proxy |
| AWS WAF rate-based | 2000 req/5min (~6.6/sec) | <5 req/sec |
| fail2ban SSH | 5 failures/600s | 1 per 2.5 min |
| OpenSSH MaxAuthTries | 6 per connection | 1 attempt per connection |
| AD lockout (typical) | 5 failures/30 min | 1 password per 35 min cycle |
| SIEM brute force (4625) | 5 failures/5 min | 1 per 2 min |
| Kerberoast detection | 10 SPNs/5 min | 2-3 per 5 min |
| DNS AXFR (SID 2027869) | Single packet match | No quiet alternative |
| DNS brute flood (SID 2016016) | 50 queries/10s | <5 queries/sec |

---

## Tool Noise Ratings

### Rating Scale
| Rating | Meaning | When Authorized |
|--------|---------|-----------------|
| LOW | Minimal signatures; blends with normal traffic | Any profile |
| MEDIUM | Detectable by tuned IDS/WAF; avoids defaults | MODERATE+ profile |
| HIGH | Triggers default IDS/WAF rules | LOUD profile or explicit escalation |
| CRITICAL | Instant detection; dedicated signatures exist | LOUD only; explicit operator override |

### Reconnaissance Tools (sova-mcp)

| Tool | Default Rating | Tuned Rating | Key Detection Vector | Quiet Config |
|------|---------------|-------------|---------------------|-------------|
| nmap -sS -T4 | HIGH | — | 300+ pps, exceeds all thresholds | — |
| nmap -sS -T2 | MEDIUM | LOW | ~2.5 pps, under most defaults | `--max-rate 3 --data-length 24` |
| nmap -sS -T1 | LOW | — | ~0.07 pps, designed for evasion | Already quiet |
| nmap -sV (default) | HIGH | MEDIUM | Service probe sigs (SID 2024364) | `--version-intensity 0` |
| nmap -sC (scripts) | HIGH | MEDIUM | NSE UA (SID 2024897), SMB enum | Cherry-pick scripts + custom UA |
| nmap -p- (full port) | HIGH | — | 65K packets always trips portscan | `--top-ports 100` instead |
| whatweb -a 1 | LOW | — | 1 request; change UA to be invisible | Custom UA |
| whatweb -a 3 | MEDIUM | LOW | 5-15 requests, path probing | Custom UA + `--wait 2` |
| whatweb -a 4 | HIGH | — | 100+ requests, scanner pattern | Not salvageable |
| smbclient (null session) | MEDIUM | — | Event ID 4624 Anonymous Logon | Inherent; single attempt = low priority |
| dig AXFR | CRITICAL | — | Single-packet signature (SID 2027869) | Use passive DNS instead |
| FTP anon login (single) | LOW | — | SID 2002383 fires but single event | One attempt only |
| Passive DNS (crt.sh) | NONE | — | Zero target-side traffic | Already passive |

### Web Enumeration Tools (webdig-mcp)

| Tool | Default Rating | Tuned Rating | Key Detection Vector | Quiet Config |
|------|---------------|-------------|---------------------|-------------|
| gobuster (default) | HIGH | MEDIUM | UA, Go TLS JA3, 404 flood | Custom UA, `-t 1 --delay 2s` |
| ffuf (default) | CRITICAL | MEDIUM | UA, Go TLS JA3, 40 threads | Custom UA, `-t 1 -rate 1 -p "1-3"` |
| curl (manual) | LOW | — | curl UA (fix with -H) | Custom UA + browser headers |
| nikto | CRITICAL | HIGH (floor) | Test patterns ARE the signature | Not salvageable for stealth |

### Exploitation Tools

| Tool | Default Rating | Tuned Rating | Key Detection Vector | Quiet Config |
|------|---------------|-------------|---------------------|-------------|
| sqlmap (default) | CRITICAL | HIGH (floor) | SQL payloads are the signature | `--random-agent --delay 3 --technique B` |
| hydra (default) | HIGH | MEDIUM | libssh banner, lockout triggers | Spray pattern, 1 per 35min cycle |
| Metasploit (default) | CRITICAL | HIGH | Meterpreter TLV, port 4444, EDR behavioral | Stageless HTTPS, port 443, shikata_ga_nai |
| enum4linux | CRITICAL | — | RID cycling, dozens of RPC calls | No quiet mode; use smbclient instead |
| crackmapexec (full) | HIGH | MEDIUM | SAMR enum, SMB fingerprint | `--no-bruteforce`, single target |

### Post-Access / LOTL

| Technique | Rating | Notes |
|-----------|--------|-------|
| Built-in OS commands (id, whoami, cat) | NONE | Normal system operation |
| sudo -l | NONE | Standard user action |
| find -perm -4000 | LOW | Logged in audit but common |
| ps aux / ss -tlnp | NONE | Normal admin activity |
| cat /etc/shadow (as root) | LOW | Logged in audit |
| SSH key planting | LOW | Single file write |
| Reverse shell (bash -i) | MEDIUM | Outbound connection anomaly |
| Process injection | HIGH | EDR behavioral detection |

---

## Key Suricata SIDs Reference

| SID | Rule | Triggered By |
|-----|------|-------------|
| 2009582 | Nmap SYN scan | TCP window size 1024 |
| 2024364 | Nmap service detection | NULL/Generic probes |
| 2024897 | Nmap Scripting Engine UA | "Nmap Scripting Engine" in UA |
| 2027869 | DNS AXFR zone transfer | Single AXFR query |
| 2002383 | FTP anonymous login | "USER anonymous" in FTP stream |
| 2019284 | FTP brute force | 5+ attempts/120s |
| 2016016 | DNS query flood | 50+ queries/10s |
| 2024220 | SMB NT Create request | SMB enumeration activity |
| 2103088 | SMB cleartext login | Plaintext NTLM auth |
| 2001219 | Potential SSH scan | 5 SSH connections/120s |
| 2002677 | Nikto scanner | "Nikto" in UA |
| 2016936 | sqlmap scanner | "sqlmap" in UA |
| 2014530 | Meterpreter reverse TCP | Meterpreter TLV pattern |
| 2024799 | Meterpreter default port | Outbound to port 4444 |

---

## TLS Fingerprinting (Cross-Cutting)

Go-based tools (gobuster, ffuf) and Python-based tools (sqlmap) have distinctive JA3/JA4 TLS fingerprints that differ from browsers. Cloudflare, Akamai, and advanced WAFs detect these regardless of User-Agent.

**Mitigation by profile:**
- LOUD: Don't care
- MODERATE: Custom UA is sufficient for most targets
- GHOST: Use `curl-impersonate` or proxy through a real browser instance
