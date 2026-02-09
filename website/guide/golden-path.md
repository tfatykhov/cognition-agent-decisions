# Golden Path - End-to-End Walkthrough

Follow these steps to verify your Cognition Engines installation and explore the full decision lifecycle. Every command is copy-paste ready.

> All examples assume the CSTP server is running at `http://localhost:9991` (the default port, configurable via `CSTP_PORT`). Set your token first:

```bash
export CSTP_TOKEN="your-api-token"
export CSTP_URL="http://localhost:9991"
```

---

## 1. Health Check

Confirm the server is up and reachable.

```bash
curl -s $CSTP_URL/health | python3 -m json.tool
```

**Expected output:**

```json
{
    "status": "healthy",
    "version": "0.10.0",
    "uptime_seconds": 1234.5,
    "decision_count": 0
}
```

If you see `"status": "healthy"`, you're good to go.

---

## 2. Query Before Deciding

Always search for similar past decisions before making a new one. This builds your deliberation trace automatically.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.queryDecisions",
    "params": {
      "query": "caching strategy for web application",
      "retrievalMode": "hybrid",
      "limit": 5
    },
    "id": 1
  }' | python3 -m json.tool
```

**Expected output (first run, no decisions yet):**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "decisions": [],
        "total": 0,
        "query": "caching strategy for web application",
        "queryTimeMs": 245,
        "agent": "your-agent-id",
        "retrievalMode": "hybrid",
        "scores": {}
    },
    "id": 1
}
```

**With existing decisions**, results include hybrid scoring (semantic + keyword):

```json
{
    "decisions": [
        {
            "id": "d44d6de0",
            "title": "Use Redis for session caching",
            "category": "architecture",
            "confidence": 0.85,
            "stakes": "medium",
            "status": "pending",
            "date": "2026-02-09",
            "distance": 0.3
        }
    ],
    "scores": {
        "d44d6de0": {
            "semantic": 1.0,
            "keyword": 0.0,
            "combined": 0.7
        }
    }
}
```

> **Key:** The server auto-captures this query as a **deliberation input** for whatever decision you record next.

---

## 3. Check Guardrails

Before acting, verify the guardrails allow it. Try a high-stakes action with low confidence - the guardrails should block it.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.checkGuardrails",
    "params": {
      "action": {
        "description": "Deploy untested model to production",
        "category": "architecture",
        "stakes": "high",
        "confidence": 0.3
      }
    },
    "id": 2
  }' | python3 -m json.tool
```

**Expected output (blocked):**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "allowed": false,
        "violations": [
            {
                "rule": "no-high-stakes-low-confidence",
                "message": "High-stakes actions require confidence >= 0.5",
                "stakes": "high",
                "confidence": 0.3
            }
        ]
    },
    "id": 2
}
```

`"allowed": false` means the guardrail fired. An agent receiving this should pause and gather more information.

> **Key:** This check is also auto-captured as a **deliberation input** - the server tracks that you checked before deciding.

---

## 4. Capture Your Reasoning

Record your chain-of-thought as you work through the problem. These reasoning steps auto-attach to whatever decision you record next.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.recordThought",
    "params": {
      "text": "In-memory caching fails on restart. Redis adds a dependency but gives persistence and shared state across instances."
    },
    "id": 3
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "success": true,
        "mode": "pre-decision",
        "agent_id": "your-agent-id"
    },
    "id": 3
}
```

You can call `recordThought` multiple times - each call captures a timestamped reasoning step. All thoughts accumulate and auto-attach when you record a decision.

> **Key:** These reasoning steps become part of the deliberation trace, capturing *how* you decided - not just *what*.

---

## 5. Record a Decision

Now log the decision. Include tags and a pattern for better retrieval. The server automatically attaches:
- **Deliberation trace** from your query (step 2), guardrail check (step 3), and reasoning (step 4)
- **Bridge-definition** extracted from your decision text (structure + function)
- **Related decisions** linked from query results
- **Quality score** measuring recording completeness

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.recordDecision",
    "params": {
      "decision": "Use Redis for session caching instead of in-memory store",
      "confidence": 0.85,
      "category": "architecture",
      "stakes": "medium",
      "context": "Evaluating caching strategies for multi-instance deployment. In-memory fails on restart; Redis provides persistence and shared state across instances.",
      "reasons": [
        {"type": "analysis", "text": "Redis survives process restarts and supports multi-instance deployments"},
        {"type": "pattern", "text": "Previous projects had cache-loss bugs with in-memory stores"}
      ],
      "tags": ["caching", "infrastructure", "redis"],
      "pattern": "Choose stateless-compatible infrastructure for multi-instance deployments"
    },
    "id": 4
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "success": true,
        "id": "dec_abc12345",
        "path": "/app/decisions/2026/02/2026-02-09-decision-dec_abc12345.yaml",
        "indexed": true,
        "timestamp": "2026-02-09T12:00:00.000000+00:00",
        "deliberation_auto": true,
        "deliberation_inputs_count": 3,
        "bridge_auto": true,
        "bridge_method": "both-extracted",
        "related_count": 2,
        "quality": {
            "score": 0.95,
            "suggestions": []
        }
    },
    "id": 4
}
```

Notice the auto-captured fields:
- **`deliberation_auto: true`** - The server built a deliberation trace automatically
- **`deliberation_inputs_count: 3`** - It captured your query, guardrail check, and reasoning steps
- **`bridge_auto: true`** - A bridge-definition (structure + function) was extracted
- **`bridge_method`** - How the bridge was extracted (`rule`, `llm`, or `both-extracted`)
- **`related_count: 2`** - Related decisions were linked from your query results
- **`quality`** - Score (0.0-1.0) measuring recording completeness, with improvement suggestions
- **`indexed: true`** - The decision is searchable in ChromaDB immediately

> Save the `id` value - you'll need it in step 7.

---

## 6. Inspect the Full Decision

Retrieve the decision to see everything the server captured, including the bridge-definition, reasoning trace, and quality score.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.getDecision",
    "params": {
      "id": "dec_abc12345"
    },
    "id": 5
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "found": true,
        "decision": {
            "id": "dec_abc12345",
            "summary": "Use Redis for session caching instead of in-memory store",
            "decision": "Use Redis for session caching instead of in-memory store",
            "category": "architecture",
            "confidence": 0.85,
            "stakes": "medium",
            "status": "pending",
            "date": "2026-02-09T12:00:00.000000+00:00",
            "context": "Evaluating caching strategies for multi-instance deployment. In-memory fails on restart; Redis provides persistence and shared state across instances.",
            "tags": ["caching", "infrastructure", "redis"],
            "pattern": "Choose stateless-compatible infrastructure for multi-instance deployments",
            "reasons": [
                {
                    "type": "analysis",
                    "text": "Redis survives process restarts and supports multi-instance deployments",
                    "strength": 0.8
                },
                {
                    "type": "pattern",
                    "text": "Previous projects had cache-loss bugs with in-memory stores",
                    "strength": 0.8
                }
            ],
            "deliberation": {
                "inputs": [
                    {
                        "id": "q-5af3c565",
                        "text": "Queried 'caching strategy for web application': 0 results (hybrid)",
                        "source": "cstp:queryDecisions",
                        "timestamp": "2026-02-09T11:58:00.000000+00:00"
                    },
                    {
                        "id": "g-81fdd447",
                        "text": "Checked 'Deploy untested model to production': blocked",
                        "source": "cstp:checkGuardrails",
                        "timestamp": "2026-02-09T11:59:00.000000+00:00"
                    },
                    {
                        "id": "r-3c7a9f12",
                        "text": "In-memory caching fails on restart. Redis adds a dependency but gives persistence and shared state across instances.",
                        "source": "cstp:recordThought",
                        "timestamp": "2026-02-09T11:59:30.000000+00:00"
                    }
                ],
                "steps": [
                    {
                        "step": 1,
                        "thought": "Queried 'caching strategy for web application': 0 results (hybrid)",
                        "inputs_used": ["q-5af3c565"],
                        "timestamp": "2026-02-09T11:58:00.000000+00:00",
                        "type": "analysis"
                    },
                    {
                        "step": 2,
                        "thought": "Checked 'Deploy untested model to production': blocked",
                        "inputs_used": ["g-81fdd447"],
                        "timestamp": "2026-02-09T11:59:00.000000+00:00",
                        "type": "constraint"
                    },
                    {
                        "step": 3,
                        "thought": "In-memory caching fails on restart. Redis adds a dependency but gives persistence and shared state across instances.",
                        "inputs_used": ["r-3c7a9f12"],
                        "timestamp": "2026-02-09T11:59:30.000000+00:00",
                        "type": "reasoning"
                    }
                ],
                "total_duration_ms": 41
            },
            "bridge": {
                "structure": "Use Redis for session caching instead of in-memory store",
                "function": "Redis survives process restarts and supports multi-instance deployments"
            },
            "related_to": [
                {
                    "id": "dec_xyz789",
                    "summary": "Use PostgreSQL connection pooling for multi-instance deployment",
                    "distance": 0.25
                }
            ],
            "recorded_by": "your-agent-id"
        }
    },
    "id": 4
}
```

The full decision includes everything the server auto-captured:
- **`deliberation`** - The complete trace: `inputs` (what you queried/checked/thought), `steps` (how they were processed), and `total_duration_ms`. Reasoning steps (type `"reasoning"`) capture your chain-of-thought.
- **`tags`** - Reusable keywords for cross-domain retrieval
- **`pattern`** - Abstract principle this decision represents (helps find similar decisions across projects)
- **`bridge`** - Structure (what it looks like) and function (what it solves), from Minsky Ch 12
- **`related_to`** - Linked decisions from your pre-decision query, with semantic `distance` scores
- **`reasons`** - Each reason has an auto-assigned `strength` score

---

## 7. Review an Outcome

Close the feedback loop by recording what actually happened. Replace `dec_abc12345` with your ID from step 4.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.reviewDecision",
    "params": {
      "id": "dec_abc12345",
      "outcome": "success",
      "result": "Redis caching reduced p99 latency from 450ms to 80ms. Shared state works correctly across 3 instances."
    },
    "id": 5
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "success": true,
        "id": "dec_abc12345",
        "path": "/app/decisions/2026/02/2026-02-09-decision-dec_abc12345.yaml",
        "status": "reviewed",
        "reviewedAt": "2026-02-09T12:10:00.000000+00:00",
        "reindexed": true
    },
    "id": 5
}
```

The system now knows this 0.85-confidence decision succeeded. This data feeds directly into calibration.

---

## 8. Check Calibration

See how well your confidence scores match actual outcomes.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.getCalibration",
    "params": {},
    "id": 6
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "overall": {
            "brierScore": 0.02,
            "accuracy": 0.989,
            "totalDecisions": 44,
            "reviewedDecisions": 44,
            "calibrationGap": 0.103,
            "interpretation": "underconfident"
        },
        "byConfidenceBucket": [
            {
                "bucket": "0.9-1.0",
                "decisions": 27,
                "successRate": 1.0,
                "expectedRate": 0.95,
                "gap": 0.05,
                "interpretation": "well_calibrated"
            },
            {
                "bucket": "0.7-0.9",
                "decisions": 17,
                "successRate": 0.97,
                "expectedRate": 0.8,
                "gap": 0.17,
                "interpretation": "underconfident"
            }
        ],
        "recommendations": [
            {
                "type": "brier_score",
                "message": "Excellent Brier score (0.02). Your predictions are very accurate.",
                "severity": "info"
            }
        ],
        "confidenceStats": {
            "mean": 0.886,
            "stdDev": 0.062,
            "min": 0.72,
            "max": 1.0,
            "count": 44
        }
    },
    "id": 6
}
```

Key metrics:
- **Brier score** closer to 0 = better calibrated predictions
- **calibrationGap** shows systematic over/underconfidence
- **recommendations** provide actionable advice
- **confidenceStats** tracks variance (low stdDev = you're not varying enough)

---

## 9. Check Reason Stats

See which reasoning patterns predict success, and whether your reasoning is diverse enough.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.getReasonStats",
    "params": {},
    "id": 7
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "byReasonType": [
            {
                "reasonType": "analysis",
                "totalUses": 93,
                "reviewedUses": 34,
                "successCount": 33,
                "successRate": 0.985,
                "avgConfidence": 0.901,
                "avgStrength": 0.767,
                "brierScore": 0.0226
            },
            {
                "reasonType": "pattern",
                "totalUses": 70,
                "reviewedUses": 26,
                "successCount": 25,
                "successRate": 0.981,
                "avgConfidence": 0.876,
                "avgStrength": 0.71,
                "brierScore": 0.0252
            },
            {
                "reasonType": "empirical",
                "totalUses": 28,
                "reviewedUses": 17,
                "successCount": 16,
                "successRate": 0.971,
                "avgConfidence": 0.906,
                "avgStrength": 0.736,
                "brierScore": 0.0178
            }
        ],
        "diversity": {
            "avgTypesPerDecision": 1.98,
            "avgReasonsPerDecision": 2.05,
            "diversityBuckets": [
                {
                    "distinctReasonTypes": 1,
                    "totalDecisions": 29,
                    "successRate": 1.0,
                    "avgConfidence": 0.9
                },
                {
                    "distinctReasonTypes": 2,
                    "totalDecisions": 60,
                    "successRate": 1.0,
                    "avgConfidence": 0.899
                },
                {
                    "distinctReasonTypes": 3,
                    "totalDecisions": 25,
                    "successRate": 0.962,
                    "avgConfidence": 0.848
                }
            ]
        },
        "recommendations": [
            {
                "type": "unused_types",
                "message": "Never-used reason types: elimination, intuition. Consider whether these perspectives could strengthen decisions.",
                "severity": "info"
            }
        ],
        "totalDecisions": 115,
        "reviewedDecisions": 43
    },
    "id": 7
}
```

A healthy system shows:
- **Diverse reason types** - not everything relying on `analysis` alone
- **Multiple reasons per decision** (parallel bundles > serial chains, per Minsky Ch 18)
- **Per-type Brier scores** - which reasoning patterns predict outcomes best

---

## The Full Lifecycle

What you just walked through:

```
Query   →  "What solved problems like this?"        (auto-captured as deliberation input)
Check   →  "Am I allowed to do this?"                (auto-captured as deliberation input)
Think   →  "Here's my reasoning..."                  (auto-captured as deliberation reasoning step)
Record  →  "Here's what I decided and why"           (auto: deliberation + bridge + related + quality)
Inspect → "Show me everything about this decision"   (bridge, reasons, tags, pattern, reasoning trace)
Review  →  "Here's what actually happened"           (closes the feedback loop)
Stats   →  "How well am I calibrated?"               (Brier score, recommendations)
Reason  →  "Which reasoning patterns work best?"     (per-type success rates, diversity)
```

Zero client-side work needed for deliberation traces, bridge-definitions, quality scores, or related decisions - the server handles it all.

---

## What's Next?

- **[Decision Protocol](/guide/decision-protocol)** - Understand the full query → check → record → review lifecycle
- **[Deliberation Traces](/guide/deliberation-traces)** - How automatic trace capture works
- **[Bridge-Definitions](/guide/bridge-definitions)** - Two-path search via structure and function (Minsky Ch 12)
- **[Guardrails](/guide/guardrails)** - Configure rules that protect against bad decisions
- **[MCP Integration](/guide/mcp-integration)** - Connect your AI agent via Model Context Protocol
