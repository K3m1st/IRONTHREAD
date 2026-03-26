# Attack Surface — Kobold
> Last updated: 2026-03-21T21:40Z
> Operation status: EXPLOITATION PHASE — re-establishing foothold

## Service Inventory

| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|
| 22 | OpenSSH | 9.6p1 | HIGH | Standard SSH |
| 80 | nginx | 1.24.0 | HIGH | Redirects to HTTPS |
| 443 | nginx | 1.24.0 | HIGH | Fronts multiple vhosts |
| 3552 | Arcane Docker Mgmt | v1.13.0 | HIGH | Go/SvelteKit, unexplored |

## Virtual Hosts

| Hostname | Service | Notes |
|----------|---------|-------|
| kobold.htb | Main site | nginx default |
| mcp.kobold.htb | MCPJam Inspector | **VULNERABLE** — unauthenticated stdio RCE |
| bin.kobold.htb | PrivateBin | Found via nginx config |

## Attack Paths

1. **MCPJam stdio RCE → reverse shell as ben** — Confidence: HIGH — Complexity: trivial
   Evidence: Confirmed exploitable in prior session. `/api/mcp/connect` with stdio transport spawns arbitrary commands as ben.
   Status: VALIDATED — needs re-execution (box likely reset)

2. **Arcane Docker Management (port 3552) → privesc** — Confidence: MEDIUM — Complexity: unknown
   Evidence: Docker management service running on non-standard port. If ben can interact with Docker API, container escape or volume mount to host root is possible.
   Status: UNEXPLORED — investigate post-foothold

3. **operator group (gid=37) membership** — Confidence: LOW — Complexity: unknown
   Evidence: ben is in operator group. May grant file/service access relevant to privesc.
   Status: UNEXPLORED — investigate post-foothold

## Vulnerability Primitive

### MCPJam Inspector stdio RCE
- **Primitive:** Unsanitized command execution via stdio transport configuration
- **Delivery:** POST to `/api/mcp/connect` with `serverConfig.type: "stdio"` and arbitrary `command`/`args`
- **Defenses observed:** None — no authentication, no input validation
- **Untested forms:** N/A — direct command execution, no filtering to bypass

## Decision Log

| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|
| 2026-03-21T16:30Z | Begin recon | Fresh operation | 4 ports, 3 vhosts identified |
| 2026-03-21T~18:00Z | Exploit MCPJam RCE | Trivial unauthenticated RCE, highest confidence path | Shell as ben, user flag captured |
| 2026-03-21T~19:00Z | Plant SSH key | Stable persistent access | SSH as ben confirmed |
| 2026-03-21T21:40Z | Re-establish foothold | Box likely reset, SSH key lost | Deploying ELLIOT with same exploit |

## Session Log

| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
| 1 | Recon → Exploitation | MCPJam RCE, foothold as ben, user flag | Privesc investigation |
| 2 | Re-exploitation | Box reset, re-establishing foothold | ELLIOT deployment for RCE + reverse shell |
