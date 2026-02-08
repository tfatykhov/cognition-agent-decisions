# Agent Quick Start Guide

> **Version:** v0.10.0
> **Protocol:** JSON-RPC 2.0 over HTTP (`/cstp`) or MCP (`/mcp`)

## What This Is

A decision intelligence server. You query it before making decisions, and it helps you:
- Find what approaches worked (or failed) for similar problems
- Check if guardrails allow your planned action
- Record decisions with structured reasoning for future reference
- Build calibration data so your confidence estimates improve over time

## Quick Start

### 1. Connect

**JSON-RPC:**
```
POST http://<server>:9991/cstp
Authorization: Bearer <your-token>
Content-Type: application/json
```

**MCP:** Connect to `http://<server>:9991/mcp` with any MCP-compliant client.

### 2. Before Deciding: Query + Check

```json
// Step 1: What solved problems like this?
{"jsonrpc":"2.0","method":"cstp.queryDecisions","params":{
  "query":"handling transient API failures",
  "bridgeSide":"function",
  "limit":5
},"id":1}

// Step 2: Am I allowed to do this?
{"jsonrpc":"2.0","method":"cstp.checkGuardrails","params":{
  "action":{
    "description":"Add retry logic to payment API",
    "category":"architecture",
    "stakes":"high",
    "confidence":0.85
  }
},"id":2}
```

### 3. After Deciding: Record

```json
{"jsonrpc":"2.0","method":"cstp.recordDecision","params":{
  "decision":"Added exponential backoff with jitter to payment API",
  "confidence":0.85,
  "category":"architecture",
  "stakes":"high",
  "context":"Payment API returning 503s during peak. Needed resilience without circuit breaker complexity.",
  "reasons":[
    {"type":"analysis","text":"Backoff handles transient failures; jitter prevents thundering herd"},
    {"type":"empirical","text":"Similar pattern succeeded in order-service (decision abc123)"}
  ]
},"id":3}
```

### 4. What You Get Back

The server automatically attaches:
- **Deliberation trace**: Your Step 1-2 queries linked to this decision
- **Bridge-definition**: Structure (what it looks like) + function (what it solves) extracted from your text
- **Related decisions**: The decisions found in Step 1, linked with distance scores

```json
{
  "result":{
    "id":"def456",
    "indexed":true,
    "deliberation_auto":true,
    "deliberation_inputs_count":2,
    "bridge_auto":true,
    "related_count":5
  }
}
```

## Adding to Your Agent's System Prompt

Paste this into your agent's AGENTS.md or system prompt:

```markdown
## Decision Protocol

Before making significant decisions (architecture, tooling, process):

1. **Query**: Search past decisions for similar context
   POST /cstp {"method":"cstp.queryDecisions","params":{"query":"your context"}}

2. **Check**: Validate against guardrails
   POST /cstp {"method":"cstp.checkGuardrails","params":{"action":{"description":"what you want to do","stakes":"medium"}}}

3. **Record**: Log the decision with reasons
   POST /cstp {"method":"cstp.recordDecision","params":{"decision":"what you chose","confidence":0.85,"category":"architecture","reasons":[{"type":"analysis","text":"why"}]}}

The server auto-captures your query and check as deliberation inputs.
Use at least 2 different reason types for robustness.
```

## Tips

- **Use 2+ reason types** for robustness: `analysis`, `empirical`, `pattern`, `authority`, `constraint`, `analogy`, `intuition`, `elimination`
- **bridgeSide search**: Use `"function"` to find what solved similar problems, `"structure"` to find where a pattern was used before
- **Confidence honestly**: Rate your actual uncertainty, not optimism. The calibration data is more valuable than a clean record.
- **Review outcomes**: Call `cstp.reviewDecision` when you know the result. This builds calibration data.

## What to Log

- Architecture and design choices
- Tool or library selections
- Process changes
- Bug fix approaches
- Any choice that could be wrong and worth reviewing

## What NOT to Log

- Routine operations (backups, deploys)
- Trivial formatting choices
- Decisions already made by someone else

## Available Methods

| Method | Purpose |
|--------|---------|
| `cstp.queryDecisions` | Search past decisions (semantic, keyword, or hybrid) |
| `cstp.checkGuardrails` | Validate an action against policy rules |
| `cstp.recordDecision` | Log a new decision with reasoning |
| `cstp.reviewDecision` | Record the outcome of a past decision |
| `cstp.getDecision` | Get full decision details by ID |
| `cstp.getCalibration` | Calibration stats (Brier score, accuracy) |
| `cstp.getReasonStats` | Which reason types predict success |
| `cstp.listGuardrails` | List active guardrail rules |
| `cstp.checkDrift` | Detect calibration drift over time |
| `cstp.attributeOutcomes` | Bulk outcome attribution by project |

## Categories

`architecture`, `process`, `integration`, `tooling`, `security`

## Stakes

`low`, `medium`, `high`, `critical`
