# Related Decisions

> **Feature:** F025 | **Status:** Shipped in v0.10.0

Related decisions are lightweight graph edges that automatically link each new decision to its predecessors - the past decisions that were consulted during the decision-making process.

## How It Works

When you query similar decisions (Step 1 of the protocol), the server remembers those results. When you record a decision (Step 3), it automatically links the query results as `related_to`.

```
Query "retry patterns" → finds decisions A, B, C
Record new decision D  → D.related_to = [A, B, C] with distances
```

## What Gets Stored

Each related decision includes:

```yaml
related_to:
  - id: abc123
    summary: "Used circuit breaker for payment API"
    distance: 0.265
  - id: def456
    summary: "Added retry with backoff to order service"
    distance: 0.324
```

- **id** - the related decision's identifier
- **summary** - first 100 chars of the decision text
- **distance** - semantic distance (lower = more similar)

## Why Not a Graph Database?

We considered adding a full graph database (Neo4j, etc.) but deferred it:

- ~50 decisions is too few for graph traversal to outperform semantic search
- Related-to edges give us 90% of the graph benefit with zero infrastructure
- Revisit at 200+ decisions if traversal patterns emerge

## Deduplication

If the same decision appears in multiple pre-decision queries, only the closest distance is kept. This prevents inflated link counts.
