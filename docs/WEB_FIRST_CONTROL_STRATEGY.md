# Web-First Control Strategy
> Hardening `Oracle → ELLIOT` without overloading the model

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

The strongest ideas in the repo externalize state and intent:
- `scouting_report.json` gives Oracle structured recon output
- `attack_surface.md` acts as persistent memory
- `handoff.json` introduces scoped authorization for ELLIOT
- MCP tool servers enforce tool boundaries (recon tools vs web enum tools vs post-access tools)

The web-first thread works as a controlled pipeline:

1. Oracle runs recon (sova-mcp) and stops at the identification boundary
2. Oracle researches CVEs and builds attack surface
3. Oracle enumerates web surface (webdig-mcp) with reasoned wordlist strategy
4. Oracle writes a scoped exploit authorization (handoff.json)
5. ELLIOT executes only inside that authorization
6. Oracle investigates post-access (noire-mcp) and writes next handoff

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

- "Oracle must choose one next move"
  becomes
  a required brief format with exactly one recommendation and one objective

- "Sova should stop at identification"
  becomes
  the identification boundary table in Oracle's system prompt plus scouting report schema that captures identified surface but not deep enumeration

---

## Contract Architecture

### Phase A: Recon Output Contract

Oracle writes scouting report via sova-mcp tools. Schema enforces:
- confirmed ports with versions and confidence
- service type categorization
- anomalies and gaps
- oracle recommendations (priority-ordered)

Reference: `schemas/SOVA_REPORT_SCHEMA.json`

### Phase B: Web Findings Contract

Oracle writes webdig findings via webdig-mcp tools. Schema enforces:
- objective and completion status
- ports enumerated, tech confirmations
- vhosts, paths, login surfaces
- high-value findings with evidence
- oracle flags

Reference: `schemas/WEBDIG_FINDINGS_SCHEMA.json`

### Phase C: Exploit Authorization Contract

Oracle writes `handoff.json` before deploying ELLIOT:
- one exploit objective
- exact targets in scope
- maximum attempt budget and turn budget
- explicit stop reasons
- mandatory return on new surface
- vulnerability primitive with all delivery forms

Reference: `schemas/HANDOFF_SCHEMA.json`

### Phase D: Post-Access Findings Contract

Oracle writes noire findings via noire-mcp tools. Schema enforces:
- current access context
- system profile
- privesc leads (ranked)
- credentials and secrets
- oracle flags

Reference: `schemas/NOIRE_FINDINGS_SCHEMA.json`

---

## Minimal Controls That Add A Lot Of Value

### 1. Small JSON contracts at each handoff

Short, typed fields are cheaper than long prose reminders. They reduce ambiguity, compress context, and make validation easy.

### 2. MCP tool boundaries

Recon tools (sova-mcp) are separate from web enum tools (webdig-mcp) and post-access tools (noire-mcp). Oracle decides which tool set to use based on operation phase. The tool servers enforce what commands can run.

### 3. Completion criteria in the brief cycle

Oracle briefs the operator after each phase. The brief format requires a single recommendation with specific objective. The operator confirms or overrides. This prevents drift.

### 4. Output validation before next phase

`validate_phase_artifacts.sh` checks:
- recon: scouting_report.json is COMPLETE with required fields
- webdig: findings have objective status, oracle flags, evidence refs
- elliot: handoff.json has authorization, scope, and vulnerability primitive
- noire: findings have access context, privesc leads, oracle flags

### 5. Replay-based evals

Save representative box scenarios and grade:
- did Oracle stop at identification boundary during recon?
- did Oracle give one clear next move per brief?
- did Oracle stay within web enum scope?
- did Oracle re-evaluate before exploitation?
- did ELLIOT avoid unauthorized pivots?

---

## What Makes This More Valuable Than Prompt Engineering

If you stop at "better prompts," the output is:
- hard to measure
- hard to compare
- brittle across model versions
- difficult to publish as a systems contribution

If you move to contracts, MCP tools, and gates, the output becomes:
- evaluable
- explainable
- model-agnostic
- extensible
- publishable as workflow orchestration research

The value shifts from:
"I wrote strong prompts"

to:
"I designed a constrained multi-agent control architecture for stateful technical workflows."

That is a much stronger capstone story.

---

## Concrete Design Principle

Use prompts for judgment.
Use contracts for control.
Use MCP tools for execution boundaries.
Use validators for enforcement.
Use logs for auditability.
Use evals for truth.

That combination helps the model instead of burdening it.

---

## One-Sentence Project Framing

This project is most valuable when framed as a constrained, stateful, multi-agent orchestration system for offensive security workflows, not as a collection of high-quality prompts.
