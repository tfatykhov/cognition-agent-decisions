# F053: Query Deduplication Cache

**Status:** Proposed
**Priority:** P2
**Category:** Performance
**Related:** F046 (Pre-Action), F047 (Session Context), F048 (Multi-Vector-DB)

## Problem

Agents frequently issue near-identical queries within short time windows:

1. **`pre_action` → `get_session_context`** - These often fire within seconds with overlapping semantic content. Both hit ChromaDB for embedding + search.
2. **Multiple `record_thought` → `get_session_context`** - During a single decision, an agent may request context multiple times as it captures reasoning steps.
3. **Parallel sub-agents** - Multiple agents querying about the same topic simultaneously (e.g., CodeReviewer and DocsAgent both querying a PR's context).

Each ChromaDB query involves:
- Text → embedding computation (~50-100ms)
- Vector similarity search (~20-50ms)
- Result enrichment from SQLite (~5-10ms)

With `pre_action` averaging 1.8s (mostly due to embedding + search), deduplication could cut 30-50% of that for repeated queries.

## Solution

A lightweight in-memory cache layer that detects semantically similar queries within a configurable time window and returns cached results instead of re-computing.

### Architecture

```
Agent → MCP/JSON-RPC → Query Router
                          │
                          ├── Cache HIT → Return cached results
                          │
                          └── Cache MISS → ChromaDB → Cache → Return
```

### Cache Key Strategy

Two-tier cache keying:

**Tier 1: Exact match (fast)**
- Hash of normalized query text (lowercase, stripped, sorted params)
- O(1) lookup
- Catches identical `get_session_context` calls

**Tier 2: Semantic similarity (slower, optional)**
- Compare query embedding cosine similarity against cached query embeddings
- Threshold: 0.95 similarity = cache hit
- Catches `pre_action("deploy config change")` followed by `get_session_context("deploying config changes")`
- Only computed if Tier 1 misses

### Cache Entry Structure

```python
@dataclass
class CacheEntry:
    query_text: str
    query_embedding: list[float]   # Reuse for Tier 2 matching
    params_hash: str               # Filter params (category, tags, etc.)
    results: list[dict]            # Cached response
    created_at: float              # Unix timestamp
    hit_count: int                 # For metrics
    agent_id: str | None           # Scope to agent if needed
```

### Configuration

```env
# Enable/disable cache (default: enabled)
CSTP_QUERY_CACHE=true

# TTL in seconds (default: 30)
CSTP_QUERY_CACHE_TTL=30

# Max entries (default: 100, LRU eviction)
CSTP_QUERY_CACHE_MAX=100

# Semantic similarity threshold for Tier 2 (default: 0.95)
CSTP_QUERY_CACHE_SIM_THRESHOLD=0.95

# Enable Tier 2 semantic dedup (default: false, requires extra embedding comparison)
CSTP_QUERY_CACHE_SEMANTIC=false
```

### What Gets Cached

| Method | Cached? | Notes |
|--------|---------|-------|
| `queryDecisions` | ✅ | Primary target. Most expensive call. |
| `getCalibration` | ✅ | Expensive aggregation, changes infrequently. |
| `get_session_context` | ✅ | Wraps `queryDecisions` + `getCalibration`. |
| `pre_action` | ✅ (query portion) | Cache the similar-decisions lookup, not the guardrail check. |
| `getDecision` | ✅ | Single-decision lookup, cheap but frequently repeated. |
| `listDecisions` | ✅ | With same filters = same results within TTL. |
| `recordDecision` | ❌ | Write operation, never cached. |
| `update_decision` | ❌ | Write operation. **Invalidates** related cache entries. |
| `reviewDecision` | ❌ | Write operation. **Invalidates** calibration cache. |

### Cache Invalidation

Write operations invalidate related cache entries:

- `recordDecision` → Invalidate all `queryDecisions` and `listDecisions` entries
- `update_decision` → Invalidate entries containing the updated decision ID
- `reviewDecision` → Invalidate `getCalibration` entries
- **TTL expiry** → Entries auto-expire after `CSTP_QUERY_CACHE_TTL` seconds

### Metrics

Expose cache stats via `cstp.getMetrics` (F052):

```json
{
  "cache": {
    "entries": 23,
    "hits": 145,
    "misses": 67,
    "hit_rate": 0.684,
    "evictions": 12,
    "invalidations": 8,
    "avg_saved_ms": 340
  }
}
```

## Implementation

### Phase 1: Exact Match Cache (P1)
- In-memory dict with TTL eviction
- Hash-based key from normalized query + params
- Wire into `query_service.py` as decorator/wrapper
- Thread-safe (threading.Lock, same pattern as deliberation tracker)
- ~100 lines

### Phase 2: Write Invalidation (P1)
- Hook into `recordDecision`, `update_decision`, `reviewDecision`
- Selective invalidation (not full flush)
- ~50 lines

### Phase 3: Semantic Dedup (P2)
- Store query embeddings alongside results
- Cosine similarity comparison on Tier 1 miss
- Configurable threshold
- ~80 lines

### Phase 4: Metrics (P2)
- Hit/miss counters
- Average time saved
- Expose via `cstp.getMetrics` and `/metrics`

## Performance Estimates

Based on current benchmarks (324 decisions):

| Scenario | Without Cache | With Cache (hit) | Savings |
|----------|--------------|-------------------|---------|
| `queryDecisions` | 370ms | 1ms | 99.7% |
| `getCalibration` | 60ms | 1ms | 98.3% |
| `pre_action` (full) | 1,800ms | ~900ms | 50% |
| `get_session_context` | ~400ms | 1ms | 99.7% |

Estimated hit rate for typical agent workflow: 40-60% (based on observed query patterns).

## Success Criteria

- Cache hit rate > 40% in typical agent workflow
- Zero correctness issues (stale results never served past TTL)
- `pre_action` P95 latency drops by 30%+
- Thread-safe under concurrent multi-agent load
- Cache adds < 1MB memory overhead at 100 entries

## Risks

- **Stale results** - Agent records a decision, then immediately queries and gets old results. Mitigate: write invalidation (Phase 2) is P1, not P2.
- **Memory growth** - Unbounded cache could grow. Mitigate: LRU eviction + max entries cap.
- **Semantic threshold tuning** - Too low = false hits, too high = no benefit. Mitigate: start with exact-match only, add semantic as opt-in.
- **Multi-process** - Cache is per-process. If running multiple workers, each has its own cache. Mitigate: acceptable for single-server deployment; Redis adapter for multi-worker (future).
