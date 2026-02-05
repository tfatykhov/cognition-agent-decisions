# F007: Record Decision Endpoint

| Field | Value |
|-------|-------|
| Feature ID | F007 |
| Status | Implemented |
| Priority | P1 |
| Depends On | F001 (Server Infrastructure) |
| Blocks | None |
| Decision | fddb416c |

---

## Summary

Add `cstp.recordDecision` JSON-RPC method to allow remote agents to create and store decisions via the CSTP API, with automatic indexing to ChromaDB for semantic search.

## Goals

1. Create decisions via API (no CLI required)
2. Auto-generate decision ID and timestamps
3. Auto-index to ChromaDB for immediate searchability
4. Support full decision schema (reasons, K-lines, pre-decision protocol)
5. Return decision ID and file path

## Non-Goals

- Decision updates (future F008)
- Decision deletion (future F009)
- Batch recording (future optimization)

---

## API Specification

### Method

`cstp.recordDecision`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.recordDecision",
  "params": {
    "decision": "Use PostgreSQL for agent memory storage",
    "confidence": 0.85,
    "category": "architecture",
    "stakes": "high",
    "context": "Choosing database for long-term agent memory",
    "reasons": [
      {"type": "analysis", "text": "ACID compliance needed for consistency", "strength": 0.9},
      {"type": "pattern", "text": "Similar to prior successful database choice", "strength": 0.7}
    ],
    "kpiIndicators": ["latency", "consistency"],
    "mentalState": "deliberate",
    "reviewIn": "30d",
    "tags": ["database", "infrastructure"],
    "preDecision": {
      "queryRun": true,
      "similarFound": 2,
      "guardrailsChecked": true,
      "guardrailsPassed": true
    }
  },
  "id": 1
}
```

### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `decision` | string | ✅ | The decision statement |
| `confidence` | float | ✅ | Confidence level (0.0-1.0) |
| `category` | string | ✅ | Category: architecture, process, integration, tooling, security |
| `stakes` | string | ❌ | Stakes level: low, medium, high, critical (default: medium) |
| `context` | string | ❌ | Background/situation being decided |
| `reasons` | array | ❌ | Array of reason objects |
| `reasons[].type` | string | ✅ | Reason type: authority, analogy, analysis, pattern, intuition |
| `reasons[].text` | string | ✅ | Reason explanation |
| `reasons[].strength` | float | ❌ | Reason strength (0.0-1.0, default: 0.8) |
| `kpiIndicators` | array | ❌ | KPIs affected by this decision |
| `mentalState` | string | ❌ | State: deliberate, reactive, exploratory, habitual, pressured |
| `reviewIn` | string | ❌ | Review reminder: 7d, 2w, 1m, etc. |
| `tags` | array | ❌ | Additional tags for categorization |
| `preDecision` | object | ❌ | Pre-decision protocol tracking |
| `preDecision.queryRun` | bool | ❌ | Whether similar decisions were queried |
| `preDecision.similarFound` | int | ❌ | Number of similar decisions found |
| `preDecision.guardrailsChecked` | bool | ❌ | Whether guardrails were checked |
| `preDecision.guardrailsPassed` | bool | ❌ | Whether guardrails passed |

### Response (Success)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "id": "fddb416c",
    "path": "decisions/2026/02/2026-02-05-decision-fddb416c.yaml",
    "indexed": true,
    "timestamp": "2026-02-05T00:45:00Z"
  },
  "id": 1
}
```

### Response (Error)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": {
      "field": "confidence",
      "error": "Must be between 0.0 and 1.0"
    }
  },
  "id": 1
}
```

---

## Implementation Plan

### Phase 1: Core Service (~2h)

#### 1.1 Create decision_service.py

```
a2a/cstp/decision_service.py
```

**Functions:**
- `generate_decision_id()` — UUID-based short ID
- `create_decision_yaml(params)` — Build YAML content
- `write_decision_file(id, yaml)` — Write to decisions/YYYY/MM/
- `index_decision(path)` — Add to ChromaDB
- `record_decision(params)` — Main orchestrator

#### 1.2 Add models

```python
# a2a/cstp/models.py

@dataclass
class Reason:
    type: str  # authority, analogy, analysis, pattern, intuition
    text: str
    strength: float = 0.8

@dataclass
class PreDecisionProtocol:
    query_run: bool = False
    similar_found: int = 0
    guardrails_checked: bool = False
    guardrails_passed: bool = False

@dataclass
class RecordDecisionRequest:
    decision: str
    confidence: float
    category: str
    stakes: str = "medium"
    context: str | None = None
    reasons: list[Reason] = field(default_factory=list)
    kpi_indicators: list[str] = field(default_factory=list)
    mental_state: str | None = None
    review_in: str | None = None
    tags: list[str] = field(default_factory=list)
    pre_decision: PreDecisionProtocol | None = None

@dataclass
class RecordDecisionResponse:
    success: bool
    id: str
    path: str
    indexed: bool
    timestamp: str
```

### Phase 2: Dispatcher Integration (~1h)

#### 2.1 Update dispatcher.py

```python
async def _handle_record_decision(self, params: dict) -> dict:
    request = RecordDecisionRequest.from_dict(params)
    result = await record_decision(request)
    return result.to_dict()
```

#### 2.2 Register method

```python
self._methods["cstp.recordDecision"] = self._handle_record_decision
```

### Phase 3: Configuration (~30m)

#### 3.1 Environment variables

```bash
# Path where decisions are stored
DECISIONS_PATH=/app/decisions

# ChromaDB collection for indexing
CHROMA_COLLECTION=decisions_gemini
```

#### 3.2 Update config.py

```python
@dataclass
class DecisionsConfig:
    path: Path = Path("decisions")
    chroma_collection: str = "decisions_gemini"
```

### Phase 4: Tests (~1h)

#### 4.1 Unit tests

```
tests/test_decision_service.py
tests/test_f007_record_decision.py
```

**Test cases:**
- Valid decision creation
- Missing required fields
- Invalid confidence range
- Invalid category
- Reason validation
- File path generation
- YAML format verification

#### 4.2 Integration tests

- End-to-end API call
- ChromaDB indexing verification
- Concurrent recording

### Phase 5: Documentation (~30m)

- Update README with new endpoint
- Update docs/CSTP-v0.7.0-DESIGN.md
- Add examples to docs/DOCKER.md

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `a2a/cstp/decision_service.py` | Create | Core recording logic |
| `a2a/cstp/models.py` | Modify | Add request/response models |
| `a2a/cstp/dispatcher.py` | Modify | Register new method |
| `a2a/config.py` | Modify | Add decisions config |
| `tests/test_decision_service.py` | Create | Unit tests |
| `tests/test_f007_record_decision.py` | Create | Integration tests |
| `README.md` | Modify | Document new endpoint |

---

## Security Considerations

1. **Input validation** — Sanitize all string inputs
2. **Path traversal** — Ensure decision paths stay within decisions/
3. **Rate limiting** — Consider adding rate limits (future)
4. **Agent attribution** — Record which agent created the decision

---

## Error Codes

| Code | Message | Cause |
|------|---------|-------|
| -32602 | Invalid params | Missing/invalid field |
| -32603 | Internal error | File write or indexing failed |
| -32001 | Storage error | Cannot write to decisions path |
| -32002 | Indexing error | ChromaDB indexing failed |

---

## Acceptance Criteria

1. ✅ `cstp.recordDecision` creates valid YAML file
2. ✅ Decision immediately searchable via `cstp.queryDecisions`
3. ✅ All required fields validated
4. ✅ Optional fields handled correctly
5. ✅ Error responses include helpful details
6. ✅ Agent ID from auth recorded in decision
7. ✅ File path follows YYYY/MM/ structure

---

## Estimated Effort

| Phase | Time |
|-------|------|
| Core Service | 2h |
| Dispatcher Integration | 1h |
| Configuration | 30m |
| Tests | 1h |
| Documentation | 30m |
| **Total** | **~5h** |

---

## Future Enhancements

- **F008**: updateDecision — Add outcome, review decision
- **F009**: deleteDecision — Remove decision (with audit)
- **F010**: listDecisions — Paginated listing with filters
- Batch recording for bulk imports
- Webhooks for decision events
