# F042: Decision Dependency Graph

**Status:** Proposed
**Priority:** Medium
**Inspired by:** Beads (steveyegge/beads) - graph links with relates_to, duplicates, supersedes, blocks

## Problem

CSTP's `related_to` field is flat - it lists similar decisions found during query but doesn't capture semantic relationships. There's no way to express:

- "Decision B was blocked until Decision A resolved"
- "Decision C supersedes Decision B (we changed our mind)"
- "Decision D duplicates Decision E (same choice, different context)"

This limits the decision history to a searchable list rather than a navigable knowledge graph.

## Solution

Add typed dependency links between decisions, enabling graph traversal and relationship-aware queries.

### Link Types

| Type | Meaning | Example |
|------|---------|---------|
| `blocks` | A must resolve before B can proceed | "Choose DB" blocks "Design schema" |
| `supersedes` | B replaces A (A is now obsolete) | "Use HTMX" supersedes "Use React" |
| `duplicates` | Same decision in different context | Two agents independently chose the same approach |
| `relates_to` | Loosely connected (existing) | Topically similar decisions |
| `contradicts` | B conflicts with A | Opposing approaches in different subsystems |
| `refines` | B narrows/improves A | "Use PostgreSQL" refines "Use SQL database" |

### Data Model

```python
class DecisionLink:
    source_id: str
    target_id: str
    link_type: LinkType
    created_at: datetime
    created_by: str        # Agent that created the link
    context: str | None    # Why this link exists
```

### API

```
cstp.linkDecisions    - Create typed link between decisions
cstp.getGraph         - Get decision graph (optional: depth, link_types)
cstp.findBlocked      - Decisions blocked by unresolved dependencies
cstp.getChain         - Follow supersedes chain to current decision
cstp.findContradictions - Detect conflicting active decisions
```

### Graph Queries

```
# "What's the current active decision for database choice?"
cstp.getChain("dec-001")  # Follows supersedes links to latest

# "Are there any contradictions in my architecture decisions?"
cstp.findContradictions(category="architecture")

# "What decisions are blocked right now?"
cstp.findBlocked(status="pending")
```

## Phases

1. **P1:** Link CRUD + basic graph storage
2. **P2:** Supersedes chains + contradiction detection
3. **P3:** Blocking/unblocking with notifications
4. **P4:** Graph visualization in dashboard (F011)

## Integration Points

- F024 (Bridge Definitions): Links informed by bridge similarity
- F027 (Decision Quality): Link density as quality signal
- F030 (Circuit Breakers): Contradiction count as breaker trigger
- F040 (Task Graph): Tasks inherit decision dependencies
