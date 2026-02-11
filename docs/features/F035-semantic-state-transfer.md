# F035: Semantic State Transfer

> **Status:** Proposed
> **Target:** v1.0.0 (Multi-Agent Cognition Network)
> **Source:** Cisco Outshift Internet of Cognition, README roadmap

## Overview
Export and import decision context in a portable, self-contained format. Enables an agent to package its decision history, reasoning traces, and relevant guardrails into a transferable bundle that another agent - potentially on a different platform - can ingest and use.

## Problem
Today, decision intelligence is locked inside a single CSTP server instance. If Agent A works on a problem and Agent B needs to continue, B must either query A's server (requires network access) or start from scratch. There's no offline, portable way to transfer cognitive context.

## Concept

### Export: Decision Context Bundle
```json
{
  "format": "cstp-bundle/v1",
  "exported_at": "2026-02-11T20:00:00Z",
  "agent": "emerson",
  "scope": {
    "project": "tfatykhov/cognition-agent-decisions",
    "tags": ["architecture"],
    "date_range": ["2026-02-01", "2026-02-11"]
  },
  "decisions": [
    {
      "id": "dec_abc",
      "decision": "...",
      "confidence": 0.85,
      "reasons": [...],
      "deliberation": {...},
      "bridge": {"structure": "...", "function": "..."},
      "outcome": "success",
      "related": ["dec_def"]
    }
  ],
  "guardrails": [...],
  "patterns": {
    "calibration": {...},
    "anti_patterns": [...]
  }
}
```

### Import: Context Ingestion
Receiving agent ingests the bundle into its own decision store, tagged with provenance:
```json
{
  "source_agent": "emerson",
  "imported_at": "2026-02-11T21:00:00Z",
  "trust_score": 0.85
}
```

## API

### `cstp.exportBundle`
```json
{
  "method": "cstp.exportBundle",
  "params": {
    "scope": {
      "project": "owner/repo",
      "tags": ["architecture"],
      "dateRange": {"from": "2026-02-01", "to": "2026-02-11"}
    },
    "includeDeliberation": true,
    "includeGuardrails": true,
    "format": "json"
  }
}
```

### `cstp.importBundle`
```json
{
  "method": "cstp.importBundle",
  "params": {
    "bundle": {...},
    "trustScore": 0.85,
    "conflictResolution": "keep_both"
  }
}
```

## Integration
- Builds on F031 (Source Trust Scoring) for trust on imported decisions
- Enables F035+ features (reasoning continuity, collective innovation)
- Protocol-agnostic: works over SSTP, file transfer, or API

## Acceptance Criteria
- [ ] `cstp.exportBundle` RPC method
- [ ] `cstp.importBundle` RPC method
- [ ] MCP tools exposed
- [ ] Provenance tracking on imported decisions
- [ ] Selective export (by project, tags, date range)
- [ ] Conflict resolution strategies (keep_both, prefer_local, prefer_remote)
- [ ] Bundle validation and schema versioning
