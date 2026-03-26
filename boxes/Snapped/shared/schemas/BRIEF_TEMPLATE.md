# Oracle Operational Brief — Template

Use this format for every brief delivered to the operator.

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ORACLE] OPERATIONAL BRIEF — {TIMESTAMP}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXECUTIVE SUMMARY
{3-5 sentences maximum. Current operation status, most significant finding
since last brief, and single recommended next move. Operator should be able
to make a decision from this alone.}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FULL DETAIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ATTACK SURFACE (current state)
{Complete picture of what is known, organized by service/category.
Confidence levels on every finding. Updated since last brief flagged with ★}

ATTACK PATHS (ranked by confidence and yield)
1. {PATH} — Confidence: {HIGH/MEDIUM/LOW} — Complexity: {HIGH/MEDIUM/LOW}
   Evidence: {WHAT SUPPORTS THIS PATH}
   Status: {UNEXPLORED / IN PROGRESS / VALIDATED / EXHAUSTED}

2. {PATH} — ...

EXPLOIT RESEARCH
{Only present if a CVE or known exploit path has been identified.
Full picture — CVE details, affected versions, PoC availability, exploit
complexity, environmental fit, reliability assessment.
Include vulnerability primitive analysis: what the attacker controls,
all valid input forms, and which remain untested.
Nothing surfaces here until research is complete.}

ENUMERATION FINDINGS (this cycle)
{What came back from the current phase.
Key findings only — full detail in output files.}

ANOMALIES
{Anything unexpected, inconsistent, or that doesn't fit the picture.
These often matter more than clean findings.}

GAPS
{What is still unknown. What enumeration, if any, remains warranted.}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
RECOMMENDATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NEXT MOVE: {SINGLE RECOMMENDED ACTION}
RATIONALE: {WHY THIS AND NOT SOMETHING ELSE}
OBJECTIVE: {SPECIFIC GOAL — NOT OPEN-ENDED}

Confirm or override?
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

The executive summary is always at the top. The recommendation is always a single move with a specific objective.
