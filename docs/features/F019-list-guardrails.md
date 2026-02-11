# F019: List Guardrails Endpoint

## Context
Agents currently check guardrails blindly using `checkGuardrails` (or `check` in CLI). They do not know *which* rules are active or what the specific criteria are without reading the raw YAML files on the server (which they might not have access to).

## Requirement
Expose an API endpoint to list all active guardrails loaded by the CSTP server.

## Specification

### 1. JSON-RPC Method
**Method:** `cstp.listGuardrails`

**Params:**
- `scope` (optional, string): Filter by project/scope. If provided, only returns guardrails that apply to this scope (or global ones).

**Returns:**
```json
{
  "guardrails": [
    {
      "id": "no-high-stakes-low-confidence",
      "description": "Prevent high-stakes actions without high confidence",
      "action": "block",
      "scope": [],  # Empty = global
      "conditions": [
        {"field": "stakes", "operator": "eq", "value": "high"},
        {"field": "confidence", "operator": "lt", "value": 0.5}
      ],
      "requirements": []
    }
  ],
  "count": 1
}
```

### 2. Python Service Layer
Add `list_guardrails` function to `guardrails_service.py`:
```python
def list_guardrails(scope: str | None = None) -> list[dict[str, Any]]:
    """List active guardrails, optionally filtered by scope."""
```

### 3. CLI Command
Add `list-guardrails` command to `cstp.py`:
```bash
uv run scripts/cstp.py list-guardrails
# Output:
# ACTIVE GUARDRAILS (5):
# - no-high-stakes-low-confidence (block): Prevent high-stakes actions...
# - require-code-review (block): Production code requires review...
```

## Security
- Read-only endpoint.
- Available to all authenticated agents.
