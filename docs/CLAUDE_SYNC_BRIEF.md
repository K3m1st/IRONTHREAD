# Claude Sync Brief
> Copy/paste context for another Claude Code session

```text
This repo is now operating under a Phase 1.5 web-first workflow:

Scout -> Planner -> WEBDIG -> Planner -> ELLIOT -> NOIRE -> Planner -> ELLIOT

Important changes already implemented:
- Planner must write shared/deployment_webdig.json before any WEBDIG run.
- WEBDIG must return both webdig_findings.md and webdig_findings.json.
- Planner must write shared/deployment_noire.json before any NOIRE run.
- NOIRE must return both noire_findings.md and noire_findings.json.
- Planner must write shared/handoff.json before any ELLIOT run.
- shared/notes/important_notes.md is the durable note file.
- shared/schemas/ contains box-local schema references.
- scripts/validate_phase_artifacts.sh can validate WEBDIG, NOIRE, and ELLIOT artifacts.
- Planner, WEBDIG, ELLIOT, and NOIRE all explicitly use live web research protocols instead of relying only on training data.

Migration rule:
- Preserve shared/
- Replace/update templates and box-local agent instruction files
- Resume from Planner after migration
```
