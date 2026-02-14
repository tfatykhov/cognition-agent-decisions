# F004: cstp.announceIntent Method

| Field | Value |
|-------|-------|
| Feature ID | F004 |
| Status | Draft |
| Priority | P1 |
| Depends On | F001 (Server Infrastructure), F002, F003 |
| Blocks | None |
| Decision | a42a3514 |

---

## Summary

Implement `cstp.announceIntent` method to enable agents to announce their intent before taking action and receive feedback from other agents.

## Goals

1. JSON-RPC method handler for `cstp.announceIntent`
2. Combine query + guardrails in single call
3. Store received intents for audit trail
4. Return similar decisions + guardrail status + suggestions
5. Optional: trigger for agent-to-agent callbacks

## Non-Goals

- Real-time push notifications
- Intent negotiation/blocking
- Multi-agent consensus

---

## Specification

### Method Signature

**Method:** `cstp.announceIntent`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.announceIntent",
  "id": "req-001",
  "params": {
    "intent": "Deploy authentication service to production",
    "context": "PR #42 approved, all tests passing, CI green",
    "category": "architecture",
    "stakes": "high",
    "confidence": 0.85,
    "agent": {
      "id": "emerson",
      "url": "https://emerson.example.com"
    },
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "metadata": {
      "pr_number": 42,
      "branch": "feat/auth-v2",
      "commit": "abc123"
    }
  }
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| intent | string | ✅ | - | What the agent intends to do |
| context | string | ❌ | null | Additional context |
| category | string | ❌ | null | Decision category |
| stakes | string | ❌ | "medium" | Stakes level |
| confidence | float | ❌ | null | Agent's confidence |
| agent.id | string | ❌ | null | Announcing agent ID |
| agent.url | string | ❌ | null | Announcing agent URL |
| correlationId | string | ❌ | auto | ID to correlate responses |
| metadata | object | ❌ | {} | Additional structured data |

### Response

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "received": true,
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "receivedAt": "2026-02-04T21:00:00Z",
    
    "similarDecisions": [
      {
        "id": "dec-123",
        "title": "Deployed auth service v2.1",
        "outcome": "success",
        "date": "2026-01-15T10:30:00Z",
        "distance": 0.18,
        "notes": "Required 30-min rollback window"
      },
      {
        "id": "dec-456",
        "title": "Auth service rollback after memory leak",
        "outcome": "partial",
        "date": "2026-01-10T08:00:00Z",
        "distance": 0.25,
        "notes": "Issue was in connection pooling"
      }
    ],
    
    "guardrailStatus": {
      "allowed": true,
      "violations": [],
      "warnings": [
        {
          "guardrailId": "prefer-staged-rollout",
          "message": "Consider staged rollout for production changes"
        }
      ],
      "evaluated": 5
    },
    
    "suggestions": [
      "Similar deploy succeeded with 30-min rollback window",
      "Consider staged rollout based on past partial failure",
      "Previous memory leak was in connection pooling"
    ],
    
    "respondingAgent": "cognition-engines"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| received | bool | Intent was received |
| correlationId | string | ID for correlation |
| receivedAt | datetime | When intent was received |
| similarDecisions | array | Relevant past decisions |
| similarDecisions[].id | string | Decision ID |
| similarDecisions[].title | string | Decision summary |
| similarDecisions[].outcome | string | Outcome if known |
| similarDecisions[].date | datetime | Decision date |
| similarDecisions[].distance | float | Semantic distance |
| similarDecisions[].notes | string | Relevant notes/lessons |
| guardrailStatus | object | Guardrail evaluation |
| guardrailStatus.allowed | bool | Whether allowed |
| guardrailStatus.violations | array | Blocking violations |
| guardrailStatus.warnings | array | Non-blocking warnings |
| guardrailStatus.evaluated | int | Guardrails checked |
| suggestions | array | AI-generated suggestions |
| respondingAgent | string | Responding agent ID |

### Errors

| Code | Message | When |
|------|---------|------|
| -32602 | InvalidParams | Missing intent |
| -32003 | QueryFailed | ChromaDB unavailable |
| -32004 | GuardrailEvalFailed | Evaluation error |
| -32002 | RateLimited | Too many requests |

---

## Implementation

### Handler

```python
# a2a/cstp/methods.py

from ..models.requests import AnnounceIntentRequest
from ..models.responses import AnnounceIntentResponse
from .methods import handle_query_decisions, handle_check_guardrails
from .suggestions import generate_suggestions

async def handle_announce_intent(
    params: AnnounceIntentRequest,
    agent_id: str
) -> AnnounceIntentResponse:
    """Handle cstp.announceIntent method."""
    
    # Rate limit check
    check_rate_limit(agent_id, "announceIntent")
    
    # Generate correlation ID if not provided
    correlation_id = params.correlationId or str(uuid.uuid4())
    received_at = datetime.utcnow()
    
    # Store intent for audit
    await store_intent(
        correlation_id=correlation_id,
        intent=params.intent,
        context=params.context,
        agent=agent_id,
        received_at=received_at,
    )
    
    # Query similar decisions
    query_result = await handle_query_decisions(
        QueryDecisionsRequest(
            query=f"{params.intent} {params.context or ''}",
            filters=QueryFilters(category=params.category),
            limit=5,
            includeReasons=False,
        ),
        agent_id=agent_id,
    )
    
    # Check guardrails
    guardrail_result = await handle_check_guardrails(
        CheckGuardrailsRequest(
            action=ActionContext(
                description=params.intent,
                category=params.category,
                stakes=params.stakes,
                confidence=params.confidence,
            ),
        ),
        agent_id=agent_id,
    )
    
    # Generate suggestions from similar decisions
    suggestions = generate_suggestions(
        intent=params.intent,
        similar_decisions=query_result.decisions,
        guardrail_warnings=guardrail_result.warnings,
    )
    
    return AnnounceIntentResponse(
        received=True,
        correlationId=correlation_id,
        receivedAt=received_at,
        similarDecisions=query_result.decisions,
        guardrailStatus=guardrail_result,
        suggestions=suggestions,
        respondingAgent=get_agent_name(),
    )
```

### Suggestions Generator

```python
# a2a/cstp/suggestions.py

def generate_suggestions(
    intent: str,
    similar_decisions: List[DecisionSummary],
    guardrail_warnings: List[Violation],
) -> List[str]:
    """Generate actionable suggestions from context."""
    
    suggestions = []
    
    # Extract lessons from similar decisions
    for decision in similar_decisions[:3]:
        if decision.outcome == "success":
            suggestions.append(
                f"Similar action succeeded: {decision.title}"
            )
        elif decision.outcome == "failure":
            suggestions.append(
                f"Warning: Similar action failed: {decision.title}"
            )
        elif decision.outcome == "partial":
            suggestions.append(
                f"Similar action had issues: {decision.title}"
            )
    
    # Add guardrail-based suggestions
    for warning in guardrail_warnings:
        if warning.suggestion:
            suggestions.append(warning.suggestion)
    
    return suggestions[:5]  # Max 5 suggestions
```

### Intent Storage

```python
# a2a/cstp/storage.py

async def store_intent(
    correlation_id: str,
    intent: str,
    context: Optional[str],
    agent: str,
    received_at: datetime,
) -> None:
    """Store received intent for audit trail."""
    
    intent_record = {
        "correlation_id": correlation_id,
        "intent": intent,
        "context": context,
        "agent": agent,
        "received_at": received_at.isoformat(),
    }
    
    # Store to file (later: database)
    intent_path = INTENTS_DIR / f"{correlation_id}.json"
    intent_path.write_text(json.dumps(intent_record, indent=2))
```

---

## Implementation Tasks

- [ ] Create `AnnounceIntentRequest` Pydantic model
- [ ] Create `AnnounceIntentResponse` Pydantic model
- [ ] Implement `handle_announce_intent` handler
- [ ] Implement `generate_suggestions` helper
- [ ] Implement intent storage for audit trail
- [ ] Add rate limiting per agent
- [ ] Register method in JSON-RPC dispatcher
- [ ] Write unit tests
- [ ] Write integration test with full flow

---

## Acceptance Criteria

1. `cstp.announceIntent` returns received confirmation
2. Similar decisions included in response
3. Guardrail status included in response
4. Suggestions generated from context
5. Intent stored for audit trail
6. Correlation ID returned (generated if not provided)
7. Rate limiting blocks excessive requests
8. Response time < 1000ms (combines query + guardrails)
