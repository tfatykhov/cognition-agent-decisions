# F008: Review Decision Endpoint

| Field | Value |
|-------|-------|
| Feature ID | F008 |
| Status | Implemented |
| Priority | P1 |
| Depends On | F007 (Record Decision) |
| Blocks | F009 (Calibration) |
| Decision | 30d70c34 |

---

## Summary

Add `cstp.reviewDecision` JSON-RPC method to record outcomes for existing decisions, enabling the feedback loop for calibration and learning.

## Goals

1. Add outcome data to existing decisions
2. Support partial updates (don't require all fields)
3. Trigger re-indexing with outcome metadata
4. Track review timestamps
5. Enable lessons capture

## Non-Goals

- Decision deletion (future)
- Bulk review (future)
- Automatic outcome detection (future enhancement)

---

## API Specification

### Method

`cstp.reviewDecision`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.reviewDecision",
  "params": {
    "id": "fddb416c",
    "outcome": "success",
    "actualResult": "Redis caching reduced latency by 40%",
    "lessons": "Should have considered cluster mode from the start",
    "notes": "Will apply clustering in next iteration"
  },
  "id": 1
}
```

### Parameters

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Decision ID to review |
| `outcome` | string | ✅ | Outcome: `success`, `partial`, `failure`, `abandoned` |
| `actualResult` | string | ❌ | What actually happened |
| `lessons` | string | ❌ | Lessons learned for future |
| `notes` | string | ❌ | Additional notes |
| `affectedKpis` | object | ❌ | KPI impacts: `{"latency": -0.4, "cost": 0.1}` |

### Response (Success)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "id": "fddb416c",
    "path": "decisions/2026/02/2026-02-05-decision-fddb416c.yaml",
    "status": "reviewed",
    "reviewedAt": "2026-02-12T14:30:00Z",
    "reindexed": true
  },
  "id": 1
}
```

### Response (Error - Decision Not Found)

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32004,
    "message": "Decision not found",
    "data": {"id": "invalid123"}
  },
  "id": 1
}
```

---

## Implementation Plan

### Phase 1: Decision Lookup (~1h)

#### 1.1 Add find_decision function

```python
# a2a/cstp/decision_service.py

async def find_decision(decision_id: str, decisions_path: str | None = None) -> tuple[Path, dict] | None:
    """Find a decision by ID.
    
    Searches decisions directory for matching ID.
    Returns (path, data) or None if not found.
    """
    base = Path(decisions_path or DECISIONS_PATH)
    
    # Search pattern: decisions/YYYY/MM/*-decision-{id}.yaml
    for year_dir in base.iterdir():
        if not year_dir.is_dir():
            continue
        for month_dir in year_dir.iterdir():
            if not month_dir.is_dir():
                continue
            for file in month_dir.glob(f"*-decision-{decision_id}.yaml"):
                with open(file) as f:
                    data = yaml.safe_load(f)
                return (file, data)
    
    return None
```

### Phase 2: Review Service (~1.5h)

#### 2.1 Add review models

```python
@dataclass
class ReviewDecisionRequest:
    id: str
    outcome: str  # success, partial, failure, abandoned
    actual_result: str | None = None
    lessons: str | None = None
    notes: str | None = None
    affected_kpis: dict[str, float] | None = None

@dataclass
class ReviewDecisionResponse:
    success: bool
    id: str
    path: str
    status: str
    reviewed_at: str
    reindexed: bool
```

#### 2.2 Add review_decision function

```python
async def review_decision(
    request: ReviewDecisionRequest,
    decisions_path: str | None = None,
) -> ReviewDecisionResponse:
    """Add outcome data to an existing decision."""
    
    # Find decision
    result = await find_decision(request.id, decisions_path)
    if not result:
        raise ValueError(f"Decision not found: {request.id}")
    
    path, data = result
    now = datetime.now(UTC)
    
    # Update decision data
    data["status"] = "reviewed"
    data["outcome"] = request.outcome
    data["reviewed_at"] = now.isoformat()
    
    if request.actual_result:
        data["actual_result"] = request.actual_result
    if request.lessons:
        data["lessons"] = request.lessons
    if request.notes:
        data["review_notes"] = request.notes
    if request.affected_kpis:
        data["affected_kpis"] = request.affected_kpis
    
    # Write updated YAML
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
    
    # Re-index with outcome metadata
    reindexed = await reindex_decision(request.id, data)
    
    return ReviewDecisionResponse(
        success=True,
        id=request.id,
        path=str(path),
        status="reviewed",
        reviewed_at=now.isoformat(),
        reindexed=reindexed,
    )
```

### Phase 3: Dispatcher Integration (~30m)

```python
async def _handle_review_decision(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    request = ReviewDecisionRequest.from_dict(params)
    
    valid_outcomes = {"success", "partial", "failure", "abandoned"}
    if request.outcome not in valid_outcomes:
        raise ValueError(f"outcome must be one of {valid_outcomes}")
    
    response = await review_decision(request)
    return response.to_dict()

# Register
dispatcher.register("cstp.reviewDecision", _handle_review_decision)
```

### Phase 4: Tests (~1h)

**Test cases:**
- Review existing decision successfully
- Decision not found error
- Invalid outcome error
- Partial update (only required fields)
- Full update (all fields)
- Re-indexing updates metadata

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `a2a/cstp/decision_service.py` | Modify | Add find_decision, review_decision |
| `a2a/cstp/models.py` | Modify | Add ReviewDecisionRequest/Response |
| `a2a/cstp/dispatcher.py` | Modify | Register new method |
| `tests/test_decision_service.py` | Modify | Add review tests |
| `tests/test_f008_review_decision.py` | Create | Integration tests |

---

## YAML Schema After Review

```yaml
id: fddb416c
summary: "Use Redis for caching"
decision: "Use Redis for caching"
category: architecture
confidence: 0.85
stakes: high
status: reviewed              # Changed from "pending"
date: "2026-02-05T00:48:00Z"
context: "Choosing cache layer"
reasons:
  - type: analysis
    text: "Fast lookups needed"
    strength: 0.9

# Added by review
outcome: success              # success | partial | failure | abandoned
reviewed_at: "2026-02-12T14:30:00Z"
actual_result: "Latency reduced 40%"
lessons: "Should have considered clustering"
review_notes: "Will add clustering next sprint"
affected_kpis:
  latency: -0.4
  cost: 0.1
```

---

## Estimated Effort

| Phase | Time |
|-------|------|
| Decision Lookup | 1h |
| Review Service | 1.5h |
| Dispatcher Integration | 30m |
| Tests | 1h |
| **Total** | **~4h** |
