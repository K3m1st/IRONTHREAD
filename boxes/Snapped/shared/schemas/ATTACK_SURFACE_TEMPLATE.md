# Attack Surface Document — Template

Oracle maintains this as a living document throughout the operation. Updated after every evaluation cycle. Single source of truth for operation state.

```markdown
# Attack Surface — {BOX_NAME}
> Last updated: {TIMESTAMP}
> Operation status: {RECON / WEB ENUM / EXPLOITATION PHASE / POST-ACCESS / COMPLETE}

## Service Inventory
| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|

## Attack Paths
| Rank | Path | Confidence | Complexity | Status | Evidence |
|------|------|------------|------------|--------|----------|

## Exploit Research
### Vulnerability Primitive
- **Primitive:** {what the attacker controls}
- **Delivery forms:** {all valid forms}
- **Defenses observed:** {what the target filters}
- **Untested forms:** {forms not yet tried}

## Web Enumeration Findings
{Key findings from webdig — vhosts, paths, login surfaces}

## Post-Access Investigation
{NOIRE findings summary, privesc leads}

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
```
