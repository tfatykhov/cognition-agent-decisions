# F050: SQLite Storage Layer

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

Add SQLite as the structured storage layer alongside ChromaDB (which remains for semantic/embedding search).

### Architecture

```
Write path:  API → SQLite (primary) → ChromaDB (embeddings) → YAML (export/backup)
Read path:   Dashboard/list queries → SQLite
             Semantic search → ChromaDB
             Human inspection → YAML export
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

### P1: Core SQLite Layer
- [ ] SQLite database manager (connection pooling, migrations)
- [ ] Schema creation and migration support
- [ ] `DecisionStore` class with CRUD operations
- [ ] Write-through: all `recordDecision` writes to SQLite + ChromaDB
- [ ] `listDecisions` RPC endpoint
- [ ] `getStats` RPC endpoint
- [ ] YAML migration script (import existing YAMLs into SQLite)
- [ ] FTS5 keyword search

### P2: Dashboard Integration
- [ ] Update `cstp_client.py` to use `listDecisions` for browsing
- [ ] Working search (keyword via FTS5)
- [ ] Date range picker
- [ ] Agent filter dropdown
- [ ] Tag filter
- [ ] Server-side sort (all columns)
- [ ] Proper pagination with total count
- [ ] Stats overview cards on main page

### P3: YAML Deprecation Path
- [ ] YAML export command (for human review / git history)
- [ ] Remove YAML as primary write path
- [ ] Backup/restore from SQLite dump
- [ ] Keep ChromaDB sync for semantic search

## Migration Strategy

1. Add SQLite alongside existing YAML storage (dual-write)
2. Run migration script to import all existing YAMLs
3. Dashboard switches to SQLite reads
4. Verify data consistency
5. Eventually deprecate YAML as primary store

## Configuration

```bash
# Environment variables
CSTP_DB_PATH=data/decisions.db     # SQLite database path (default)
CSTP_STORAGE=sqlite                # Storage backend: sqlite | yaml (legacy)
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
