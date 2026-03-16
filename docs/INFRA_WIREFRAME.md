# Infra Wireframe
> Current Phase 1.5 architecture for `IRONTHREAD`

---

## 1. High-Level Flow

```mermaid
flowchart LR
    A["Operator"] --> B["SCOUT"]
    B --> C["shared/scouting_report.md"]
    B --> D["shared/scouting_report.json"]
    D --> E["PLANNER"]
    C --> E
    E --> F["shared/attack_surface.md"]
    E --> G["shared/deployment_webdig.json"]
    G --> H["WEBDIG"]
    H --> I["shared/webdig_findings.md"]
    H --> J["shared/webdig_findings.json"]
    I --> K["PLANNER re-eval"]
    J --> K
    K --> L["shared/handoff.json"]
    L --> M["ELLIOT"]
    M --> N["shared/exploit_log.md"]
    N --> K
```

---

## 2. Current Control Plane

```mermaid
flowchart TD
    A["Prompts"] --> B["Role and reasoning"]
    C["Schemas"] --> D["Artifact shape"]
    E["Validation scripts"] --> F["Phase gate checks"]
    G["Shared state in files"] --> H["Cross-agent memory"]
    I["Operator confirmations"] --> J["Human approval boundary"]

    B --> K["Phase 1.5 control model"]
    D --> K
    F --> K
    H --> K
    J --> K
```

---

## 3. Box-Level Directory Wireframe

```mermaid
flowchart TD
    A["boxes/{BOX_NAME}/"] --> B["scout/"]
    A --> C["planner/"]
    A --> D["webdig/"]
    A --> E["elliot/"]
    A --> F["shared/"]

    B --> B1["CLAUDE.md"]
    B --> B2["SCOUT_SYSTEM_PROMPT.md"]
    B --> B3["SCOUT_REPORT_TEMPLATE.md"]
    B --> B4["SCOUT_REPORT_SCHEMA.json"]

    C --> C1["CLAUDE.md"]
    C --> C2["PLANNER_SYSTEM_PROMPT.md"]

    D --> D1["CLAUDE.md"]
    D --> D2["WEBDIG_SYSTEM_PROMPT.md"]

    E --> E1["CLAUDE.md"]
    E --> E2["ELLIOT_SYSTEM_PROMPT.md"]

    F --> F1["target.txt"]
    F --> F2["operation.md"]
    F --> F3["attack_surface.md"]
    F --> F4["scouting_report.md"]
    F --> F5["scouting_report.json"]
    F --> F6["deployment_webdig.json"]
    F --> F7["webdig_findings.md"]
    F --> F8["webdig_findings.json"]
    F --> F9["handoff.json"]
    F --> F10["exploit_log.md"]
    F --> F11["notes/important_notes.md"]
    F --> F12["schemas/"]
    F --> F13["raw/"]
```

---

## 4. Agent Responsibilities

```mermaid
flowchart LR
    A["SCOUT"] --> A1["Identify services"]
    A --> A2["Stop at identification boundary"]
    A --> A3["Write scouting report"]

    B["PLANNER"] --> B1["Read all available intelligence"]
    B --> B2["Rank attack paths"]
    B --> B3["Authorize next move"]

    C["WEBDIG"] --> C1["Stay inside deployment_webdig.json scope"]
    C --> C2["Enumerate web surface"]
    C --> C3["Return markdown plus JSON"]

    D["ELLIOT"] --> D1["Validate handoff.json"]
    D --> D2["Exploit only in scope"]
    D --> D3["Return to Planner on stop condition"]
```

---

## 5. Web-First Execution Thread

```mermaid
sequenceDiagram
    participant O as Operator
    participant S as SCOUT
    participant P as PLANNER
    participant W as WEBDIG
    participant E as ELLIOT
    participant X as shared/

    O->>S: Start recon
    S->>X: Write scouting_report.md/json
    S->>O: Recommend Planner

    O->>P: Start planning
    P->>X: Read scouting report
    P->>X: Write attack_surface.md
    P->>X: Write deployment_webdig.json
    P->>O: Deploy WEBDIG

    O->>W: Start web enumeration
    W->>X: Read deployment_webdig.json
    W->>X: Write webdig_findings.md/json
    W->>X: Append important notes if needed
    W->>O: Return to Planner

    O->>P: Re-evaluate findings
    P->>X: Read webdig findings
    P->>X: Update attack_surface.md
    P->>X: Write handoff.json
    P->>O: Deploy ELLIOT

    O->>E: Start exploitation
    E->>X: Validate handoff.json
    E->>X: Write exploit_log.md
    E->>X: Append important notes if needed
    E->>O: Return to Planner on stop condition
```

---

## 6. Artifact Dependency Map

```mermaid
flowchart LR
    A["scouting_report.json"] --> B["PLANNER"]
    A --> C["WEBDIG"]
    D["attack_surface.md"] --> B
    D --> E["ELLIOT"]
    F["deployment_webdig.json"] --> C
    G["webdig_findings.json"] --> B
    H["handoff.json"] --> E
    I["important_notes.md"] --> B
    I --> C
    I --> E
```

---

## 7. What Changed In Phase 1.5

```mermaid
flowchart TD
    A["Before"] --> A1["Prompt-heavy coordination"]
    A --> A2["Operator carried sequencing burden"]
    A --> A3["WEBDIG handoff was informal"]

    B["After"] --> B1["deployment_webdig.json required"]
    B --> B2["webdig_findings.json required"]
    B --> B3["handoff.json schema-backed"]
    B --> B4["important_notes.md added"]
    B --> B5["validation scripts added"]
```

---

## 8. Obsidian Note Flow

```mermaid
flowchart LR
    A["SCOUT / PLANNER / WEBDIG / ELLIOT"] --> B["shared/notes/important_notes.md"]
    B --> C["scripts/publish_obsidian_note.sh"]
    C --> D["~/Desktop/AllSeeing/Agent Orchestration Idea"]
    D --> E["IRONTHREAD/Boxes or Architecture notes"]
```

---

## 9. Short Explainer

The current infrastructure is a file-backed multi-agent workflow.

- `SCOUT` discovers and identifies.
- `PLANNER` decides and authorizes.
- `WEBDIG` enumerates web scope under a bounded deployment contract.
- `ELLIOT` exploits only after scoped authorization.
- `shared/` is the system bus.
- `schemas/` and validation scripts are the first step away from prompt-only control.
