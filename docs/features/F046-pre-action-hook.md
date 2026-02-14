# F046: Pre-Action Hook API

**Status:** Proposed
**Priority:** High
**Category:** Agentic Loop Integration

## Problem

Integrating CSTP into an agent's decision loop currently requires 3 separate API calls before acting:
1. `queryDecisions` - find relevant past decisions
2. `checkGuardrails` - validate the action is allowed
3. `recordDecision` - commit intent before executing

This 3-call overhead discourages adoption. Agents skip steps under time pressure. Our own experience confirms this - the single biggest process failure is skipping the pre-decision query (documented in 4+ violations).

## Solution

A single `cstp.preAction` endpoint that combines query + guardrails + optional record in one round-trip. Designed to be called at the decision point in any agentic loop.

### API

```json
{
  "method": "cstp.preAction",
  "params": {
    "agent_id": "claude-code",
    "action": {
      "description": "Refactor auth module to use JWT instead of sessions",
      "category": "architecture",
      "stakes": "high",
      "confidence": 0.80
    },
    "options": {
      "query_limit": 5,
      "auto_record": true,
      "include_patterns": true
    }
  }
}
```

### Response

```json
{
  "result": {
    "allowed": true,
    "decision_id": "dec-a3f8b2c1",

    "relevant_decisions": [
      {
        "id": "dec-7e2f",
        "decision": "Chose JWT for API auth in microservice layer",
        "outcome": "success",
        "date": "2026-01-15",
        "pattern": "Stateless auth scales better than session-based",
        "confidence": 0.90,
        "similarity": 0.87
      }
    ],

    "guardrail_results": [
      {
        "name": "no-high-stakes-low-confidence",
        "status": "pass",
        "message": null
      },
      {
        "name": "no-production-without-review",
        "status": "warn",
        "message": "High-stakes change - ensure code review before merge"
      }
    ],

    "calibration_context": {
      "category_accuracy": 0.91,
      "category_brier": 0.03,
      "confidence_tendency": "slightly_underconfident",
      "suggestion": "Your architecture decisions succeed 91% of the time - confidence of 0.80 may be low"
    },

    "patterns_summary": [
      "Stateless auth scales better than session-based (3 confirmations)",
      "Migration decisions need rollback plan (2 confirmations)"
    ]
  }
}
```

### Behavior

1. **Query:** Semantic search for similar past decisions (hybrid mode)
2. **Guardrails:** Run all active guardrails against the proposed action
3. **Calibration:** Fetch agent's calibration profile for this category
4. **Patterns:** Extract relevant confirmed patterns from matching decisions
5. **Record (optional):** If `auto_record: true` and guardrails pass, record the decision immediately and return `decision_id`
6. **Block:** If any guardrail blocks, return `allowed: false` with reasons. Decision is NOT recorded.

### Blocked Response

```json
{
  "result": {
    "allowed": false,
    "decision_id": null,
    "block_reasons": [
      {
        "guardrail": "no-high-stakes-low-confidence",
        "message": "Stakes=high but confidence=0.35. Increase confidence or lower stakes.",
        "suggestion": "Research more before proceeding, or break into smaller decisions"
      }
    ],
    "relevant_decisions": [...],
    "calibration_context": {...}
  }
}
```

### MCP Tool Definition

```json
{
  "name": "pre_action",
  "description": "Check if an action is safe and informed before executing. Returns relevant past decisions, guardrail results, calibration context, and optionally records the decision. Call this BEFORE making any significant choice.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "description": { "type": "string", "description": "What you plan to do" },
      "category": { "type": "string", "enum": ["architecture", "process", "integration", "tooling", "security"] },
      "stakes": { "type": "string", "enum": ["low", "medium", "high", "critical"] },
      "confidence": { "type": "number", "minimum": 0, "maximum": 1 },
      "reasons": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "type": { "type": "string" },
            "text": { "type": "string" }
          }
        }
      },
      "tags": { "type": "array", "items": { "type": "string" } },
      "pattern": { "type": "string", "description": "Abstract pattern this decision represents" },
      "auto_record": { "type": "boolean", "default": true }
    },
    "required": ["description", "category", "stakes", "confidence"]
  }
}
```

## Design Principles

- **One call, full context.** Reduce friction to zero - if the agent only makes one CSTP call, this is the one.
- **Opinionated defaults.** `auto_record: true`, `query_limit: 5`, `include_patterns: true`. Works out of the box.
- **Fail open or fail closed.** Configurable per deployment. Default: warn on guardrail violations but allow (fail open). Production: block on violations (fail closed).
- **Idempotent query, non-idempotent record.** If `auto_record: false`, the call is pure query (safe to retry). If `auto_record: true`, it creates a decision (call once).

## Phases

1. **P1:** Core endpoint combining query + guardrails + record
2. **P2:** Calibration context injection + pattern extraction
3. **P3:** MCP tool exposure + Claude Desktop/Code integration
4. **P4:** Configurable fail-open/fail-closed modes

## Integration Points

- F002 (Query): Reuses hybrid query internally
- F003 (Guardrails): Reuses guardrail evaluation
- F007 (Record): Reuses decision recording
- F009 (Calibration): Category-specific calibration context
- F027 (Quality): Auto-enforces tags + pattern requirement
- F045 (Graph): Future - include graph-neighbor decisions in results
- F047 (Session Context): preAction is the per-decision call; F047 is the per-session call
