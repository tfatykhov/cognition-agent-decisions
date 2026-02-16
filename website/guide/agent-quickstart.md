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

### 3. After Deciding: Record (via `pre_action` — preferred)

```json
{"jsonrpc":"2.0","method":"cstp.preAction","params":{
  "action":{
    "description":"Add exponential backoff with jitter to payment API",
    "category":"architecture",
    "stakes":"high",
    "confidence":0.85
  },
  "auto_record":true,
  "reasons":[
    {"type":"analysis","text":"Backoff handles transient failures; jitter prevents thundering herd"},
    {"type":"empirical","text":"Similar pattern succeeded in order-service (decision abc123)"}
  ],
  "tags":["resilience","retry","payment"],
  "pattern":"Exponential backoff with jitter for transient failures"
},"id":3}
```

This queries + checks guardrails + records in **one call**, returning a `decisionId`.

### 4. During Work: Capture Reasoning

```json
{"jsonrpc":"2.0","method":"cstp.recordThought","params":{
  "text":"Chose 3 retries with base 500ms - matches P99 latency recovery window",
  "decision_id":"<decisionId from step 3>"
},"id":4}
```

### 5. After Work: Finalize

```json
{"jsonrpc":"2.0","method":"cstp.updateDecision","params":{
  "id":"<decisionId>",
  "decision":"Added exponential backoff (3 retries, 500ms base, jitter) to payment API",
  "context":"Deployed to staging, 503 rate dropped from 2.1% to 0.03%"
},"id":5}
```

### 6. What You Get Back

The server automatically attaches:
- **Deliberation trace**: Your queries and reasoning steps linked to this decision
- **Bridge-definition**: Structure (what it looks like) + function (what it solves) extracted from your text
- **Related decisions**: Past decisions found during pre_action, linked with distance scores
- **Graph edges**: Auto-linked to related decisions

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

1. **Decide + Record**: Use pre_action with auto_record to query, check guardrails, and record in one call
   POST /cstp {"method":"cstp.preAction","params":{"action":{"description":"what you want to do","category":"architecture","stakes":"medium","confidence":0.85},"auto_record":true,"reasons":[{"type":"analysis","text":"why"}],"tags":["keyword"],"pattern":"abstract principle"}}

2. **Think**: Capture reasoning during work (use decisionId from step 1)
   POST /cstp {"method":"cstp.recordThought","params":{"text":"reasoning...","decision_id":"<decisionId>"}}

3. **Finalize**: Update the decision with what actually happened
   POST /cstp {"method":"cstp.updateDecision","params":{"id":"<decisionId>","decision":"what you actually did","context":"outcome details"}}

4. **Review** (later): Record success/failure for calibration
   POST /cstp {"method":"cstp.reviewDecision","params":{"id":"<decisionId>","outcome":"success","result":"what happened"}}

Use at least 2 different reason types for robustness.
For multi-agent setups, pass agent_id to isolate deliberation streams.
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
