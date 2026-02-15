# F044: Agent Work Discovery

**Status:** Implemented (P1: review_outcome, calibration_drift, stale_pending)
**Priority:** High
**Inspired by:** Beads (steveyegge/beads) - `bd ready` command that surfaces tasks with no open blockers

## Problem

CSTP is passive - agents record and query decisions but must know what to ask. There's no mechanism to surface:

- Decisions needing outcome reviews
- Categories with degrading calibration
- Stale decisions that need re-evaluation

Agents miss valuable cognitive maintenance work because nothing prompts them.

## Solution

The `cstp.ready` endpoint returns prioritized cognitive actions, turning CSTP from a passive record into an active work queue.

### Ready Queue

```json
POST /cstp
{
  "jsonrpc": "2.0",
  "method": "cstp.ready",
  "params": {
    "minPriority": "low",
    "actionTypes": ["review_outcome", "calibration_drift", "stale_pending"],
    "limit": 20,
    "category": "tooling"
  },
  "id": 1
}
```

```json
{
  "actions": [
    {
      "type": "review_outcome",
      "priority": "high",
      "decisionId": "dec-a3f8",
      "category": "tooling",
      "date": "2025-12-01",
      "title": "Use Redis for caching layer",
      "reason": "Decision needs outcome review (due 2025-12-15, 62d overdue)",
      "suggestion": "Use review_outcome to record what happened",
      "detail": "review by 2025-12-15 (62d overdue)"
    },
    {
      "type": "calibration_drift",
      "priority": "medium",
      "category": "tooling",
      "reason": "Tooling decisions: Brier score degraded 33%",
      "suggestion": "Review recent tooling decisions — calibration has degraded from historical baseline"
    },
    {
      "type": "stale_pending",
      "priority": "medium",
      "decisionId": "b1c2d3e4",
      "category": "tooling",
      "date": "2025-10-01",
      "title": "Migrate CI to GitHub Actions",
      "reason": "Decision pending for 137 days with no outcome",
      "suggestion": "Review and record outcome, or mark as abandoned",
      "detail": "pending 137 days"
    }
  ],
  "total": 5,
  "filtered": 2,
  "warnings": []
}
```

### Implemented Action Types

| Type | Trigger | Priority Logic |
|------|---------|---------------|
| `review_outcome` | Decision has `review_by` date in the past, status still pending | `high` for critical/high stakes, `medium` for medium, `low` for low |
| `calibration_drift` | Per-category Brier score degraded >20% from historical baseline | `high` if drift >40%, else `medium` |
| `stale_pending` | Pending decision >30 days old with no `review_by` set | `high` if >60 days, `medium` if >30 days |

### Request Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `minPriority` | `string` | `"low"` | Minimum priority: `low`, `medium`, `high` |
| `actionTypes` | `list[string]` | `[]` (all) | Filter to specific types |
| `limit` | `int` | `20` | Max actions to return (1-50) |
| `category` | `string\|null` | `null` | Filter to specific category |

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `actions` | `list[ReadyAction]` | Prioritized actions (sorted: high priority first, then type order, then oldest date) |
| `total` | `int` | Total actions before priority filtering |
| `filtered` | `int` | Actions removed by `minPriority` filter |
| `warnings` | `list[string]` | Partial failure notices (e.g., drift detection failure). Omitted when empty. |

### Agent Integration

Available as both a JSON-RPC method (`cstp.ready`) and an MCP tool (`ready`). The MCP tool is marked PRIMARY — call during idle periods or after completing tasks.

```markdown
# In agent instructions:
During quiet periods, call the ready tool and address top items.
```

### Filtering

```bash
# Only high priority
cstp.ready { "minPriority": "high" }

# Specific types
cstp.ready { "actionTypes": ["review_outcome", "calibration_drift"] }

# For specific category
cstp.ready { "category": "architecture" }
```

### Session Context Integration

The `cstp.getSessionContext` endpoint also includes a ready queue (limited to `review_outcome` and `stale_pending` types) via the `ready` section. F044 provides the standalone, full-featured endpoint with all action types including calibration drift.

## Implementation

### Key Files

- `a2a/cstp/ready_service.py` — Service with detectors and `get_ready_actions()`
- `a2a/cstp/models.py` — `ReadyRequest`, `ReadyAction`, `ReadyResponse` dataclasses
- `a2a/cstp/dispatcher.py` — `_handle_ready()` handler, `cstp.ready` method
- `a2a/mcp_schemas.py` — `ReadyInput` Pydantic model for MCP tool
- `a2a/mcp_server.py` — `_handle_ready_mcp()` MCP handler
- `tests/test_f044_ready.py` — 49 tests covering models, detectors, service, and dispatcher

### Design Decisions

- **Category filter pushed to detectors**: All three detectors accept `category_filter` for early filtering, avoiding post-filter overhead.
- **agent_id threaded through**: `get_ready_actions()` accepts `agent_id` (keyword-only) for forward compatibility with multi-agent isolation, currently unused.
- **Warnings for partial failure**: If drift detection fails, the response includes a `warnings` list so callers know results are partial.
- **Unknown action_types logged**: Unrecognized values in `actionTypes` are logged as warnings to aid debugging.
- **8-char ID truncation**: Decision IDs are truncated to 8 chars for display brevity, matching the existing session context pattern (lossless for current 8-char hex ID format).

## Future Phases

- **P2:** Contradiction detection (conflicting active patterns)
- **P3:** Staleness detection for patterns (not validated in 30+ days)
- **P4:** Configurable priority policies per agent
- **CLI:** `cstp.py ready` command (not yet implemented)

## Integration Points

- F009 (Calibration): Drift detection feeds ready queue via `drift_service.check_drift()`
- F047 (Session Context): Ready queue embedded in session context response (review + stale only)
- F030 (Circuit Breakers): Future — tripped breakers surface as high-priority actions
- F041 (Compaction): Future — compaction candidates surfaced as low-priority maintenance
