# Web-First Control Strategy
> Hardening `SCOUT -> PLANNER -> WEBDIG -> ELLIOT` without overloading the model

---

## Core Thesis

Prompt obedience is useful, but it is not a durable control plane.

For this project, prompts should carry:
- role
- tone
- decision style
- prioritization heuristics

Mission-critical behavior should be moved into:
- structured state
- explicit handoff contracts
- transition gates
- small validation checks
- replayable evaluations

That is how this becomes more valuable than "good prompting." It becomes a real multi-agent system with prompts as one layer, not the entire safety model.

---

## Why This Matters

Right now, the strongest ideas in the repo are already pointing in the right direction:
- `scouting_report.json` gives Scout a machine-readable handoff
- `attack_surface.md` acts as persistent memory
- `handoff.json` introduces scoped authorization for ELLIOT

Those are more valuable than prompt wording alone because they externalize state and intent.

The next step is to make the web-first thread work as a controlled pipeline:

1. `SCOUT` identifies web surface and stops at the identification boundary
2. `PLANNER` converts Scout output into one concrete specialist objective
3. `WEBDIG` enumerates only within that objective and returns structured findings
4. `PLANNER` re-ranks paths and writes a scoped exploit authorization
5. `ELLIOT` executes only inside that authorization

If this thread is reliable, the same pattern can later expand to SMB, DNS, and other specialists.

---

## What To Preserve In Prompts

Do not try to remove reasoning from the model. Keep prompts responsible for:
- deciding which tool best fits the current evidence
- explaining why a path is high or low confidence
- adapting when new evidence changes the picture
- writing concise operator-facing briefings

This is where language models add value.

Do not force prompts to be the only enforcement layer for:
- sequencing
- authorization
- in-scope versus out-of-scope behavior
- required outputs
- schema shape
- stop conditions
- retry limits

Those should be system constraints, not "please obey" text.

---

## The Shift: From Prompting To Contracts

The best transition path is:

`mission-critical prompt instructions -> small external contract -> validation gate -> logged decision`

Examples:

- "ELLIOT must stay in scope"
  becomes
  `handoff.json` with `objective`, `in_scope`, `out_of_scope`, and `stop_conditions`

- "Planner must choose one next move"
  becomes
  a required `next_action` object with exactly one `deploys` target and one `objective`

- "WEBDIG should not brute force auth"
  becomes
  an allowed-actions list for the specialist phase plus evaluator checks on the output log

- "Scout should stop at identification"
  becomes
  a report schema that captures identified web surface but does not contain deep enumeration fields

---

## Web-First Target Architecture

### Phase A: Scout Contract

Scout should output a constrained, web-relevant surface summary that Planner can trust.

Minimum contract:
- confirmed web ports
- service type
- stack fingerprint with confidence
- redirects observed
- login pages observed
- notable headers
- anomalies
- explicit gaps
- recommended specialist priority

Important rule:
Scout should not carry deep content discovery fields in its primary schema unless they were discovered incidentally during identification. The more room Scout has to look like WEBDIG, the easier it is for the model to drift.

### Phase B: Planner Deployment Contract

Planner should emit a structured deployment order for WEBDIG before any specialist run.

Recommended artifact:
`shared/deployment_webdig.json`

Minimum fields:
- `authorized`: boolean
- `source_report`: path
- `target`
- `ports`
- `objective`
- `priority_paths`
- `allowed_actions`
- `disallowed_actions`
- `completion_criteria`
- `return_conditions`

This turns WEBDIG from "go do web enum" into "perform this bounded task."

### Phase C: WEBDIG Findings Contract

WEBDIG should return both markdown and JSON.

Recommended artifact:
`shared/webdig_findings.json`

Minimum fields:
- `objective_completed`: boolean
- `ports_enumerated`
- `vhosts_found`
- `paths_found`
- `login_surfaces`
- `tech_confirmations`
- `high_value_findings`
- `anomalies`
- `gaps`
- `planner_flags`
- `evidence_refs`

Planner should ingest the JSON first, then consult markdown for nuance if needed.

### Phase D: Exploit Authorization Contract

Planner already has the start of this with `handoff.json`.

For the web-first thread, that handoff should become stricter:
- one exploit objective
- exact endpoint or path family in scope
- exact credential material in scope if any
- maximum attempt budget
- explicit stop reasons
- mandatory return on new surface

If the objective is "test LFI on `/download?file=`" then ELLIOT should not pivot into admin auth, API fuzzing, or unrelated vhosts unless Planner updates scope.

---

## Minimal Controls That Add A Lot Of Value

These are the highest-leverage additions that do not significantly bog down the model.

### 1. Small JSON contracts at each handoff

Why it helps:
- reduces ambiguity
- compresses context
- makes parsing and validation easy

Why it does not bog down the model:
- short, typed fields are cheaper than long prose reminders

### 2. Phase-specific allowed/disallowed actions

Each agent should receive a short action policy.

Example for WEBDIG:
- allowed: `whatweb`, `ffuf`, `gobuster`, `curl`, JS review, vhost enum
- disallowed: credential spraying, auth attempts, exploit execution

Example for ELLIOT:
- allowed only if listed in handoff scope
- all out-of-scope discoveries become `NEW_SURFACE`

This is much stronger than repeating "do not go deeper."

### 3. Completion criteria and return conditions

Every deployment should say what "done" means.

Example:
- complete when top 3 priority paths are checked, login surfaces described, and wildcard filtering documented
- return early if admin panel found, auth required, or anomalous behavior suggests a different path

This keeps specialists from wandering.

### 4. Output validation before next phase

Before Planner uses WEBDIG output:
- verify required fields exist
- verify objective status is present
- verify evidence references are included

Before ELLIOT runs:
- verify `elliot_authorized == true`
- verify `in_scope` is non-empty
- verify `objective` is singular and concrete

Even lightweight validation increases obedience because the model learns that malformed handoffs fail to advance.

### 5. Replay-based evals

Save a few representative web-box scenarios and grade:
- did Scout stop at the right boundary?
- did Planner give one clear next move?
- did WEBDIG stay within scope?
- did Planner re-evaluate before exploitation?
- did ELLIOT avoid unauthorized pivots?

This is where the project starts becoming capstone-grade.

---

## What Makes This More Valuable Than Prompt Engineering

If you stop at "better prompts," the output is:
- hard to measure
- hard to compare
- brittle across model versions
- difficult to publish as a systems contribution

If you move to contracts and gates, the output becomes:
- evaluable
- explainable
- model-agnostic
- extensible to new specialists
- publishable as workflow orchestration research

The value shifts from:
"I wrote strong prompts"

to:
"I designed a constrained multi-agent control architecture for stateful technical workflows."

That is a much stronger capstone story.

---

## Recommended Build Order

Keep this intentionally narrow at first.

### Step 1
Harden the web-only thread:
- Scout
- Planner
- WEBDIG
- Planner re-eval
- ELLIOT

Do not add SMB or DNS controls until this path is reliable.

### Step 2
Add missing machine-readable artifacts:
- `deployment_webdig.json`
- `webdig_findings.json`
- `handoff.schema.json`

### Step 3
Add lightweight validators:
- schema presence checks
- required field checks
- phase transition checks

### Step 4
Create 3-5 replay scenarios and a grading rubric.

### Step 5
Only after that, move the state layer toward MCP.

MCP should not be the first fix for obedience. It should be the scaling layer after the contracts are clear.

---

## Concrete Design Principle

Use prompts for judgment.
Use contracts for control.
Use validators for enforcement.
Use logs for auditability.
Use evals for truth.

That combination helps the model instead of burdening it.

---

## Immediate Next Changes To Consider

1. Add `deployment_webdig.json` as a required Planner artifact before any WEBDIG run.
2. Add `webdig_findings.json` as a required WEBDIG artifact in parallel with markdown.
3. Add a JSON schema for `handoff.json` instead of defining it only inline in prose.
4. Narrow Scout's web fields so Scout cannot easily drift into WEBDIG territory.
5. Add a simple validator script that checks whether phase artifacts are complete before allowing the next phase.

---

## One-Sentence Project Framing

This project is most valuable when framed as a constrained, stateful, multi-agent orchestration system for offensive security workflows, not as a collection of high-quality prompts.
