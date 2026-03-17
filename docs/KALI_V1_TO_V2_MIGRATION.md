# Kali Migration Note
> Move a live box from V1 workflow to the current V2-style flow without losing memory

Preserve:
- `shared/target.txt`
- `shared/scouting_report.*`
- `shared/attack_surface.md`
- `shared/*_findings.*`
- `shared/exploit_log.md`
- `shared/raw/`
- `shared/notes/important_notes.md`

Replace/update:
- `scout/`
- `planner/`
- `webdig/`
- `elliot/`
- `noire/`

Backfill:
- `shared/schemas/`
- `shared/notes/important_notes.md`

Resume from:
- `planner/`
