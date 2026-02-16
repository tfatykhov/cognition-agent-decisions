# F050: Structured Storage Layer

**Status:** Proposed
**Priority:** P1
**Category:** Infrastructure
**Related:** F048 (Multi-Vector-DB), F049 (Dashboard)

## Problem

Current storage uses one YAML file per decision on disk. This works at ~200 decisions but creates problems:

1. **No efficient querying** - every list/filter/sort operation loads all YAMLs into memory
2. **No server-side pagination** - dashboard fetches 200 results and slices client-side
3. **No date range queries** - no index on timestamps
4. **No aggregation** - stats require full scan every time
5. **No keyword search** - only semantic search via ChromaDB
6. **Scaling ceiling** - disk reads grow linearly with decision count

## Solution

Add an abstract `DecisionStore` interface (same pattern as F048's `VectorStore`) with SQLite as the default backend. ChromaDB remains for semantic/embedding search.

### Architecture

```
Write path:  API → DecisionStore (abstract) → ChromaDB (embeddings)
Read path:   Dashboard/list queries → DecisionStore
             Semantic search → ChromaDB

Backends:    SQLite (default) | PostgreSQL (future) | YAML (legacy)
```

### Abstract Interface

```python
class DecisionStore(ABC):
    """Abstract structured storage for decisions.

    All storage backends (SQLite, PostgreSQL, YAML-legacy)
    implement this interface. Services interact only through
    these methods.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection, run migrations."""
        ...

    @abstractmethod
    async def save(self, decision: DecisionRecord) -> bool:
        """Insert or update a decision."""
        ...

    @abstractmethod
    async def get(self, decision_id: str) -> DecisionRecord | None:
        """Get a single decision by ID."""
        ...

    @abstractmethod
    async def delete(self, decision_id: str) -> bool:
        """Delete a decision by ID."""
        ...

    @abstractmethod
    async def list(self, query: ListQuery) -> ListResult:
        """List decisions with filters, sort, pagination.

        Supports: category, stakes, status, agent, tags,
        date range, keyword search, sort, offset/limit.
        """
        ...

    @abstractmethod
    async def stats(self, query: StatsQuery) -> StatsResult:
        """Aggregate statistics (counts by category, stakes,
        agent, day, tags)."""
        ...

    @abstractmethod
    async def update_outcome(
        self, decision_id: str, outcome: str, result: str
    ) -> bool:
        """Record review outcome for a decision."""
        ...

    @abstractmethod
    async def count(self, **filters) -> int:
        """Count decisions matching filters."""
        ...
```

### Factory Pattern

```python
# a2a/cstp/storage/factory.py
def create_decision_store() -> DecisionStore:
    backend = os.getenv("CSTP_STORAGE", "sqlite")
    match backend:
        case "sqlite":
            from .sqlite_store import SQLiteDecisionStore
            return SQLiteDecisionStore()
        case "yaml":
            from .yaml_store import YAMLDecisionStore
            return YAMLDecisionStore()
        case "postgresql":
            from .pg_store import PostgreSQLDecisionStore
            return PostgreSQLDecisionStore()
        case _:
            raise ValueError(f"Unknown storage backend: {backend}")
```

### Schema

```sql
CREATE TABLE decisions (
    id TEXT PRIMARY KEY,           -- 8-char hex
    decision TEXT NOT NULL,        -- full decision text
    confidence REAL NOT NULL,
    category TEXT NOT NULL,
    stakes TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    context TEXT,
    recorded_by TEXT,              -- agent_id
    project TEXT,
    feature TEXT,
    pr INTEGER,
    pattern TEXT,
    outcome TEXT,                  -- success/failure/partial/abandoned
    outcome_result TEXT,           -- outcome description
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

CREATE TABLE decision_tags (
    decision_id TEXT NOT NULL REFERENCES decisions(id),
    tag TEXT NOT NULL,
    PRIMARY KEY (decision_id, tag)
);

CREATE TABLE decision_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL REFERENCES decisions(id),
    type TEXT NOT NULL,            -- analysis, pattern, authority, etc.
    text TEXT NOT NULL,
    strength REAL DEFAULT 0.8
);

CREATE TABLE decision_bridge (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(id),
    structure TEXT,
    function TEXT,
    tolerance TEXT,
    enforcement TEXT,
    prevention TEXT
);

CREATE TABLE decision_deliberation (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(id),
    inputs_json TEXT,              -- JSON array of deliberation inputs
    steps_json TEXT,               -- JSON array of deliberation steps
    total_duration_ms INTEGER
);

-- Indexes for common queries
CREATE INDEX idx_decisions_created_at ON decisions(created_at);
CREATE INDEX idx_decisions_category ON decisions(category);
CREATE INDEX idx_decisions_status ON decisions(status);
CREATE INDEX idx_decisions_stakes ON decisions(stakes);
CREATE INDEX idx_decisions_recorded_by ON decisions(recorded_by);
CREATE INDEX idx_decisions_project ON decisions(project);
CREATE INDEX idx_decision_tags_tag ON decision_tags(tag);

-- FTS5 for keyword search
CREATE VIRTUAL TABLE decisions_fts USING fts5(
    id UNINDEXED,
    decision,
    context,
    pattern,
    content=decisions,
    content_rowid=rowid
);
```

### New API Endpoints

#### `cstp.listDecisions`

Server-side filtered, sorted, paginated listing for dashboard use.

```json
{
    "method": "cstp.listDecisions",
    "params": {
        "limit": 20,
        "offset": 0,
        "category": "architecture",
        "stakes": "high",
        "status": "pending",
        "agent": "emerson",
        "tags": ["security"],
        "project": "owner/repo",
        "dateFrom": "2026-02-01",
        "dateTo": "2026-02-16",
        "search": "keyword search",
        "sort": "created_at",
        "order": "desc"
    }
}
```

Response:
```json
{
    "decisions": [...],
    "total": 193,
    "limit": 20,
    "offset": 0
}
```

#### `cstp.getStats`

Aggregated statistics for dashboard overview.

```json
{
    "method": "cstp.getStats",
    "params": {
        "dateFrom": "2026-02-01",
        "dateTo": "2026-02-16",
        "project": "owner/repo"
    }
}
```

Response:
```json
{
    "total": 193,
    "byCategory": {"architecture": 45, "process": 80, ...},
    "byStakes": {"low": 50, "medium": 100, "high": 40, "critical": 3},
    "byStatus": {"pending": 108, "reviewed": 85},
    "byAgent": {"emerson": 150, "code-reviewer": 30, ...},
    "byDay": [{"date": "2026-02-16", "count": 12}, ...],
    "topTags": [{"tag": "code-review", "count": 30}, ...],
    "recentActivity": {
        "last24h": 15,
        "last7d": 45,
        "last30d": 120
    }
}
```

## Implementation Plan

### P1: Abstract Interface + SQLite Backend
- [ ] `DecisionStore` ABC in `a2a/cstp/storage/__init__.py`
- [ ] Data classes: `DecisionRecord`, `ListQuery`, `ListResult`, `StatsQuery`, `StatsResult`
- [ ] Factory pattern with `CSTP_STORAGE` env var (default: `sqlite`)
- [ ] `SQLiteDecisionStore` implementation (WAL mode, connection pooling)
- [ ] Schema creation and migration support
- [ ] FTS5 keyword search
- [ ] `YAMLDecisionStore` wrapper (legacy, wraps existing `load_all_decisions`)
- [ ] Wire into `decision_service.py` (replace direct YAML read/write)
- [ ] YAML migration script (import existing YAMLs into SQLite)

### P2: New RPC Endpoints + Dashboard
- [ ] `cstp.listDecisions` RPC endpoint (delegates to `DecisionStore.list()`)
- [ ] `cstp.getStats` RPC endpoint (delegates to `DecisionStore.stats()`)
- [ ] MCP tool wrappers for both endpoints
- [ ] Update `cstp_client.py` to use `listDecisions` for browsing
- [ ] Working search (keyword via FTS5)
- [ ] Date range picker
- [ ] Agent filter dropdown
- [ ] Tag filter
- [ ] Server-side sort (all columns)
- [ ] Proper pagination with total count
- [ ] Stats overview cards on main page

### P3: PostgreSQL Backend + YAML Deprecation
- [ ] `PostgreSQLDecisionStore` implementation (async, pgvector potential)
- [ ] YAML export command (for human review / git history)
- [ ] Remove YAML as primary write path
- [ ] Backup/restore utilities

## Migration Strategy

1. Add SQLite alongside existing YAML storage (dual-write)
2. Run migration script to import all existing YAMLs
3. Dashboard switches to SQLite reads
4. Verify data consistency
5. Eventually deprecate YAML as primary store

## Configuration

```bash
# Environment variables
CSTP_STORAGE=sqlite                # Storage backend: sqlite | yaml | postgresql
CSTP_DB_PATH=data/decisions.db     # SQLite database path (default)
CSTP_PG_URL=postgresql://...       # PostgreSQL connection URL (P3)
```

## Risks

- **Data migration:** Must be lossless - verify all YAML fields map to schema
- **Dual-write complexity:** During transition, both stores must stay in sync
- **SQLite concurrency:** Single-writer limitation - fine for current scale, use WAL mode
- **ChromaDB still needed:** SQLite handles structured queries, ChromaDB handles embeddings

## Success Criteria

- Dashboard search returns results in <100ms
- Date range, category, agent, tag filters all work server-side
- Pagination works with accurate total counts
- Stats endpoint powers overview dashboard
- Zero data loss from YAML migration
