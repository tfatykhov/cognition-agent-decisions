# F041: Memory Compaction

**Status:** Proposed
**Priority:** High
**Inspired by:** Beads (steveyegge/beads) - semantic "memory decay" that summarizes old closed tasks

## Problem

As decision count grows (currently 182+), loading full decision history into agent context becomes expensive and noisy. Agents waste context window on resolved decisions that could be summarized. There's no mechanism to distinguish between "active knowledge" and "historical record."

## Solution

Implement semantic compaction that progressively summarizes old, resolved decisions while preserving their calibration value and key learnings.

### Compaction Levels

| Level | Age | Content |
|-------|-----|---------|
| **Full** | < 7 days | Complete decision with all reasoning, traces, context |
| **Summary** | 7-30 days | Decision text, outcome, key pattern, confidence vs actual |
| **Digest** | 30-90 days | One-line summary grouped by category |
| **Wisdom** | 90+ days | Statistical aggregates + extracted principles |

### Compaction Process

1. **Trigger:** Scheduled (daily) or on-demand via API
2. **Summarize:** LLM-generated summary preserving decision essence
3. **Preserve:** Raw data always kept in storage; compaction only affects query responses
4. **Protect:** Decisions with `preserve: true` or unreviewed outcomes skip compaction

### API

```
cstp.compact          - Run compaction cycle
cstp.getCompacted     - Get decisions at appropriate compaction level
cstp.setPreserve      - Mark decision as never-compact
cstp.getWisdom        - Get category-level distilled principles
```

### Example Output

**Wisdom level (90+ days, architecture category):**
```json
{
  "category": "architecture",
  "decisions": 45,
  "success_rate": 0.93,
  "key_principles": [
    "Manual type resolution beats annotation magic (3 confirmations)",
    "Search-first prevents duplicate work (8 confirmations)",
    "Parallel independent reasons > single strong argument (5 confirmations)"
  ],
  "common_failure_mode": "Skipping pre-decision query (4 failures)"
}
```

## Phases

1. **P1:** Time-based compaction levels in query responses
2. **P2:** LLM-generated summaries for summary/digest levels
3. **P3:** Wisdom extraction - cross-decision principle mining
4. **P4:** Configurable compaction policies per agent/category

## Integration Points

- F002 (Query): Compaction level affects query response size
- F009 (Calibration): Compacted decisions retain calibration data
- F024 (Bridge Definitions): Bridge summaries survive compaction
- F034 (Decomposed Confidence): Confidence components inform compaction priority
