---
name: cognition-engines
description: Decision intelligence for AI agents. Query similar past decisions, check guardrails before deciding, and auto-index decisions for semantic search.
homepage: https://github.com/tfatykhov/cognition-agent-decisions
metadata:
  openclaw:
    emoji: "🧠"
    requires:
      env:
        - CSTP_TOKEN
    primaryEnv: CSTP_TOKEN
---

# Cognition Engines v0.10.0

Decision intelligence for AI agents. Every decision automatically captures its full cognitive context - deliberation traces, bridge-definitions, and related decision links.

## Setup

**Required:** A running CSTP server and an API token.

```bash
# Set in your .secrets/ or environment
export CSTP_URL="http://your-server:9991"
export CSTP_TOKEN="your-token"
```

## Decision Protocol

Every significant decision follows this workflow. The server auto-captures your query and check as deliberation trace inputs.

### Step 1: Query Similar Decisions

```bash
uv run scripts/cstp.py query "your decision context" --top 5 --mode hybrid
```

**Directional search** (F024 Bridge-Definitions):
```bash
# "What solved problems like this?" (search by purpose)
uv run scripts/cstp.py query "the problem" --bridge-side function --top 5

# "Where did we use this pattern?" (search by form)
uv run scripts/cstp.py query "the approach" --bridge-side structure --top 5
```

### Step 2: Check Guardrails

```bash
uv run scripts/cstp.py check -d "what you want to do" -s high -f 0.85
```

### Step 3: Record the Decision

```bash
uv run scripts/cstp.py record \
  -d "What you decided" \
  -f 0.85 \
  -c architecture \
  -s medium \
  --context "Situation and what was done" \
  -r "analysis:Why this approach" \
  -r "pattern:Similar to past approach X"
```

**Optional bridge-definition (Minsky Ch 12):**
```bash
uv run scripts/cstp.py record \
  -d "Used retry with backoff" \
  -f 0.88 -c architecture -s medium \
  --structure "Exponential backoff with jitter" \
  --function "Handle transient API failures without cascading"
```

### Step 4: Review Outcomes (Later)

```bash
uv run scripts/cstp.py review --id <id> --outcome success --result "What happened"
```

### Step 5: Get Decision Details

```bash
uv run scripts/cstp.py get <id>
```

### Step 6: Check Calibration

```bash
uv run scripts/cstp.py calibration
```

## What Happens Automatically

When you follow the query -> check -> record workflow, three things auto-populate:

| Feature | What It Does | Response Field |
|---------|-------------|----------------|
| **Deliberation Traces** (F023) | Links your queries and checks to the decision | `deliberation_auto: true` |
| **Bridge-Definitions** (F024) | Extracts structure/function from your text | `bridge_auto: true` |
| **Related Decisions** (F025) | Links to decisions found in pre-decision queries | `related_count: N` |

Zero client changes needed - the server handles everything.

## MCP Integration

For MCP-compliant agents (Claude Desktop, OpenClaw, etc.):

**Endpoint:** `http://your-server:9991/mcp`

**7 Tools Available:**
- `query_decisions` - search past decisions (supports `bridge_side`)
- `check_action` - validate against guardrails
- `log_decision` - record a new decision (with optional bridge)
- `review_outcome` - record what actually happened
- `get_stats` - calibration statistics
- `get_decision` - full decision details by ID
- `get_reason_stats` - which reason types predict success

## JSON-RPC API

For direct HTTP integration:

```bash
curl -s -X POST http://your-server:9991/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.queryDecisions","params":{
    "query":"database selection",
    "bridgeSide":"function",
    "limit":5
  },"id":1}'
```

**Methods:** `cstp.queryDecisions`, `cstp.checkGuardrails`, `cstp.recordDecision`, `cstp.reviewDecision`, `cstp.getCalibration`, `cstp.getDecision`, `cstp.getReasonStats`, `cstp.attributeOutcomes`, `cstp.listGuardrails`, `cstp.checkDrift`

## For Other Agents

### Quick Onboarding

Any AI agent can use Cognition Engines by adding this to its system prompt or AGENTS.md:

```
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

### What to Log

- Architecture and design choices
- Tool or library selections
- Process changes
- Bug fix approaches
- Any choice that could be wrong and worth reviewing

### What NOT to Log

- Routine operations (backups, deploys)
- Trivial formatting choices
- Decisions already made by someone else

## Guardrails

Default rules in `guardrails/`:
- **no-high-stakes-low-confidence**: Block if stakes=high and confidence < 0.5
- **no-production-without-review**: Block production changes without code review

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `CSTP_TOKEN` | Yes | - | API authentication token |
| `CSTP_URL` | No | `http://localhost:9991` | CSTP server URL |
| `GEMINI_API_KEY` | Server | - | Embeddings (server-side only) |
| `CHROMA_URL` | Server | `http://localhost:8000` | ChromaDB (server-side only) |
