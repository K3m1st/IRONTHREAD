# SCOUTING REPORT — Markdown Template
> Operation: {OPERATION_NAME}
> Target: {TARGET_IP} / {TARGET_HOSTNAME}
> Date: {DATE}
> Agent: SOVA v1.0
> Status: {COMPLETE | PARTIAL}

---

## EXECUTIVE SUMMARY

> 2-4 sentences. What is this target? What is the attack surface at a glance? What should the Planner focus on first?

{SUMMARY}

---

## TARGET PROFILE

| Field | Value |
|-------|-------|
| IP Address | {IP} |
| Hostname | {HOSTNAME or UNKNOWN} |
| OS (detected) | {OS or UNKNOWN} |
| OS Confidence | {HIGH / MEDIUM / LOW} |
| Open Ports | {COUNT} |
| Attack Surface Categories | {LIST} |

---

## OPEN PORTS & SERVICES

| Port | Protocol | Service | Version | Confidence | Notes |
|------|----------|---------|---------|------------|-------|
| {PORT} | {TCP/UDP} | {SERVICE} | {VERSION or UNKNOWN} | {HIGH/MEDIUM/LOW} | {NOTES} |

---

## ENUMERATION FINDINGS

### Web (HTTP/HTTPS)
> Complete if ports 80, 443, 8080, 8443, or other web ports detected. Otherwise omit.

- **Technology Stack:** {WHATWEB OUTPUT — CMS, frameworks, server, languages detected}
- **Interesting Directories/Files:**
  - `{PATH}` — {DESCRIPTION} — Confidence: {LEVEL}
  - `{PATH}` — {DESCRIPTION} — Confidence: {LEVEL}
- **Notable Headers:** {SECURITY HEADERS PRESENT/MISSING, SERVER HEADER, etc.}
- **Login Pages Detected:** {YES/NO — paths if yes}
- **Notable Response Codes:** {403s, redirects, unusual codes worth flagging}

---

### File Sharing (SMB / FTP / NFS)
> Complete if ports 445, 139, 21, 2049 detected. Otherwise omit.

- **Anonymous Access:** {YES / NO / NOT TESTED}
- **Shares Enumerated:** {LIST or NONE}
- **Interesting Files:** {LIST or NONE}
- **Domain/Workgroup:** {VALUE or UNKNOWN}

---

### Remote Access (SSH / RDP / WinRM)
> Complete if ports 22, 3389, 5985 detected. Otherwise omit.

- **SSH Version:** {VALUE}
- **Authentication Methods:** {PASSWORD / KEY / OTHER}
- **Notes:** {ANYTHING UNUSUAL}

---

### Name Resolution (DNS)
> Complete if port 53 detected. Otherwise omit.

- **Zone Transfer Attempted:** {YES/NO}
- **Zone Transfer Result:** {SUCCESS — records listed / FAILED}
- **Hostnames Discovered:** {LIST}
- **Subdomains Discovered:** {LIST}

---

### Database Services
> Complete if database ports detected (3306, 1433, 5432, 6379, 27017). Otherwise omit.

- **Service:** {MYSQL / MSSQL / POSTGRESQL / REDIS / MONGODB}
- **Version:** {VALUE or UNKNOWN}
- **Anonymous Access:** {YES / NO / NOT TESTED}
- **Notes:** {ANYTHING UNUSUAL}

---

### Other / Unusual Services
> Document any ports or services that don't fit above categories.

| Port | Service | Notes | Confidence |
|------|---------|-------|------------|
| {PORT} | {SERVICE} | {NOTES} | {LEVEL} |

---

## ANOMALIES

> Things that were unexpected, unclear, or don't fit the normal pattern. These are not necessarily vulnerabilities — they are unknowns that need attention.

- **[ANOMALY-001]** {DESCRIPTION} — Detected via: {TOOL/METHOD} — Recommended follow-up: {ACTION}
- **[ANOMALY-002]** {DESCRIPTION} — Detected via: {TOOL/METHOD} — Recommended follow-up: {ACTION}

---

## GAPS

> Areas where deeper enumeration is needed. These are the Planner's first priorities.

- **[GAP-001]** {DESCRIPTION} — Why: {REASON} — Suggested approach: {METHOD}
- **[GAP-002]** {DESCRIPTION} — Why: {REASON} — Suggested approach: {METHOD}

---

## PLANNER RECOMMENDATIONS

> Prioritized list of next steps for the Planner agent. Evidence-based, ranked by likelihood of yield.

1. **{ACTION}** — Rationale: {WHY} — Target: {WHERE}
2. **{ACTION}** — Rationale: {WHY} — Target: {WHERE}
3. **{ACTION}** — Rationale: {WHY} — Target: {WHERE}

---

## TOOLS EXECUTED

| Tool | Command | Output File |
|------|---------|-------------|
| nmap | `{FULL COMMAND}` | `nmap_initial.txt` |
| whatweb | `{FULL COMMAND}` | `whatweb.txt` |
| gobuster | `{FULL COMMAND}` | `gobuster.txt` |
| {TOOL} | `{FULL COMMAND}` | `{FILE}` |

---

## RAW OUTPUT REFERENCES

All raw tool output saved to: `{OPERATION_DIR}/raw/`

---
`[HANDOFF]` Recon complete. Planner may proceed.
