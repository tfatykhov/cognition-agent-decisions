# Deliberation Traces

> **Feature:** F023 | **Status:** Shipped in v0.10.0

Deliberation traces capture the chain-of-thought behind every decision - which past decisions you queried, which guardrails you checked, and how long the process took.

## How It Works

The CSTP server tracks your queries and checks per `agent_id`. When you record a decision, it automatically attaches the trace.

```
Agent queries "retry patterns"     → Tracker stores input
Agent checks guardrails            → Tracker stores input
Agent records decision             → Tracker builds trace, attaches it, clears
```

**Zero client changes needed.** The server handles everything.

## What Gets Captured

Each deliberation trace contains:

- **Inputs** - queries and guardrail checks that preceded the decision
- **Steps** - timestamped processing events
- **Timing** - total deliberation duration in milliseconds
- **Convergence** - whether multiple search paths pointed to the same answer

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
