# F037: Collective Innovation Protocol

> **Status:** Proposed
> **Target:** v1.0.0 (Multi-Agent Cognition Network)
> **Source:** README roadmap, Cisco Outshift IoC
> **Depends on:** F036 (Reasoning Continuity), F031 (Source Trust Scoring)

## Overview
Enable multiple agents to collaboratively reason about novel problems. Instead of one agent making a decision in isolation, a group of agents contribute perspectives, challenge assumptions, and converge on a solution - with the full deliberation captured as a structured multi-agent trace.

## Problem
Current CSTP is single-agent: one agent queries, checks guardrails, and records. Even with sub-agents, each decides independently. There's no protocol for structured multi-agent deliberation where agents explicitly build on, challenge, or refine each other's reasoning.

## Concept

### Deliberation Session
```json
{
  "method": "cstp.openDeliberation",
  "params": {
    "topic": "Should we adopt HSM architecture for long-context processing?",
    "category": "architecture",
    "stakes": "high",
    "participants": ["emerson", "minski", "code-reviewer"],
    "protocol": "structured_debate"
  }
}
```

### Contribution Types
| Type | Purpose | Example |
|------|---------|---------|
| `propose` | Initial proposal | "We should use HSM because..." |
| `support` | Add supporting evidence | "MIT research confirms 81% improvement" |
| `challenge` | Raise concerns | "HSM hasn't been tested at scale" |
| `synthesize` | Combine perspectives | "HSM for parallel, attention for sequential" |
| `vote` | Signal position | Confidence-weighted agreement/disagreement |

### Deliberation Flow
```
1. OPEN: Emerson proposes topic
2. PROPOSE: Emerson: "Adopt HSM for long-context" (confidence: 0.80)
3. SUPPORT: Minski: "MIT data supports this" (confidence: 0.85)
4. CHALLENGE: CodeReviewer: "No production benchmarks" (confidence: 0.70)
5. SYNTHESIZE: Emerson: "HSM for parallel + attention fallback" (confidence: 0.82)
6. VOTE: All agents signal confidence
7. CLOSE: Decision recorded with full multi-agent trace
```

### Resolution
```json
{
  "result": {
    "decision": "Adopt HSM with attention fallback for sequential tasks",
    "confidence": 0.82,
    "consensusType": "convergent",
    "participantVotes": {
      "emerson": {"position": "support", "confidence": 0.85},
      "minski": {"position": "support", "confidence": 0.80},
      "code-reviewer": {"position": "conditional_support", "confidence": 0.70}
    },
    "dissent": ["No production benchmarks yet - revisit after pilot"]
  }
}
```

## Protocols

### Structured Debate
Round-robin: propose -> support/challenge -> synthesize -> vote. Best for high-stakes architectural decisions.

### Advisory Panel
One agent proposes, others advise. Proposer makes final call. Best for decisions with a clear owner.

### Consensus
All agents must agree above threshold. Best for shared-impact decisions.

## API

### `cstp.openDeliberation`
Start a multi-agent deliberation session.

### `cstp.contribute`
Add a contribution (propose/support/challenge/synthesize/vote).

### `cstp.closeDeliberation`
Finalize and record the collective decision.

### `cstp.getDeliberation`
Retrieve full deliberation history.

## Integration
- F031 Source Trust weights each agent's contribution by their track record
- F032 Error Amplification tracks whether collective decisions outperform solo ones
- F036 Reasoning Continuity enables async deliberation across sessions
- F030 Circuit Breakers can trigger mandatory deliberation for high-stakes decisions

## Acceptance Criteria
- [ ] `cstp.openDeliberation` RPC method
- [ ] `cstp.contribute` RPC method (all 5 contribution types)
- [ ] `cstp.closeDeliberation` with consensus calculation
- [ ] `cstp.getDeliberation` RPC method
- [ ] Multi-agent decision trace stored in CSTP
- [ ] MCP tools exposed
- [ ] Dashboard: Deliberation timeline view
- [ ] At least 3 resolution protocols (debate, advisory, consensus)
