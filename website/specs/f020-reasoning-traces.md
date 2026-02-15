# F020: Structured Reasoning Traces

## Context
Current decision logging captures the `decision` (output) and `context` (input summary), plus high-level `reasons` (categorical). It completely misses the **process**—the step-by-step reasoning chain that led to the decision. 

Recent research (GRPO, DAPO) shows that optimizing the reasoning *process* (step-level value) is critical for high-stakes agentic tasks. To support this, CSTP must capture the reasoning trace.

## Requirement
Update the `Decision` model and `recordDecision` endpoint to accept a structured reasoning trace.

## Specification

### 1. Schema Update
Add `trace` field to `Decision` model:

```python
class ReasoningStep(BaseModel):
    step: int
    thought: str  # The reasoning content
    output: str | None = None  # Optional intermediate result/action
    confidence: float | None = None  # Step-level confidence (if available)
    tags: list[str] = []  # e.g. ["planning", "critique", "selection"]

class Decision(BaseModel):
    # ... existing fields ...
    trace: list[ReasoningStep] | None = None
```

### 2. API Update
**Method:** `cstp.recordDecision`

**Params:**
- `trace` (optional, list): List of reasoning steps.

**Example Payload:**
```json
{
  "decision": "Use Postgres instead of SQLite",
  "trace": [
    {
      "step": 1,
      "thought": "Analyzing concurrency requirements...",
      "output": "High concurrency needed",
      "tags": ["analysis"]
    },
    {
      "step": 2,
      "thought": "Comparing SQLite vs Postgres limits...",
      "output": "SQLite locks on write",
      "tags": ["comparison"]
    }
  ]
}
```

### 3. Downstream Usage
*   **Offline Analysis:** DAPO-style attribution of failure to specific reasoning steps.
*   **Pattern Detection:** "Steps tagged 'analysis' often missing in failed decisions."
*   **Debugging:** Replay the agent's thought process.

## Migration
*   Backward compatible (optional field).
*   Existing decisions have `trace=None`.
