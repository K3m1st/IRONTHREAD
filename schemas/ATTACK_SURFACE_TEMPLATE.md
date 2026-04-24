# Attack Surface Document — Template

Oracle maintains this as a living document throughout the operation. Updated after every evaluation cycle. Single source of truth for operation state.

```markdown
# Attack Surface — {BOX_NAME}
> Last updated: {TIMESTAMP}
> Phase: {1 Recon / 2 Attack Surface Modeling / 3 CVE Research / 4 Exploitation / 5 Post-Access}

## Phase 2 — Attack Surface Modeling
These sections are populated during Phase 2 and reviewed at the Phase 2 Completion Check before CVE research begins.

### Service Inventory
| Port | Service | Version | Confidence | Notes |
|------|---------|---------|------------|-------|

### Service Dossier
Populate one entry per service in the Service Inventory. Depth scales with the service:

- **Services with an API, query interface, or application-layer protocol** (web apps, HTTP APIs, CMSes, databases, source control, message queues, etc.) — populate all fields from official documentation.
- **Services limited to connect/auth** (SSH, FTP, DNS, basic SMTP, bare TCP banner services) — a single line stating the service, version, and "no application-layer API" is sufficient.

#### {service_name} ({version})
- **Docs consulted:** {URLs}
- **Auth model (per docs):** {how auth is supposed to work}
- **API / endpoint structure (per docs):** {canonical endpoints, HTTP methods, required headers}
- **Notable behaviors / quirks:** {required params, side effects, docs-vs-observed divergences}

### Endpoint Map
Per web or API service, enumerated endpoints with response behavior.

#### {service_name} ({host}:{port})
| Endpoint | Method | Status | Response notes / anomalies |
|----------|--------|--------|---------------------------|

### Authentication Model
Per service, how auth works and what has been probed.

#### {service_name}
- **Auth mechanism:** {basic / session-cookie / token / none / unknown}
- **Pre-auth endpoints:** {list}
- **Post-auth endpoints:** {list}
- **Login probes:** {what was tried, what came back}

### Enumeration Status
Per service, what has been enumerated and what has not.

| Service | Enumerated | Remaining | Stop rationale |
|---------|-----------|-----------|----------------|

## Phase 3 — CVE Research
Populated after the Phase 2 Completion Check passes. Research here is scoped to surfaces confirmed in Phase 2.

### Attack Paths
| Rank | Path | Confidence | Complexity | Status | Evidence |
|------|------|------------|------------|--------|----------|

### Vulnerability Primitive
- **Primitive:** {what the attacker controls}
- **Delivery forms:** {all valid forms}
- **Defenses observed:** {what the target filters}
- **Untested forms:** {forms not yet tried}

## Phase 5 — Post-Access Investigation
{NOIRE findings summary, privesc leads}

## Decision Log
| Timestamp | Decision | Rationale | Outcome |
|-----------|----------|-----------|---------|

## Session Log
| Session | Phase | Key findings | Next move confirmed |
|---------|-------|-------------|---------------------|
```
