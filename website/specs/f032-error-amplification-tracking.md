# F032: Error Amplification Tracking

## Source
MIT Media Lab / Google Research: "Towards a Science of Scaling Agent Systems" (Feb 4, 2026)
- Independent multi-agent: **17.2x** error amplification
- Centralized multi-agent: **4.4x** error amplification
- Single agent: **1x** baseline

## Overview
Track error propagation chains across multi-agent decision sequences. When a sub-agent's decision leads to a downstream failure, trace the causal chain back to identify amplification patterns. Enables the system to detect when agent collaboration is making things worse, not better.

## Problem
Today we track individual decision outcomes but not causal chains. If CodeReviewer approves a PR, DocsAgent updates docs based on it, and the feature turns out broken - we mark each decision independently. We can't see that the review failure **amplified** into a docs failure.

## API

### Decision Lineage

Enhanced `cstp.recordDecision`:

```json
{
  "method": "cstp.recordDecision",
  "params": {
    "decision": "Updated docs based on PR #42 review",
    "confidence": 0.85,
    "parentDecisionId": "dec_abc",
    "agentId": "docs-agent",
    "context": "CodeReviewer approved PR #42 (dec_abc). Updating docs accordingly."
  }
}
```

### New RPC Method: `cstp.getAmplificationChain`

```json
{
  "method": "cstp.getAmplificationChain",
  "params": {
    "decisionId": "dec_abc"
  }
}
```

### Response

```json
{
  "result": {
    "root": {
      "id": "dec_abc",
      "agent": "code-reviewer",
      "decision": "Approved PR #42",
      "outcome": "failure"
    },
    "chain": [
      {
        "id": "dec_def",
        "agent": "docs-agent",
        "decision": "Updated docs for PR #42",
        "outcome": "failure",
        "amplification": "inherited"
      },
      {
        "id": "dec_ghi",
        "agent": "main",
        "decision": "Merged PR #42",
        "outcome": "failure",
        "amplification": "cascaded"
      }
    ],
    "metrics": {
      "chainLength": 3,
      "amplificationFactor": 3.0,
      "affectedAgents": ["code-reviewer", "docs-agent", "main"],
      "architecture": "sequential_pipeline"
    }
  }
}
```

### New RPC Method: `cstp.getAmplificationStats`

```json
{
  "method": "cstp.getAmplificationStats",
  "params": {
    "windowDays": 30
  }
}
```

### Response

```json
{
  "result": {
    "averageAmplification": 2.3,
    "maxChainLength": 5,
    "totalChains": 12,
    "byArchitecture": {
      "single_agent": {"count": 45, "avgAmplification": 1.0},
      "sequential_pipeline": {"count": 8, "avgAmplification": 2.8},
      "centralized_parallel": {"count": 4, "avgAmplification": 1.6}
    },
    "topAmplifiers": [
      {"agent": "code-reviewer", "rootFailures": 3, "totalDownstream": 7}
    ],
    "recommendation": "CodeReviewer decisions are the most common root of amplification chains. Consider adding a second reviewer for high-stakes PRs."
  }
}
```

## Data Model

```yaml
# Added to decision records
parent_decision_id: "dec_abc"   # Decision this depends on
agent_id: "docs-agent"          # Which agent made this
chain_id: "chain_001"           # Group linked decisions
```

## Integration
- When `cstp.reviewDecision` marks a decision as failed, scan for child decisions
- Automatically propagate "inherited failure" markers down the chain
- Circuit breakers (F030) can trip based on amplification factor, not just failure count
- Task router (F029) can use historical amplification data to avoid bad architectures

## Acceptance Criteria
- [ ] `parentDecisionId` field on `cstp.recordDecision`
- [ ] `agentId` field on `cstp.recordDecision`
- [ ] Chain detection on failure review
- [ ] `cstp.getAmplificationChain` RPC method
- [ ] `cstp.getAmplificationStats` RPC method
- [ ] Amplification factor calculation
- [ ] Dashboard: Chain visualization (Mermaid)
- [ ] MCP tools exposed
- [ ] Integration with circuit breakers (F030)
