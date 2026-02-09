# F023: Deliberation Traces — Chain-of-Thought Capture

## Status: Draft
## Author: ⚡ Emerson
## Date: 2026-02-08

## Problem

Current decision records capture WHAT was decided and WHY (reasons), but not 
HOW the thinking process unfolded. This loses:

1. **Provenance** — which inputs influenced which conclusions
2. **Temporal dynamics** — thinking order, time spent per step
3. **Convergence patterns** — how independent inputs combined into a conclusion
4. **Replay capability** — can't reconstruct the reasoning path for learning

## Solution

Add a `deliberation` field to decision records that captures the step-by-step 
reasoning trace with inputs, intermediate thoughts, and timing.

## Schema

```yaml
deliberation:
  inputs:
    - id: "i1"
      text: "Description of input/evidence"
      source: "where it came from"  # optional: url, file, memory, api, etc.
      timestamp: "2026-02-08T14:01:00Z"  # when this input was gathered

  steps:
    - step: 1
      thought: "What was considered at this step"
      inputs_used: ["i1", "i2"]  # which inputs contributed
      timestamp: "2026-02-08T14:01:03Z"
      duration_ms: 3200  # optional: how long this step took
      type: "analysis"  # optional: maps to reason types

    - step: 2
      thought: "How inputs converged"
      inputs_used: ["i1", "i2", "i3"]
      timestamp: "2026-02-08T14:01:05Z"
      duration_ms: 1800
      type: "pattern"
      conclusion: true  # marks the concluding step

  total_duration_ms: 8200  # total deliberation time
  convergence_point: 2  # step where inputs converged to decision
```

## Requirements

### R1: Schema Extension
- Add `deliberation` field to `RecordDecisionRequest`
- Required for new decisions, absent in legacy decisions
- Backward compatible: existing decisions without deliberation still work

### R2: Automatic Capture (Client-Side)
The CSTP client (`cstp.py` / MCP tool) tracks deliberation automatically:

```
Agent workflow:
  1. query_decisions("should I use X?")     → input i1 (similar past decisions)
  2. check_action("deploy X")               → input i2 (guardrail result)
  3. [agent reasoning]                       → step 1: considered i1+i2
  4. query_decisions("X vs Y comparison")    → input i3 (more evidence)
  5. [agent reasoning]                       → step 2: converged on X
  6. log_decision(deliberation={...})        → record with full trace
```

Implementation approach:
- CSTP client maintains a `DeliberationContext` that accumulates inputs/steps
- Each `query_decisions` / `check_action` call auto-registers as an input
- Agent explicitly adds `steps` via `add_step()` or they're inferred from 
  the sequence of API calls
- On `log_decision`, the accumulated trace is attached automatically

### R3: Search Enhancement
When `queryDecisions` returns similar past decisions, optionally include 
deliberation traces so agents can see HOW those decisions were made:

```json
{
  "query": "should I use Izhikevich neurons?",
  "includeDeliberation": true,
  "decisions": [{
    "id": "abc123",
    "title": "Use Izhikevich for Membrain",
    "deliberation": { ... }  // full trace
  }]
}
```

### R4: Deliberation Analytics
New analytics on deliberation patterns:

- **Step count vs outcome**: Do more deliberate decisions succeed more?
- **Input count vs outcome**: Do decisions with more inputs perform better?
- **Convergence speed**: Fast convergence = intuition, slow = analysis
- **Input source diversity**: Decisions using varied sources (memory, search, 
  analysis) vs single-source

### R5: Membrain Integration (Future)
Deliberation traces map to SNN temporal patterns:

- Each input = activation of a neuron population
- Each step = a time window of network dynamics
- Convergence = attractor basin formation
- Replay = feed the temporal sequence back through the SNN

The trace format is designed to be directly convertible to spike timing 
patterns for Membrain's STDP-based learning.

## API Changes

### `cstp.recordDecision` — Extended
```json
{
  "decision": "Use Izhikevich neurons",
  "confidence": 0.85,
  "deliberation": {
    "inputs": [...],
    "steps": [...],
    "totalDurationMs": 8200
  }
}
```

### `cstp.queryDecisions` — Extended
```json
{
  "query": "neuron model selection",
  "includeDeliberation": true
}
```

### `cstp.getDeliberationStats` — New Endpoint
```json
{
  "filters": { "category": "architecture" }
}
// Returns: avg steps, avg inputs, step_count vs success_rate, etc.
```

## Implementation Phases

### Phase 1: Schema + Storage
- Add `Deliberation` dataclass to `decision_service.py`
- Extend `RecordDecisionRequest` to accept deliberation
- Store in YAML alongside existing fields
- Backward compatible (field is optional for reads)

### Phase 2: Server-Side Auto-Capture
Server-side `DeliberationTracker` captures inputs automatically for both
JSON-RPC and MCP — zero client changes required.

**Tracking key:** `agent_id` (from auth token) for JSON-RPC, `session_id`
for MCP. Sub-agents have different agent_ids, so parallel agents are
naturally isolated.

**Hooks:**
- After `queryDecisions` succeeds → register query + result count as input
- After `checkGuardrails` succeeds → register action + allowed/blocked as input
- After `getDecision` succeeds → register decision lookup as input
- After `getReasonStats` succeeds → register stats snapshot as input
- On `recordDecision` → auto-build `Deliberation` from unconsumed inputs,
  attach to decision, clear tracker for that agent

**Edge case — sequential decisions by same agent:**
Inputs captured AFTER the last `recordDecision` belong to the next decision.
`recordDecision` consumes and clears tracked inputs atomically.

**Auto-generated steps:** The server creates `DeliberationStep` entries from
the call sequence (query → check → record), each referencing which inputs
they used. These are lower-fidelity than manual steps but provide baseline
provenance automatically.

**Merge behavior:** If `recordDecision` includes an explicit `deliberation`
field, tracked inputs are merged into it (appended, not overwritten).

**TTL:** Tracked inputs expire after 5 minutes (configurable). Periodic
cleanup sweeps expired entries.

### Phase 3: Search Integration
- Extend `queryDecisions` with `includeDeliberation` flag
- Return traces alongside decision summaries

### Phase 4: Analytics
- `cstp.getDeliberationStats` endpoint
- Step count vs outcome correlation
- Input diversity analysis
- Convergence speed patterns

### Phase 5: Membrain Bridge (Future — deferred until Membrain ready)
- Export deliberation traces as spike timing patterns
- Feed into Membrain SNN for associative learning

## Open Questions

~~1. **MCP auto-capture**: Should the MCP server maintain session-level 
   deliberation context, or is this purely client-side?~~
   **RESOLVED:** Server-side. `DeliberationTracker` tracks inputs per
   `agent_id` (JSON-RPC) or `session_id` (MCP). Sub-agents are naturally
   isolated by their auth identity. No client changes needed — the server
   hooks into query/check/record handlers and auto-captures inputs.
   `recordDecision` consumes tracked inputs and clears the tracker.

~~2. **Size limits**: Deliberation traces could get large. Cap at N steps/inputs?~~
   **RESOLVED:** No limits for now.

~~3. **Privacy**: Deliberation may contain sensitive intermediate thoughts. 
   Should there be a `redact` option?~~
   **RESOLVED:** No redaction. Full traces are stored.

## Related

- Minsky Ch 18: Parallel bundles — deliberation captures how independent 
  reasons converge
- Minsky Ch 21: Pronomes — inputs are like pronome assignments, steps are 
  action scripts operating on them
- F017: Hybrid retrieval — deliberation search benefits from both semantic 
  and keyword matching
