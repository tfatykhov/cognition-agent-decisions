# Deliberation Traces

> **Feature:** F023 + F028 | **Status:** Shipped in v0.10.0+

Deliberation traces capture the full chain-of-thought behind every decision - which past decisions you queried, which guardrails you checked, what reasoning you applied, and how long the process took.

## How It Works

The CSTP server tracks your queries, checks, and reasoning per `agent_id`. When you record a decision, it automatically attaches the trace.

```
Agent queries "retry patterns"     → Tracker stores input
Agent checks guardrails            → Tracker stores input
Agent records thought              → Tracker stores reasoning step
Agent records decision             → Tracker builds trace, attaches it, clears
```

**Zero client changes needed.** The server handles everything.

## What Gets Captured

Each deliberation trace contains:

- **Inputs** - queries, guardrail checks, and reasoning steps that preceded the decision
- **Steps** - timestamped processing events with types (`analysis`, `constraint`, `reasoning`)
- **Timing** - total deliberation duration in milliseconds
- **Convergence** - whether multiple search paths pointed to the same answer

## Reasoning Steps (F028)

Use `cstp.recordThought` to capture your chain-of-thought reasoning before recording a decision:

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.recordThought","params":{"text":"Option A is simpler but Option B handles edge cases better"},"id":1}'
```

Reasoning steps appear in the trace with `"type": "reasoning"` and `"source": "cstp:recordThought"`.

**Post-decision mode:** You can also append reasoning to an existing decision:

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.recordThought","params":{"text":"Retrospective: Option B was the right call","decision_id":"dec_abc123"},"id":1}'
```

## Example

```yaml
deliberation:
  inputs:
    - id: q-a1b2c3
      type: query
      text: "Queried 'retry patterns': 3 results"
    - id: g-d4e5f6
      type: guardrail
      text: "Checked 'deploy retry logic': Allowed"
  steps:
    - timestamp: "2026-02-08T21:30:00Z"
      action: "query_executed"
    - timestamp: "2026-02-08T21:30:01Z"
      action: "guardrail_checked"
    - timestamp: "2026-02-08T21:30:05Z"
      action: "decision_recorded"
  timing_ms: 5000
```

## Why It Matters

- **Provenance** - see exactly what influenced each decision
- **Compliance** - prove the full workflow was followed
- **Learning** - identify when skipped steps correlate with failures
- **Debugging** - when a decision goes wrong, trace back to what was considered
