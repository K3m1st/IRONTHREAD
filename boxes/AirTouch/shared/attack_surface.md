# Attack Surface — AirTouch
> Last updated: 2026-03-24T16:48Z
> Operation status: ANALYSIS — foothold on consultant container, wireless recon complete

## Service Inventory

| Port | Protocol | Service | Version | Confidence | Notes |
|------|----------|---------|---------|------------|-------|
| 22 | TCP | SSH | OpenSSH 8.2p1 Ubuntu 4ubuntu0.11 | HIGH | Only TCP port open. Entry point via SNMP creds. |
| 161 | UDP | SNMP | v2c, community: public | HIGH | Leaked default consultant password in sysDescr |

## Environment

- **Target IP**: 10.129.244.98
- **Hostname**: AirTouch-Consultant
- **OS**: Ubuntu 20.04.6 LTS (kernel 5.4.0-216-generic) — Docker container
- **Container IP**: 172.20.1.2/24 (gateway 172.20.1.1)
- **Access**: consultant:RxBlZhLmOkacNWScmZ6D — sudo NOPASSWD ALL
- **Wireless interfaces**: wlan0-wlan6 (7 interfaces, all initially DOWN)

## Network Architecture (from diagrams)

Three VLANs:
1. **Consultant VLAN** (172.20.1.0/24) — wired, Docker container, where we are
2. **Tablets VLAN** — wireless AP "AirTouch-Internet" (WPA2-PSK) — tablets
3. **Corp VLAN** — wireless AP "AirTouch-Office" (WPA2-Enterprise/802.1X) — corporate computers

## Wireless Networks Discovered

| SSID | BSSID | Channel | Freq | Security | Target? |
|------|-------|---------|------|----------|---------|
| vodafoneFB6N | b6:d3:d3:83:04:82 | 1 | 2.4GHz | WPA2-PSK (TKIP) | No — neighbor |
| MOVISTAR_FG68 | 5e:62:3e:e7:04:80 | 3 | 2.4GHz | WPA2-PSK (CCMP+TKIP) | No — neighbor |
| **AirTouch-Internet** | f0:9f:c2:a3:f1:a7 | 6 | 2.4GHz | **WPA2-PSK (CCMP+TKIP)** | **YES — Tablets VLAN** |
| WIFI-JOHN | ee:ac:6b:96:c7:1e | 6 | 2.4GHz | WPA2-PSK (CCMP+TKIP) | No — neighbor |
| MiFibra-24-D4VY | c6:b0:6f:88:43:07 | 9 | 2.4GHz | WPA2-PSK (CCMP) | No — neighbor |
| **AirTouch-Office** | ac:8b:a9:f3:a1:13 | 44 | 5GHz | **WPA2-Enterprise (802.1X, CCMP)** | **YES — Corp VLAN** |
| **AirTouch-Office** | ac:8b:a9:aa:3f:d2 | 44 | 5GHz | **WPA2-Enterprise (802.1X, CCMP)** | **YES — Corp VLAN (2nd AP)** |

## Attack Paths

### Path 1 — AirTouch-Internet WPA2-PSK Crack (Tablets VLAN)
- **Confidence**: HIGH | **Complexity**: LOW-MEDIUM
- **Evidence**: WPA2-PSK on channel 6, standard crackable auth
- **Method**: Monitor mode on wlan interface → airodump-ng on ch6 targeting BSSID f0:9f:c2:a3:f1:a7 → deauth client with aireplay-ng → capture 4-way handshake → crack with aircrack-ng + dictionary
- **Status**: UNEXPLORED
- **Prerequisite**: Active client(s) associated with the AP for deauth attack
- **Yield**: Access to Tablets VLAN — may contain user flag or creds for next stage

### Path 2 — AirTouch-Office WPA2-Enterprise (Corp VLAN)
- **Confidence**: MEDIUM | **Complexity**: HIGH
- **Evidence**: 802.1X authentication, CCMP only, two APs
- **Method**: Requires valid enterprise credentials or certificate. Cannot crack PSK. Options include: evil twin attack to capture RADIUS creds, or obtain creds from Tablets VLAN after Path 1.
- **Status**: UNEXPLORED — blocked until credentials obtained
- **Yield**: Access to Corp VLAN — likely contains root flag or higher-value targets

### Path 3 — Docker Container Escape
- **Confidence**: LOW | **Complexity**: HIGH
- **Evidence**: Running in Docker with full root. Could attempt container escape but likely not the intended path given the wireless focus.
- **Status**: UNEXPLORED — low priority

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-24T16:43Z | Start with full TCP scan | Standard Phase 1 | Only SSH found, triggered UDP scan |
| 2026-03-24T16:44Z | Run UDP scan | Only 1 TCP port — unusual for HTB | Found SNMP on UDP 161 |
| 2026-03-24T16:45Z | SNMP walk with public community | Standard SNMP enum | Leaked consultant password |
| 2026-03-24T16:46Z | SSH with leaked creds | Direct credential use | Foothold on Docker container |
| 2026-03-24T16:47Z | Wireless scan from container | 7 wlan interfaces present, box name = AirTouch | Found 7 APs, 2 target networks |

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon + Analysis | SNMP cred leak → SSH foothold → Docker container with wireless interfaces → 2 target APs identified | Pending operator confirmation |
