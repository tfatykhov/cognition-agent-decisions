# F002: cstp.queryDecisions Method

| Field | Value |
|-------|-------|
| Feature ID | F002 |
| Status | Implemented |
| Priority | P1 |
| Depends On | F001 (Server Infrastructure) |
| Blocks | None |
| Decision | a42a3514 |

---

## Summary

Implement `cstp.queryDecisions` method to enable remote agents to search this agent's decision history via semantic search.

## Goals

1. JSON-RPC method handler for `cstp.queryDecisions`
2. Wrap existing `query.py` functionality
3. Filter by category, confidence, date range
4. Return decision metadata (not raw content)
5. Rate limiting per agent

## Non-Goals

- Full decision content exposure
- Write access to decisions
- Cross-agent federated search (future)

---

## Specification

### Method Signature

**Method:** `cstp.queryDecisions`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.queryDecisions",
  "id": "req-001",
  "params": {
    "query": "database migration strategy",
    "filters": {
      "category": "architecture",
      "minConfidence": 0.7,
      "maxConfidence": 1.0,
      "dateAfter": "2026-01-01T00:00:00Z",
      "dateBefore": "2026-12-31T23:59:59Z",
      "stakes": ["medium", "high"],
      "status": ["decided", "reviewed"]
    },
    "limit": 10,
    "includeReasons": false
  }
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| query | string | ✅ | - | Semantic search query |
| filters.category | string | ❌ | null | Filter by category |
| filters.minConfidence | float | ❌ | 0.0 | Minimum confidence |
| filters.maxConfidence | float | ❌ | 1.0 | Maximum confidence |
| filters.dateAfter | datetime | ❌ | null | After this date |
| filters.dateBefore | datetime | ❌ | null | Before this date |
| filters.stakes | string[] | ❌ | null | Filter by stakes level |
| filters.status | string[] | ❌ | null | Filter by status |
| limit | int | ❌ | 10 | Max results (1-50) |
| includeReasons | bool | ❌ | false | Include reason summary |

### Response

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "decisions": [
      {
        "id": "dec-456",
        "title": "Use blue-green deployment for DB migration",
        "category": "architecture",
        "confidence": 0.9,
        "stakes": "high",
        "status": "reviewed",
        "outcome": "success",
        "date": "2026-01-20T14:00:00Z",
        "distance": 0.23,
        "reasons": ["pattern", "analysis"]
      }
    ],
    "total": 1,
    "query": "database migration strategy",
    "queryTimeMs": 45,
    "agent": "emerson"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| decisions | array | Matching decisions |
| decisions[].id | string | Decision ID (short hash) |
| decisions[].title | string | Decision summary |
| decisions[].category | string | Category |
| decisions[].confidence | float | Confidence 0.0-1.0 |
| decisions[].stakes | string | Stakes level |
| decisions[].status | string | Current status |
| decisions[].outcome | string | Outcome if reviewed |
| decisions[].date | datetime | Decision timestamp |
| decisions[].distance | float | Semantic distance (lower = closer) |
| decisions[].reasons | string[] | Reason types used (if includeReasons) |
| total | int | Total matches returned |
| query | string | Original query |
| queryTimeMs | int | Query execution time |
| agent | string | Responding agent ID |

### Errors

| Code | Message | When |
|------|---------|------|
| -32602 | InvalidParams | Missing query, invalid filters |
| -32003 | QueryFailed | ChromaDB unavailable |
| -32002 | RateLimited | Too many requests |

---

## Implementation

### Handler

```python
# a2a/cstp/dispatcher.py

from .models import QueryDecisionsRequest, QueryDecisionsResponse
from .query_service import query_decisions

async def _handle_query_decisions(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.queryDecisions method."""
    
    # Parse request
    request = QueryDecisionsRequest.from_params(params)
    
    # Execute query
    results = await query_decisions(
        query=request.query,
        n_results=request.limit,
        category=request.filters.category,
        # ...
    )
    
    # Map to response format
    # ...
```

### Models

```python
# a2a/cstp/models.py

from dataclasses import dataclass
from typing import Any

@dataclass(slots=True)
class QueryFilters:
    # ...

@dataclass(slots=True)
class QueryDecisionsRequest:
    # ...
```

---

## Implementation Tasks

- [ ] Create `QueryDecisionsRequest` Pydantic model
- [ ] Create `QueryDecisionsResponse` Pydantic model
- [ ] Implement `handle_query_decisions` handler
- [ ] Add rate limiting per agent
- [ ] Register method in JSON-RPC dispatcher
- [ ] Write unit tests
- [ ] Write integration test with ChromaDB

---

## Acceptance Criteria

1. `cstp.queryDecisions` returns matching decisions
2. Filters correctly narrow results
3. Rate limiting blocks excessive requests
4. Invalid params return -32602 error
5. ChromaDB failure returns -32003 error
6. Response time < 500ms for typical queries
