# Checkpoint — Kobold
> Saved: 2026-03-22T00:10Z
> Target: 10.129.7.164
> Operation status: COMPLETE
> Current phase: Both flags captured. Ready for writeup.

## Where We Are Right Now
Operation complete. User flag and root flag captured. Root obtained via pre-exploited world-writable /usr/bin/bash — a prior player (or the box itself) had already replaced bash with a SUID-dropping wrapper and /tmp/rootbash existed with SUID root. We missed this for ~2 hours while chasing Arcane JWT forgery. Key lesson documented in memory.

## Confirmed Facts
- Target: 10.129.7.164, kobold.htb
- User flag: `f1057924705f1ae16e6b57d59b439aeb` (/home/ben/user.txt)
- Root flag: `98c2e7694dba838e4d28cf913f178fd0` (/root/root.txt)
- Foothold: MCPJam Inspector stdio RCE -> reverse shell as ben -> SSH key persistence
- Privesc: /usr/bin/bash world-writable (0777), replaced with wrapper that creates SUID /tmp/rootbash when root executes bash. /tmp/rootbash -p gives euid=0.

## Kill Chain
1. Recon: nmap -> 4 ports (22, 80/443, 3552). Vhost fuzz -> mcp.kobold.htb, bin.kobold.htb
2. Foothold: MCPJam Inspector unauthenticated stdio RCE (POST /api/mcp/connect) -> shell as ben
3. Persistence: SSH key planted via curl download method
4. Privesc: /usr/bin/bash was world-writable and already replaced with SUID wrapper. /tmp/rootbash -p -> root

## Post-Mortem
NOIRE reported /usr/bin/bash as 0777 and 158 bytes but did not check file contents or whether the attack had already succeeded. Oracle spent ~2 hours on Arcane JWT forgery before the operator caught that the wrapper was already deployed and /tmp/rootbash existed. Lessons saved to memory.
