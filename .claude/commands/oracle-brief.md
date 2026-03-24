Deliver a full operational brief to the operator.

This is Oracle's core output — the brief that makes the next decision obvious.

## Steps

1. Call `memoria_get_state` to get the current operational picture
2. Read `../shared/attack_surface.md` for the full decision log
3. Read any recent findings files that have been updated since the last brief:
   - `../shared/scouting_report.md` (if recon phase)
   - `../shared/webdig_findings.md` (if web enum phase)
   - `../shared/noire_findings.md` (if post-access phase)
   - `../shared/exploit_log.md` (if ELLIOT has returned)
4. Read `../shared/schemas/BRIEF_TEMPLATE.md` for the output format
5. Assemble and deliver the brief using that format

## Rules

- Executive summary at the top — operator makes the fast call from there
- Every finding gets a confidence level (HIGH/MEDIUM/LOW)
- Recommendation is always a SINGLE move with a specific objective
- Flag anything updated since last brief with ★
- Do not brief on incomplete CVE research — full picture or nothing
- End with "Confirm or override?" and wait
