Read the current operation state from shared/ and present an operational picture.

Check the current working directory to determine if we're inside a box directory. If not, ask the user which box to check.

Read the following files from `../shared/` (or the appropriate shared/ path):
- `target.txt` — box name and target IP
- `operation.md` — agent status
- `attack_surface.md` — if present, current attack paths and findings
- `scouting_report.json` — if present, recon status
- `webdig_findings.json` — if present, web enum status
- `noire_findings.json` — if present, post-access investigation status
- `handoff.json` — if present, current ELLIOT authorization
- `exploit_log.md` — if present, exploitation progress

Present a concise operational picture:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
OPERATION STATUS — {BOX_NAME}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Target: {IP}
Phase: {RECON / WEB ENUM / EXPLOITATION / POST-ACCESS / COMPLETE}

Completed:
- {list of completed phases with key findings}

Current:
- {what phase is active, last action taken}

Attack Paths:
- {ranked paths from attack_surface.md if available}

Recommended Next Step:
- {what the operator should do next}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```
