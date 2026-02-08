# CSTP API Reference

The **Cognition State Transfer Protocol** (CSTP) is a JSON-RPC 2.0 API exposed over HTTP. All method calls use `POST /cstp` with a bearer token in the `Authorization` header.

---

## Protocol Basics

### Request Format

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.<methodName>",
  "params": { ... },
  "id": "unique-request-id"
}
```

### Response Format — Success

```json
{
  "jsonrpc": "2.0",
  "result": { ... },
  "id": "unique-request-id"
}
```

### Response Format — Error

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32003,
    "message": "Query failed: ..."
  },
  "id": "unique-request-id"
}
```

### Authentication

All requests must include a bearer token:

```
Authorization: Bearer <agent>:<token>
```

The agent name is extracted from the token pair and included in audit trails.

### Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | Parse Error | Malformed JSON |
| -32600 | Invalid Request | Missing required fields |
| -32601 | Method Not Found | Unknown CSTP method |
| -32602 | Invalid Params | Parameter validation failed |
| -32603 | Internal Error | Unexpected server error |
| -32002 | Rate Limited | Too many requests |
| -32003 | Query Failed | Error during decision query |
| -32004 | Guardrail Eval Failed | Error evaluating guardrails |
| -32005 | Record Failed | Error recording decision |
| -32006 | Review Failed | Error reviewing decision |
| -32007 | Decision Not Found | Decision ID not found |
| -32008 | Attribution Failed | Error attributing outcomes |

---

## Non-Authenticated Endpoints

### `GET /health`

Health check with uptime tracking.

**Response:**

```json
{
  "status": "ok",
  "version": "0.9.0",
  "agent": "cognition-engines",
  "uptime_seconds": 3600,
  "timestamp": "2026-02-07T12:00:00Z"
}
```

### `GET /.well-known/agent.json`

A2A agent discovery card.

**Response:**

```json
{
  "name": "cognition-engines",
  "description": "Decision Intelligence Service",
  "version": "0.9.0",
  "url": "http://localhost:8100",
  "capabilities": ["queryDecisions", "checkGuardrails", "recordDecision", "reviewDecision", "getCalibration"],
  "protocol": "cstp",
  "protocolVersion": "0.9.0"
}
```

---

## CSTP Methods

### `cstp.queryDecisions` — Search Decision Memory

Search for semantically similar decisions using vector similarity, keyword matching, or hybrid search.

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | ✅ | — | Natural language search query |
| `limit` | int | ❌ | 10 | Maximum results |
| `include_reasons` | bool | ❌ | false | Include decision reasons in results |
| `retrieval_mode` | string | ❌ | `"semantic"` | `"semantic"`, `"keyword"`, or `"hybrid"` |
| `hybrid_weight` | float | ❌ | 0.7 | Semantic weight in hybrid mode (0.0–1.0) |
| `filters` | object | ❌ | `{}` | Filtering criteria (see below) |

**Filter object:**

| Field | Type | Description |
|-------|------|-------------|
| `category` | string | Filter by decision category |
| `min_confidence` | float | Minimum confidence (0.0–1.0) |
| `max_confidence` | float | Maximum confidence (0.0–1.0) |
| `stakes` | string[] | Filter by stakes level (`"low"`, `"medium"`, `"high"`, `"critical"`) |
| `status` | string[] | Filter by status (`"pending"`, `"reviewed"`) |
| `project` | string | Filter by project name |
| `feature` | string | Filter by feature name |
| `pr` | int | Filter by PR number |
| `has_outcome` | bool | Only reviewed (true) or pending (false) |
| `date_after` | string | ISO 8601 minimum date |
| `date_before` | string | ISO 8601 maximum date |

**Example request:**

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.queryDecisions",
  "params": {
    "query": "database selection for agent memory storage",
    "limit": 5,
    "retrieval_mode": "hybrid",
    "include_reasons": true,
    "filters": {
      "category": "architecture",
      "min_confidence": 0.6
    }
  },
  "id": "q-001"
}
```

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "decisions": [
      {
        "id": "2026-01-15-decision-a1b2c3",
        "title": "Use ChromaDB for semantic memory",
        "category": "architecture",
        "confidence": 0.85,
        "stakes": "high",
        "status": "reviewed",
        "outcome": "success",
        "date": "2026-01-15",
        "distance": 0.234,
        "reasons": ["Lightweight vector DB", "HTTP API", "Good Python support"]
      }
    ],
    "total": 1,
    "query": "database selection for agent memory storage",
    "query_time_ms": 142,
    "agent": "cognition-engines",
    "retrieval_mode": "hybrid",
    "scores": {
      "2026-01-15-decision-a1b2c3": {
        "semantic": 0.892,
        "keyword": 0.654,
        "combined": 0.821
      }
    }
  },
  "id": "q-001"
}
```

---

### `cstp.checkGuardrails` — Evaluate Policy Rules

Check a proposed action against all active guardrails.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `action` | object | ✅ | Action context |
| `action.description` | string | ✅ | What the agent intends to do |
| `action.category` | string | ❌ | Decision category |
| `action.stakes` | string | ❌ | Stakes level (default: `"medium"`) |
| `action.confidence` | float | ❌ | Agent's confidence (0.0–1.0) |
| `action.context` | object | ❌ | Arbitrary context fields for condition matching |
| `agent` | object | ❌ | Agent identity |
| `agent.id` | string | ❌ | Agent identifier |
| `agent.url` | string | ❌ | Agent callback URL |

**Example request:**

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.checkGuardrails",
  "params": {
    "action": {
      "description": "Deploy new ML pipeline to production",
      "category": "deployment",
      "stakes": "high",
      "confidence": 0.75,
      "context": {
        "affects_production": true,
        "code_review_completed": false
      }
    }
  },
  "id": "g-001"
}
```

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "allowed": false,
    "violations": [
      {
        "guardrail_id": "no-production-without-review",
        "name": "Production changes require code review",
        "message": "Production changes require completed code review",
        "severity": "block",
        "suggestion": "Complete code review before proceeding"
      }
    ],
    "warnings": [],
    "evaluated": 3,
    "evaluated_at": "2026-02-07T12:00:00Z",
    "agent": "cognition-engines"
  },
  "id": "g-001"
}
```

---

### `cstp.listGuardrails` — List Active Guardrails

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `scope` | string | ❌ | Filter by scope/project |

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "guardrails": [
      {
        "id": "no-production-without-review",
        "description": "Production changes require code review",
        "action": "block",
        "scope": null,
        "conditions": 1,
        "requirements": 1
      }
    ],
    "total": 3
  },
  "id": "lg-001"
}
```

---

### `cstp.recordDecision` — Record a Decision

Record a new decision with full metadata, reasoning trace, and optional guardrail pre-check.

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `decision` | string | ✅ | — | Decision text / title |
| `confidence` | float | ✅ | — | Confidence level (0.0–1.0) |
| `category` | string | ✅ | — | Category (e.g., `"architecture"`, `"trading"`) |
| `stakes` | string | ❌ | `"medium"` | `"low"`, `"medium"`, `"high"`, `"critical"` |
| `context` | string | ❌ | — | Free-text context |
| `reasons` | array | ❌ | `[]` | List of reason objects |
| `reasons[].type` | string | — | — | Reason type: `"technical"`, `"risk"`, `"constraint"`, etc. |
| `reasons[].text` | string | — | — | Reason text |
| `reasons[].strength` | float | — | — | Weight (0.0–1.0) |
| `alternatives_considered` | array | ❌ | `[]` | List of rejected alternatives |
| `review_in` | string | ❌ | `"7d"` | Review cadence: `"24h"`, `"3d"`, `"7d"`, `"30d"` |
| `project` | object | ❌ | — | Project context |
| `project.name` | string | — | — | Project name |
| `project.feature` | string | — | — | Feature name |
| `project.pr` | int | — | — | Pull request number |
| `project.files` | array | — | — | Affected files |
| `reasoning_trace` | array | ❌ | — | Step-by-step reasoning |
| `pre_decision_protocol` | object | ❌ | — | Track whether query + guardrail check were performed |

**Example request:**

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.recordDecision",
  "params": {
    "decision": "Use PostgreSQL for persistent state storage",
    "confidence": 0.82,
    "category": "architecture",
    "stakes": "high",
    "context": "Evaluating database options for agent state persistence",
    "reasons": [
      {"type": "technical", "text": "ACID compliance for critical state", "strength": 0.9},
      {"type": "risk", "text": "Team has PostgreSQL experience", "strength": 0.7}
    ],
    "alternatives_considered": ["SQLite", "Redis", "MongoDB"],
    "project": {
      "name": "CryptoTrader",
      "feature": "state-persistence",
      "pr": 42
    }
  },
  "id": "r-001"
}
```

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "decision_id": "2026-02-07-decision-a1b2c3d4",
    "path": "decisions/2026/02/2026-02-07-decision-a1b2c3d4.yaml",
    "indexed": true,
    "guardrails_checked": false,
    "message": "Decision recorded and indexed"
  },
  "id": "r-001"
}
```

---

### `cstp.reviewDecision` — Record Outcome

Record the actual outcome of a previously recorded decision.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `decision_id` | string | ✅ | Decision ID (full or prefix) |
| `outcome` | string | ✅ | `"success"`, `"failure"`, `"partial"`, `"abandoned"` |
| `actual_result` | string | ✅ | Description of what actually happened |
| `lessons` | string | ❌ | Lessons learned |

**Example request:**

```json
{
  "jsonrpc": "2.0",
  "method": "cstp.reviewDecision",
  "params": {
    "decision_id": "2026-02-07-decision-a1b2c3d4",
    "outcome": "success",
    "actual_result": "PostgreSQL has been stable for 30 days with zero data loss",
    "lessons": "Connection pooling was needed sooner than expected"
  },
  "id": "rv-001"
}
```

---

### `cstp.getCalibration` — Calibration Statistics

Compute confidence calibration metrics for reviewed decisions.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `agent` | string | ❌ | Filter by recording agent |
| `category` | string | ❌ | Filter by decision category |
| `stakes` | string | ❌ | Filter by stakes level |
| `project` | string | ❌ | Filter by project |
| `feature` | string | ❌ | Filter by feature |
| `window` | string | ❌ | Time window: `"30d"`, `"60d"`, `"90d"` |

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "total_decisions": 47,
    "reviewed_decisions": 32,
    "overall": {
      "brier_score": 0.142,
      "accuracy": 0.78,
      "calibration_gap": 0.05,
      "interpretation": "Good calibration"
    },
    "buckets": [
      {"range": "0.0-0.2", "decisions": 2, "predicted": 0.15, "actual": 0.0, "brier": 0.023},
      {"range": "0.2-0.4", "decisions": 5, "predicted": 0.32, "actual": 0.4, "brier": 0.051},
      {"range": "0.4-0.6", "decisions": 8, "predicted": 0.52, "actual": 0.5, "brier": 0.098},
      {"range": "0.6-0.8", "decisions": 10, "predicted": 0.72, "actual": 0.7, "brier": 0.089},
      {"range": "0.8-1.0", "decisions": 7, "predicted": 0.88, "actual": 0.86, "brier": 0.021}
    ],
    "confidence_stats": {
      "mean": 0.64,
      "std_dev": 0.21,
      "min": 0.12,
      "max": 0.95,
      "habituation_detected": false
    },
    "recommendations": [
      {"type": "improvement", "message": "Consider more decisions in 0.0-0.2 range", "severity": "low"}
    ]
  },
  "id": "c-001"
}
```

---

### `cstp.attributeOutcomes` — Automatic Outcome Attribution

Automatically attribute outcomes to decisions based on PR stability (age).

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `project` | string | ✅ | — | Project name |
| `since` | string | ❌ | `"30d"` | Look-back window |
| `stability_days` | int | ❌ | 7 | Days before PR is considered stable |
| `dry_run` | bool | ❌ | false | Preview only, don't modify files |

---

### `cstp.checkDrift` — Calibration Drift Detection

Compare recent calibration against historical baseline to detect degradation.

**Parameters:**

| Param | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `category` | string | ❌ | — | Filter by category |
| `project` | string | ❌ | — | Filter by project |
| `brier_threshold` | float | ❌ | 0.05 | Brier score change threshold for alerts |
| `accuracy_threshold` | float | ❌ | 0.1 | Accuracy change threshold for alerts |

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "drift_detected": true,
    "alerts": [
      {
        "type": "brier_degradation",
        "recent_value": 0.22,
        "historical_value": 0.14,
        "change_pct": 57.1,
        "severity": "warning"
      }
    ],
    "recent_period": "30d",
    "historical_period": "90d+",
    "recommendations": ["Review recent high-stakes decisions for confidence accuracy"]
  },
  "id": "d-001"
}
```

---

### `cstp.reindex` — Full Reindex

Delete and rebuild the ChromaDB collection from YAML files.

**Parameters:**

| Param | Type | Required | Description |
|-------|------|----------|-------------|
| `decisions_path` | string | ❌ | Override decisions directory |

**Example response:**

```json
{
  "jsonrpc": "2.0",
  "result": {
    "success": true,
    "decisions_indexed": 47,
    "errors": 0,
    "duration_ms": 12340
  },
  "id": "ri-001"
}
```

---

## MCP Interface (Model Context Protocol)

Since v0.9.0, CSTP exposes decision intelligence capabilities as **MCP tools** for native integration with any MCP-compliant agent. The MCP layer is a thin bridge — each tool maps 1:1 to an existing CSTP service method with zero code duplication.

### Transports

| Transport | Endpoint | Use Case |
|-----------|----------|----------|
| **Streamable HTTP** | `POST`/`GET` `http://host:8100/mcp` | Remote access from any network-reachable MCP client |
| **stdio** | `python -m a2a.mcp_server` | Local access or Docker exec |

### Connecting

```bash
# Claude Code — add as remote MCP server
claude mcp add --transport http cstp-decisions http://your-server:8100/mcp

# Claude Desktop — add to claude_desktop_config.json (stdio via Docker)
{
  "mcpServers": {
    "cstp": {
      "command": "docker",
      "args": ["exec", "-i", "cstp", "python", "-m", "a2a.mcp_server"]
    }
  }
}

# Local development (stdio)
python -m a2a.mcp_server
```

### MCP Tools

#### `query_decisions`

Search similar past decisions using semantic search, keyword matching, or hybrid retrieval.

**Input Schema:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `query` | string | ✅ | — | Natural language query |
| `limit` | int | ❌ | 5 | Max results (1–50) |
| `retrieval_mode` | string | ❌ | `"hybrid"` | `"semantic"`, `"keyword"`, or `"hybrid"` |
| `filters` | object | ❌ | — | `category`, `stakes`, `project`, `has_outcome` |

**Maps to:** `cstp.queryDecisions`

---

#### `check_action`

Validate an intended action against safety guardrails and policies.

**Input Schema:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `description` | string | ✅ | — | Action you intend to take |
| `category` | string | ❌ | — | Action category |
| `stakes` | string | ❌ | `"medium"` | `"low"`, `"medium"`, `"high"`, `"critical"` |
| `confidence` | float | ❌ | — | Your confidence (0.0–1.0) |

**Maps to:** `cstp.checkGuardrails`

---

#### `log_decision`

Record a decision to the immutable decision log.

**Input Schema:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `decision` | string | ✅ | — | What you decided (state the choice) |
| `confidence` | float | ✅ | — | Confidence level (0.0–1.0) |
| `category` | string | ✅ | — | `"architecture"`, `"process"`, `"integration"`, `"tooling"`, `"security"` |
| `stakes` | string | ❌ | `"medium"` | Stakes level |
| `context` | string | ❌ | — | Situation context |
| `reasons` | array | ❌ | — | `[{"type": "analysis", "text": "..."}]` — types: authority, analogy, analysis, pattern, intuition |
| `tags` | array | ❌ | — | Tags for categorization |
| `project` | string | ❌ | — | Project in owner/repo format |
| `feature` | string | ❌ | — | Feature or epic name |
| `pr` | int | ❌ | — | Pull request number |

**Maps to:** `cstp.recordDecision`

---

#### `review_outcome`

Record the outcome of a past decision for calibration.

**Input Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | ✅ | Decision ID (8-char hex) |
| `outcome` | string | ✅ | `"success"`, `"partial"`, `"failure"`, `"abandoned"` |
| `actual_result` | string | ❌ | What actually happened |
| `lessons` | string | ❌ | Lessons learned |
| `notes` | string | ❌ | Additional review notes |

**Maps to:** `cstp.reviewDecision`

---

#### `get_stats`

Get calibration statistics to assess decision-making quality.

**Input Schema:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `category` | string | ❌ | Filter by category |
| `project` | string | ❌ | Filter by project (owner/repo) |
| `window` | string | ❌ | `"30d"`, `"60d"`, `"90d"`, or `"all"` |

**Maps to:** `cstp.getCalibration`

---

### Error Handling

MCP tool errors are returned as `TextContent` with JSON:

```json
{
  "error": "validation_error",
  "message": "1 validation error for QueryDecisionsInput..."
}
```

Error types:
- `validation_error` — Invalid input (Pydantic validation failure)
- `internal_error` — Unexpected server error

---

## cURL Quick Reference

```bash
# Query decisions
curl -X POST http://localhost:8100/cstp \
  -H "Authorization: Bearer myagent:mytoken" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.queryDecisions","params":{"query":"authentication approach"},"id":"1"}'

# Check guardrails
curl -X POST http://localhost:8100/cstp \
  -H "Authorization: Bearer myagent:mytoken" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.checkGuardrails","params":{"action":{"description":"Deploy to prod","stakes":"high","context":{"affects_production":true}}},"id":"2"}'

# Record decision
curl -X POST http://localhost:8100/cstp \
  -H "Authorization: Bearer myagent:mytoken" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"cstp.recordDecision","params":{"decision":"Use Redis for caching","confidence":0.8,"category":"architecture"},"id":"3"}'

# Health check (no auth)
curl http://localhost:8100/health
```
