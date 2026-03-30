# NOIRE Findings — Template

Use this format for `noire_findings.md`. Also produce `noire_findings.json` per `NOIRE_FINDINGS_SCHEMA.json`.

```markdown
# NOIRE Findings
> Target: {TARGET}
> Current Access: {USER} / {PRIVILEGE LEVEL}
> Date: {DATE}

## Access Context
{WHO WE ARE, GROUPS, SHELL QUALITY, LIMITATIONS}

## System Profile
{OS, KERNEL, HOSTNAME, CONTAINERIZATION, KEY SERVICES}

## High-Value Findings
| Finding | Evidence | Why It Matters | Confidence |
|---------|----------|----------------|------------|

## Privilege Escalation Leads
| Rank | Path | Evidence | Complexity | Confidence |
|------|------|----------|------------|------------|

## Credentials And Secrets
{KEYS, TOKENS, CONFIGS, PASSWORD MATERIAL}

## Misconfigurations
{SUDO, FILE PERMS, SERVICES, WRITABLE SCRIPTS, CAPABILITIES}

## Anomalies
{UNEXPECTED RESULTS}

## Oracle Flags
{WHAT ORACLE SHOULD CONSIDER NEXT}

## Tools Executed
| Tool | Command | Output File |
|------|---------|-------------|
```
