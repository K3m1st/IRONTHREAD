# Infra Wireframe
> Current Phase 3 architecture for `IRONTHREAD`

---

## 1. High-Level Flow

```mermaid
flowchart LR
    A["Operator"] --> B["ORACLE"]
    B --> C["sova-mcp tools"]
    C --> D["shared/scouting_report.md/json"]
    D --> B
    B --> E["shared/attack_surface.md"]
    B --> F["webdig-mcp tools"]
    F --> G["shared/webdig_findings.md/json"]
    G --> B
    B --> H["shared/handoff.json"]
    H --> I["ELLIOT"]
    I --> J["shared/exploit_log.md"]
    J --> B
    B --> K["noire-mcp tools"]
    K --> L["shared/noire_findings.md/json"]
    L --> B
```

---

## 2. Current Control Plane

```mermaid
flowchart TD
    A["Prompts"] --> B["Role and reasoning"]
    C["MCP Tools"] --> D["Tool execution boundary"]
    E["Schemas"] --> F["Artifact shape"]
    G["Validation scripts"] --> H["Phase gate checks"]
    I["Shared state in files"] --> J["Cross-session memory"]
    K["Operator confirmations"] --> L["Human approval boundary"]

    B --> M["Phase 3 control model"]
    D --> M
    F --> M
    H --> M
    J --> M
    L --> M
```

---

## 3. Box-Level Directory Wireframe

```mermaid
flowchart TD
    A["boxes/{BOX_NAME}/"] --> B["oracle/"]
    A --> C["elliot/"]
    A --> D["shared/"]

    B --> B1["CLAUDE.md"]
    B --> B2["ORACLE_SYSTEM_PROMPT.md"]
    B --> B3[".claude/settings.local.json — MCP config"]

    C --> C1["CLAUDE.md"]
    C --> C2["ELLIOT_SYSTEM_PROMPT.md"]

    D --> D1["target.txt"]
    D --> D2["operation.md"]
    D --> D3["attack_surface.md"]
    D --> D4["scouting_report.md/json"]
    D --> D5["webdig_findings.md/json"]
    D --> D6["noire_findings.md/json"]
    D --> D7["handoff.json"]
    D --> D8["exploit_log.md"]
    D --> D9["notes/important_notes.md"]
    D --> D10["schemas/"]
    D --> D11["raw/"]
```

---

## 4. Agent Responsibilities

```mermaid
flowchart LR
    A["ORACLE"] --> A1["Run recon via sova-mcp"]
    A --> A2["Research CVEs and rank attack paths"]
    A --> A3["Enumerate web via webdig-mcp"]
    A --> A4["Investigate post-access via noire-mcp"]
    A --> A5["Brief operator and write handoff.json"]

    B["ELLIOT"] --> B1["Validate handoff.json"]
    B --> B2["Exploit only in scope"]
    B --> B3["Return to Oracle on stop condition"]
```

---

## 5. Execution Thread

```mermaid
sequenceDiagram
    participant O as Operator
    participant R as ORACLE
    participant E as ELLIOT
    participant X as shared/

    O->>R: Start operation
    R->>X: sova-mcp → scouting_report.md/json
    R->>X: Write attack_surface.md
    R->>O: Brief — recommend web enum

    O->>R: Confirm
    R->>X: webdig-mcp → webdig_findings.md/json
    R->>X: Update attack_surface.md
    R->>X: Write handoff.json
    R->>O: Brief — deploy ELLIOT

    O->>E: Start exploitation
    E->>X: Validate handoff.json
    E->>X: Write exploit_log.md
    E->>O: Return with foothold

    O->>R: Re-evaluate foothold
    R->>X: noire-mcp → noire_findings.md/json
    R->>X: Update attack_surface.md
    R->>X: Write handoff.json (privesc)
    R->>O: Brief — deploy ELLIOT for privesc

    O->>E: Execute privesc
    E->>X: Write exploit_log.md
    E->>O: Return
```

---

## 6. Artifact Dependency Map

```mermaid
flowchart LR
    A["scouting_report.json"] --> B["ORACLE"]
    C["attack_surface.md"] --> B
    C --> D["ELLIOT"]
    E["webdig_findings.json"] --> B
    F["noire_findings.json"] --> B
    G["handoff.json"] --> D
    H["important_notes.md"] --> B
    H --> D
```

---

## 7. MCP Tool Servers

```mermaid
flowchart TD
    A["ORACLE"] --> B["sova-mcp"]
    A --> C["webdig-mcp"]
    A --> D["noire-mcp"]

    B --> B1["sova_full_scan"]
    B --> B2["sova_whatweb"]
    B --> B3["sova_banner_grab"]
    B --> B4["sova_zone_transfer"]
    B --> B5["sova_null_session"]
    B --> B6["sova_anon_ftp"]

    C --> C1["webdig_dir_bust"]
    C --> C2["webdig_vhost_fuzz"]
    C --> C3["webdig_whatweb"]
    C --> C4["webdig_curl"]
    C --> C5["webdig_js_review"]

    D --> D1["noire_system_profile"]
    D --> D2["noire_sudo_check"]
    D --> D3["noire_suid_scan"]
    D --> D4["noire_cron_inspect"]
    D --> D5["noire_service_enum"]
    D --> D6["noire_config_harvest"]
    D --> D7["noire_writable_paths"]
```

---

## 8. What Changed In Phase 3

```mermaid
flowchart TD
    A["Before: 5 agent sessions"] --> A1["Operator cd between sova/ planner/ webdig/ elliot/ noire/"]
    A --> A2["Manual sequencing of 5 agents"]
    A --> A3["deployment_webdig.json and deployment_noire.json required"]

    B["After: 2 agent sessions"] --> B1["Oracle handles recon + analysis + enum via MCP tools"]
    B --> B2["Only Oracle and Elliot as agent sessions"]
    B --> B3["MCP tools replace 3 separate agents"]
    B --> B4["Operator flow: Oracle → Elliot → Oracle → Elliot"]
```

---

## 9. Obsidian Note Flow

```mermaid
flowchart LR
    A["ORACLE / ELLIOT"] --> B["shared/notes/important_notes.md"]
    B --> C["scripts/publish_obsidian_note.sh"]
    C --> D["~/Desktop/AllSeeing/Agent Orchestration Idea"]
    D --> E["IRONTHREAD/Boxes or Architecture notes"]
```

---

## 10. Short Explainer

The current infrastructure is a two-agent system with MCP tool servers.

- `ORACLE` runs recon (sova-mcp), analyzes and researches CVEs, enumerates web surface (webdig-mcp), investigates post-access (noire-mcp), briefs the operator, and writes scoped handoff.json.
- `ELLIOT` exploits only after scoped authorization via handoff.json.
- `shared/` is the system bus — all intelligence flows through files.
- `schemas/` define artifact contracts.
- MCP servers wrap CLI tools (nmap, gobuster, ffuf, etc.) as structured tool calls.
