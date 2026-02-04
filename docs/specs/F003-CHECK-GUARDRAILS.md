# F003: cstp.checkGuardrails Method

| Field | Value |
|-------|-------|
| Feature ID | F003 |
| Status | Draft |
| Priority | P1 |
| Depends On | F001 (Server Infrastructure) |
| Blocks | None |
| Decision | a42a3514 |

---

## Summary

Implement `cstp.checkGuardrails` method to enable remote agents to check their intended actions against this agent's guardrails.

## Goals

1. JSON-RPC method handler for `cstp.checkGuardrails`
2. Wrap existing `check.py` functionality
3. Evaluate action context against guardrails
4. Return allow/block with violation details
5. Audit logging of all checks

## Non-Goals

- Guardrail modification via API
- Custom guardrail upload
- Guardrail templates

---

## Specification

### Method Signature

**Method:** `cstp.checkGuardrails`

### Request

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.checkGuardrails",
  "id": "req-001",
  "params": {
    "action": {
      "description": "Deploy authentication service to production",
      "category": "architecture",
      "stakes": "high",
      "confidence": 0.85,
      "context": {
        "affectsProduction": true,
        "codeReviewCompleted": true,
        "hasTests": true,
        "ciPassing": true
      }
    },
    "agent": {
      "id": "emerson",
      "url": "https://emerson.example.com"
    }
  }
}
```

### Request Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| action.description | string | ✅ | - | What the agent wants to do |
| action.category | string | ❌ | null | Decision category |
| action.stakes | string | ❌ | "medium" | Stakes level |
| action.confidence | float | ❌ | null | Agent's confidence |
| action.context | object | ❌ | {} | Additional context for evaluation |
| agent.id | string | ❌ | null | Requesting agent ID |
| agent.url | string | ❌ | null | Requesting agent URL |

### Response (Allowed)

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "allowed": true,
    "violations": [],
    "warnings": [],
    "evaluated": 5,
    "evaluatedAt": "2026-02-04T21:00:00Z",
    "agent": "cognition-engines"
  }
}
```

### Response (Blocked)

```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "allowed": false,
    "violations": [
      {
        "guardrailId": "no-production-without-review",
        "name": "Production Requires Review",
        "message": "Production changes require completed code review",
        "severity": "block",
        "suggestion": "Complete code review before deploying"
      }
    ],
    "warnings": [
      {
        "guardrailId": "prefer-staged-rollout",
        "name": "Staged Rollout Preferred",
        "message": "Consider staged rollout for production changes",
        "severity": "warn",
        "suggestion": "Deploy to 10% of traffic first"
      }
    ],
    "evaluated": 5,
    "evaluatedAt": "2026-02-04T21:00:00Z",
    "agent": "cognition-engines"
  }
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| allowed | bool | Whether action is allowed |
| violations | array | Blocking guardrail violations |
| violations[].guardrailId | string | Guardrail identifier |
| violations[].name | string | Human-readable name |
| violations[].message | string | Violation explanation |
| violations[].severity | string | "block" or "warn" |
| violations[].suggestion | string | How to resolve |
| warnings | array | Non-blocking warnings |
| evaluated | int | Number of guardrails checked |
| evaluatedAt | datetime | Evaluation timestamp |
| agent | string | Responding agent ID |

### Errors

| Code | Message | When |
|------|---------|------|
| -32602 | InvalidParams | Missing action.description |
| -32004 | GuardrailEvalFailed | Evaluation error |
| -32002 | RateLimited | Too many requests |

---

## Implementation

### Handler

```python
# a2a/cstp/methods.py

from ..models.requests import CheckGuardrailsRequest
from ..models.responses import CheckGuardrailsResponse
from skills.cognition_engines.check import evaluate_guardrails

async def handle_check_guardrails(
    params: CheckGuardrailsRequest,
    agent_id: str
) -> CheckGuardrailsResponse:
    """Handle cstp.checkGuardrails method."""
    
    # Rate limit check
    check_rate_limit(agent_id, "checkGuardrails")
    
    # Build evaluation context
    context = {
        "category": params.action.category,
        "stakes": params.action.stakes,
        "confidence": params.action.confidence,
        **params.action.context,
    }
    
    # Evaluate against guardrails
    result = await evaluate_guardrails(context)
    
    # Audit log
    log_guardrail_check(
        requesting_agent=agent_id,
        action=params.action.description,
        allowed=result.allowed,
        violations=result.violations,
    )
    
    # Map to response
    violations = [
        Violation(
            guardrailId=v.id,
            name=v.name,
            message=v.message,
            severity=v.severity,
            suggestion=v.suggestion,
        )
        for v in result.violations
        if v.severity == "block"
    ]
    
    warnings = [
        Violation(
            guardrailId=v.id,
            name=v.name,
            message=v.message,
            severity=v.severity,
            suggestion=v.suggestion,
        )
        for v in result.violations
        if v.severity == "warn"
    ]
    
    return CheckGuardrailsResponse(
        allowed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
        evaluated=result.evaluated,
        evaluatedAt=datetime.utcnow(),
        agent=get_agent_name(),
    )
```

### Models

```python
# a2a/models/requests.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class ActionContext(BaseModel):
    description: str = Field(..., min_length=1)
    category: Optional[str] = None
    stakes: str = "medium"
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    context: Dict[str, Any] = Field(default_factory=dict)

class AgentInfo(BaseModel):
    id: Optional[str] = None
    url: Optional[str] = None

class CheckGuardrailsRequest(BaseModel):
    action: ActionContext
    agent: Optional[AgentInfo] = None
```

### Audit Log Format

```json
{
  "timestamp": "2026-02-04T21:00:00Z",
  "event": "guardrail_check",
  "requesting_agent": "emerson",
  "action": "Deploy authentication service to production",
  "allowed": false,
  "violations": ["no-production-without-review"],
  "evaluated": 5
}
```

---

## Implementation Tasks

- [ ] Create `CheckGuardrailsRequest` Pydantic model
- [ ] Create `CheckGuardrailsResponse` Pydantic model
- [ ] Implement `handle_check_guardrails` handler
- [ ] Add audit logging for checks
- [ ] Add rate limiting per agent
- [ ] Register method in JSON-RPC dispatcher
- [ ] Write unit tests with mock guardrails
- [ ] Write integration test with real guardrails

---

## Acceptance Criteria

1. `cstp.checkGuardrails` correctly evaluates context
2. Violations return `allowed: false`
3. Warnings included but don't block
4. All checks are audit logged
5. Rate limiting blocks excessive requests
6. Invalid params return -32602 error
7. Response time < 100ms
