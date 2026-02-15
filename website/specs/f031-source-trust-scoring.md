# F031: Source Trust Scoring

## Source
- ai16z/elizaOS: "Trust Scores" to filter social signals for autonomous trading
- Minsky Ch 18: Parallel bundles - weight evidence by source reliability
- CSTP calibration: We already track decision accuracy, extend to source tracking

## Overview
Assign and maintain trust scores for information sources referenced in decisions. When querying past decisions, weight results by the reliability of their sources. Enables agents to distinguish high-signal from low-signal information and make better-calibrated decisions.

## Problem
Today, all decisions are treated equally in retrieval regardless of where their information came from. A decision based on peer-reviewed research and one based on a random tweet have the same weight. We need source provenance.

## API

### Recording Source Attribution

Enhanced `cstp.recordDecision`:

```json
{
  "method": "cstp.recordDecision",
  "params": {
    "decision": "Adopted HSM architecture for long-context processing",
    "confidence": 0.85,
    "category": "architecture",
    "stakes": "high",
    "sources": [
      {"id": "arxiv:2602.01234", "type": "paper", "name": "Hierarchical Shift Mixing", "url": "https://arxiv.org/abs/2602.01234"},
      {"id": "mit-media-lab", "type": "institution", "name": "MIT Media Lab"},
      {"id": "moltbook:user123", "type": "social", "name": "happy_milvus"}
    ]
  }
}
```

### New RPC Method: `cstp.getSourceTrust`

```json
{
  "method": "cstp.getSourceTrust",
  "params": {
    "sourceId": "moltbook:user123"
  }
}
```

### Response

```json
{
  "result": {
    "sourceId": "moltbook:user123",
    "type": "social",
    "name": "happy_milvus",
    "trustScore": 0.72,
    "decisionsReferenced": 8,
    "successRate": 0.75,
    "lastReferenced": "2026-02-10T15:00:00Z",
    "breakdown": {
      "accuracy": 0.75,
      "recency": 0.80,
      "consistency": 0.65
    }
  }
}
```

### Enhanced Query Results

`cstp.queryDecisions` response includes source trust:

```json
{
  "result": {
    "decisions": [{
      "id": "dec_abc",
      "decision": "...",
      "sourceWeightedScore": 0.91,
      "sources": [
        {"id": "arxiv:2602.01234", "trustScore": 0.95},
        {"id": "moltbook:user123", "trustScore": 0.72}
      ]
    }]
  }
}
```

## Trust Score Computation

```
trustScore = w1 * accuracy + w2 * recency + w3 * consistency

accuracy   = successful_outcomes / total_outcomes (from decisions referencing this source)
recency    = decay_factor(days_since_last_reference)
consistency = 1 - stddev(outcome_scores)
```

Default weights: `w1=0.5, w2=0.2, w3=0.3`

## Source Types

| Type | Example | Initial Trust | Notes |
|------|---------|--------------|-------|
| `paper` | arXiv, journals | 0.80 | High baseline, peer-reviewed |
| `institution` | MIT, Google Research | 0.75 | Track record weighted |
| `documentation` | Official docs, RFCs | 0.85 | Authoritative |
| `social` | Moltbook, Twitter | 0.50 | Starts neutral, earned |
| `agent` | Minski, CodeReviewer | 0.70 | Track by agent ID |
| `empirical` | Own experiments | 0.90 | Direct evidence |

## Use Cases
- **Moltbook engagement:** Weight posts by author trust score before engaging
- **Research briefings:** Flag stories from low-trust sources
- **Decision retrieval:** Surface high-trust decisions first
- **Agent collaboration:** Track which sub-agents give reliable reviews

## Acceptance Criteria
- [ ] `sources` field on `cstp.recordDecision`
- [ ] `cstp.getSourceTrust` RPC method
- [ ] `cstp.listSources` RPC method (with filters)
- [ ] Trust score computation from decision outcomes
- [ ] Source-weighted query results in `cstp.queryDecisions`
- [ ] MCP tools exposed
- [ ] Dashboard: Source trust leaderboard
- [ ] Automatic trust decay for stale sources
