# F044: Agent Work Discovery

**Status:** Proposed
**Priority:** High
**Inspired by:** Beads (steveyegge/beads) - `bd ready` command that surfaces tasks with no open blockers

## Problem

CSTP is passive - agents record and query decisions but must know what to ask. There's no mechanism to surface:

- Decisions needing outcome reviews
- Categories with degrading calibration
- Patterns with recurring failures
- Unresolved contradictions
- Stale decisions that need re-evaluation

Agents miss valuable cognitive maintenance work because nothing prompts them.

## Solution

Add a `cstp.ready` endpoint that returns prioritized cognitive actions, turning CSTP from a passive record into an active work queue.

### Ready Queue

```bash
cstp.py ready
```

```json
{
  "actions": [
    {
      "type": "review_outcome",
      "priority": "high",
      "decision_id": "dec-a3f8",
      "reason": "Decision is 14 days old with no outcome review",
      "suggestion": "Check if the approach worked"
    },
    {
      "type": "calibration_drift",
      "priority": "medium",
      "category": "tooling",
      "reason": "Brier score degraded 40% in last 7 days (0.02 -> 0.028)",
      "suggestion": "Review recent tooling decisions for overconfidence"
    },
    {
      "type": "contradiction",
      "priority": "medium",
      "decisions": ["dec-b1c2", "dec-d3e4"],
      "reason": "Active decisions with conflicting approaches",
      "suggestion": "Resolve: one should supersede the other"
    },
    {
      "type": "stale_pattern",
      "priority": "low",
      "pattern": "Override system defaults when they don't match workload",
      "reason": "Pattern referenced by 5 decisions, none reviewed in 30 days",
      "suggestion": "Validate pattern still holds"
    }
  ]
}
```

### Action Types

| Type | Trigger | Priority Logic |
|------|---------|---------------|
| `review_outcome` | Decision age > review_period, no outcome | Higher stakes = higher priority |
| `calibration_drift` | Category Brier score degraded >20% | Based on drift magnitude |
| `contradiction` | Active decisions with conflicting patterns | Always medium+ |
| `stale_pattern` | Pattern not validated in 30+ days | Based on pattern frequency |
| `low_confidence_cluster` | 3+ recent decisions in same area with conf < 0.6 | Signals knowledge gap |
| `success_streak` | 10+ successes in category | Prompt: raise default confidence? |

### Agent Integration

```markdown
# In HEARTBEAT.md or agent instructions:
During quiet periods, run `cstp.py ready` and address top items.
```

### Filtering

```bash
# Only high priority
cstp.py ready --min-priority high

# Specific types
cstp.py ready --type review_outcome,calibration_drift

# For specific agent
cstp.py ready --agent code-reviewer
```

## Phases

1. **P1:** Outcome review reminders (overdue decisions)
2. **P2:** Calibration drift detection (extends existing checkDrift)
3. **P3:** Contradiction and staleness detection
4. **P4:** Configurable priority policies per agent

## Integration Points

- F009 (Calibration): Drift detection feeds ready queue
- F030 (Circuit Breakers): Tripped breakers surface as high-priority actions
- F040 (Task Graph): Blocked tasks appear in ready queue
- F042 (Dependencies): Contradictions detected via dependency graph
- F041 (Compaction): Compaction candidates surfaced as low-priority maintenance
