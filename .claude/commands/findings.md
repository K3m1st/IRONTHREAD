Summarize all findings from the current operation.

Check the current working directory to determine if we're inside a box directory. If not, ask the user which box to check.

Read ALL findings files from `../shared/` (or the appropriate shared/ path):
- `scouting_report.md` and `scouting_report.json` — recon findings
- `webdig_findings.md` and `webdig_findings.json` — web enumeration findings
- `noire_findings.md` and `noire_findings.json` — post-access investigation findings
- `exploit_log.md` — exploitation results
- `attack_surface.md` — consolidated attack surface

Present a consolidated findings summary:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FINDINGS SUMMARY — {BOX_NAME}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Services Discovered:
- {from scouting report}

Web Findings:
- {from webdig findings — vhosts, paths, login surfaces, high-value items}

Credentials & Secrets:
- {from any source — git dumps, config files, noire findings}

Access Obtained:
- {from exploit log — what footholds exist}

Post-Access Intelligence:
- {from noire findings — privesc leads, system profile}

High-Value Items:
- {consolidated list of most actionable findings across all sources}

Open Gaps:
- {what still needs investigation}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

Only include sections that have data. Skip sections where the corresponding files don't exist yet.
