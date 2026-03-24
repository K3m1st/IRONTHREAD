Write handoff.json to authorize ELLIOT deployment.

This is the most error-prone manual workflow — the command enforces the schema every time.

## Steps

1. Call `memoria_get_state` to get current attack paths and findings
2. Read `../shared/attack_surface.md` for ranked paths and vulnerability primitive analysis
3. Read `../shared/schemas/HANDOFF_SCHEMA.json` for the contract
4. Ask the operator to confirm:
   - Primary attack path
   - Backup path (if any)
   - Turn budget (suggest based on Turn Budget Guidance: 8-12 for trivial, 12-20 for known CVE, 20-30 for multiple forms, 30-40 for complex chains)
5. Write `../shared/handoff.json` with ALL required fields:
   - `elliot_authorized: true`
   - `scope.objective` — specific objective
   - `scope.in_scope` — authorized targets
   - `scope.out_of_scope` — "everything not listed above"
   - `scope.stop_conditions`
   - `scope.max_turns` — from operator confirmation
   - `primary_path` and `backup_path`
   - `vulnerability_primitive` — primitive, delivery_forms, defenses_observed, untested_forms
   - `context_files` — which shared/ files ELLIOT should read
6. Output confirmation:
   ```
   [HANDOFF] handoff.json written. ELLIOT authorized within defined scope.
   Operator: cd ../elliot && claude
   ```

## Trivial Exploit Threshold

If the attack path is a single known-good command (known creds → SSH, default password, one-shot PoC with confirmed version match), set `complexity: "trivial"`, `max_turns: 8`. Don't over-engineer the handoff for 1-turn exploits.
