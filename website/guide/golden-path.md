# Golden Path — End-to-End Walkthrough

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

## 2. Record a Decision

Log your first decision — an agent choosing a caching strategy.

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
      ]
    },
    "id": 1
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "id": "dec_abc12345",
        "decision": "Use Redis for session caching instead of in-memory store",
        "confidence": 0.85,
        "category": "architecture",
        "stakes": "medium",
        "timestamp": "2026-02-09T12:00:00Z",
        "status": "recorded"
    },
    "id": 1
}
```

> Save the `id` value — you'll need it in step 6.

---

## 3. Query Similar Decisions

Search for decisions related to "caching" to see what's been recorded.

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
    "id": 2
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "decisions": [
            {
                "id": "dec_abc12345",
                "decision": "Use Redis for session caching instead of in-memory store",
                "confidence": 0.85,
                "category": "architecture",
                "similarity": 0.92,
                "timestamp": "2026-02-09T12:00:00Z"
            }
        ],
        "total": 1,
        "retrievalMode": "hybrid"
    },
    "id": 2
}
```

The decision you just recorded appears with a high similarity score.

---

## 4. Check Guardrails (See a Block)

Try a high-stakes action with low confidence — the guardrails should block it.

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
    "id": 3
  }' | python3 -m json.tool
```

**Expected output:**

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
    "id": 3
}
```

The `"allowed": false` response means the guardrail fired correctly. An agent receiving this should pause and gather more information before proceeding.

---

## 5. Record Another Decision

Add a second decision so there's enough data for calibration.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.recordDecision",
    "params": {
      "decision": "Use PostgreSQL full-text search instead of Elasticsearch for v1",
      "confidence": 0.70,
      "category": "architecture",
      "stakes": "medium",
      "context": "Need search functionality but want to avoid operational overhead of a separate Elasticsearch cluster for initial launch.",
      "reasons": [
        {"type": "analysis", "text": "PostgreSQL FTS handles our current scale (< 100k docs) without extra infra"},
        {"type": "elimination", "text": "Elasticsearch adds operational complexity we cannot staff for at launch"}
      ]
    },
    "id": 4
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "id": "dec_def67890",
        "decision": "Use PostgreSQL full-text search instead of Elasticsearch for v1",
        "confidence": 0.70,
        "category": "architecture",
        "stakes": "medium",
        "timestamp": "2026-02-09T12:05:00Z",
        "status": "recorded"
    },
    "id": 4
}
```

---

## 6. Review an Outcome

Go back to the first decision and record what actually happened. Replace `dec_abc12345` with the ID from step 2.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.reviewOutcome",
    "params": {
      "id": "dec_abc12345",
      "outcome": "success",
      "result": "Redis caching reduced p99 latency from 450ms to 80ms. Shared state works correctly across 3 instances. No cache-loss incidents in 2 weeks of production use."
    },
    "id": 5
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "id": "dec_abc12345",
        "outcome": "success",
        "result": "Redis caching reduced p99 latency from 450ms to 80ms. Shared state works correctly across 3 instances. No cache-loss incidents in 2 weeks of production use.",
        "reviewedAt": "2026-02-09T12:10:00Z"
    },
    "id": 5
}
```

This closes the feedback loop — the system now knows this 0.85-confidence decision turned out well.

---

## 7. Check Calibration

See how well your confidence scores match actual outcomes.

```bash
curl -s -X POST $CSTP_URL/cstp \
  -H "Authorization: Bearer $CSTP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.getStats",
    "params": {},
    "id": 6
  }' | python3 -m json.tool
```

**Expected output:**

```json
{
    "jsonrpc": "2.0",
    "result": {
        "totalDecisions": 2,
        "reviewedDecisions": 1,
        "calibration": {
            "buckets": [
                {
                    "range": "0.8-0.9",
                    "count": 1,
                    "successRate": 1.0,
                    "avgConfidence": 0.85
                }
            ],
            "brierScore": 0.02,
            "overconfidenceIndex": 0.0
        },
        "byCategory": {
            "architecture": 2
        },
        "byStakes": {
            "medium": 2
        }
    },
    "id": 6
}
```

With more reviewed decisions, the calibration data becomes meaningful. A `brierScore` closer to 0 means your confidence scores are well-calibrated.

---

## 8. Check Drift

Monitor whether decision patterns are shifting over time.

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
        "reasonTypes": {
            "analysis": {
                "count": 3,
                "percentage": 0.60
            },
            "pattern": {
                "count": 1,
                "percentage": 0.20
            },
            "elimination": {
                "count": 1,
                "percentage": 0.20
            }
        },
        "totalReasons": 5,
        "avgReasonsPerDecision": 2.0,
        "diversityScore": 0.72
    },
    "id": 7
}
```

A healthy system shows diverse reason types. If every decision relies on a single reason type, the agent may be operating on brittle logic — the `diversityScore` helps surface this.

---

## What's Next?

- **[Decision Protocol](/guide/decision-protocol)** — Understand the full query → check → record → review lifecycle
- **[Guardrails](/guide/guardrails)** — Configure rules that protect against bad decisions
- **[MCP Integration](/guide/mcp-integration)** — Connect your AI agent via Model Context Protocol
- **[Bridge-Definitions](/guide/bridge-definitions)** — Link structure to purpose for richer recall
