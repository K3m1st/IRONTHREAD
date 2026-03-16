# Claude Sync Brief
> Copy/paste context for another Claude Code session

Use this to bring another Claude session up to date quickly.

```text
This repo is now operating under a Phase 1.5 web-first workflow:

Scout -> Planner -> WEBDIG -> Planner -> ELLIOT

Important changes already implemented:
- Planner must write shared/deployment_webdig.json before any WEBDIG run.
- WEBDIG must return both webdig_findings.md and webdig_findings.json.
- Planner must write shared/handoff.json before any ELLIOT run (Step 6.5).
- ELLIOT hard-stops if handoff.json is missing or elliot_authorized != true.
- ELLIOT logs out-of-scope discoveries as [NEW SURFACE] without pursuing them.
- ELLIOT writes a structured return entry to exploit_log.md on any stop condition.
- handoff.json now includes scope.max_attempts_per_path.
- shared/notes/important_notes.md is the durable note file.
- shared/schemas/ contains box-local schema references.
- scripts/validate_phase_artifacts.sh can validate WEBDIG and ELLIOT artifacts.
- Planner, WEBDIG, and ELLIOT all explicitly use live web research protocols instead of relying only on training data.

Current repo guidance:
- Read README.md
- Read docs/PHASE_1_5.md
- Read docs/INFRA_WIREFRAME.md
- Read tmp/KALI_V1_TO_V2_MIGRATION.md if working on a live box migration

Migration rule:
- Preserve shared/
- Replace/update templates and box-local agent instruction files
- Resume from Planner after migration

If syncing a live box, do not discard:
- shared/target.txt
- shared/scouting_report.md
- shared/scouting_report.json
- shared/attack_surface.md
- shared/*_findings.md
- shared/exploit_log.md
- shared/raw/
- shared/notes/important_notes.md
```
