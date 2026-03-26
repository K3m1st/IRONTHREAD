# Important Notes — Kobold
> Created: Sat Mar 21 04:30:18 PM CDT 2026
> Target IP: 10.129.7.164

## Key Findings

### MCPJam Inspector — Unauthenticated RCE via stdio transport
- **Location:** https://mcp.kobold.htb/api/mcp/connect
- **Mechanism:** The stdio transport type spawns arbitrary commands server-side. The endpoint expects an MCP server command, but executes whatever you give it — no auth, no validation.
- **Implication:** Any command runs as `ben` (uid=1001). The MCP connection always reports failure (not a real MCP server), but the subprocess fires regardless.
- **Lesson:** MCP Inspector tools that support stdio transport are trivially exploitable if exposed without auth. The "failure" response is misleading — the command still ran.

### Target Architecture
- nginx 1.24.0 fronts multiple vhosts: kobold.htb (main), mcp.kobold.htb (MCPJam Inspector), bin.kobold.htb (PrivateBin)
- Arcane Docker Management v1.13.0 on port 3552 (Go/SvelteKit) — unexplored, potential privesc vector if it manages Docker
- ben is in `operator` group (gid=37) — non-standard group, likely grants access to something specific
- SSL wildcard cert (*.kobold.htb) means additional vhosts could exist

### Operational Notes
- SSH key persistence worked cleanly — plant pubkey via RCE, SSH in for stable shell
- PrivateBin (bin.kobold.htb) discovered via nginx config, not via vhost fuzzing — always check server configs
- Port 3552 (Arcane Docker Mgmt) is the most interesting unexplored surface for privesc
