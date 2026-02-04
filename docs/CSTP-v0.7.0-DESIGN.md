# CSTP v0.7.0 Design Document

**Cognition State Transfer Protocol for cognition-engines**

| Field | Value |
|-------|-------|
| Version | 0.7.0 |
| Status | Draft |
| Author | Emerson |
| Created | 2026-02-04 |
| Decisions | b5614ac0, e675cf9c, aba645a3 |

---

## 1. Overview

### 1.1 Problem Statement

AI agents making decisions in isolation leads to:
- Redundant problem-solving across agents
- No shared learning from past decisions
- Inability to enforce organization-wide policies
- No visibility into *why* an agent is taking an action

### 1.2 Solution

**Cognition State Transfer Protocol (CSTP)** — an A2A-compatible extension enabling agents to share *intent* and *decision context* before acting, query each other's decision history, and enforce federated guardrails.

### 1.3 Goals

1. **Intent Sharing** — Announce what you're about to do and why
2. **Decision Query** — Search other agents' decision history
3. **Federated Guardrails** — Check policies across agent boundaries
4. **Backward Compatibility** — Existing local scripts unchanged

### 1.4 Non-Goals (v0.7.0)

- Full A2A task lifecycle management
- Streaming/SSE support
- Push notifications
- Agent Card registry/discovery service
- Decision outcome synchronization

---

## 2. Architecture

### 2.1 Component Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Agent (e.g., Emerson)                        │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    Local Usage (unchanged)                    │   │
│  │  uv run query.py "context"                                   │   │
│  │  uv run check.py --stakes high                               │   │
│  │  uv run decide log "decision"                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                              │                                       │
│                              ▼                                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              cognition-engines (Python library)               │   │
│  │                                                               │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │   │  ChromaDB   │  │  Guardrails │  │  Pattern Detection  │  │   │
│  │   │  (vectors)  │  │  (YAML)     │  │  (calibration)      │  │   │
│  │   └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  │                              │                                │   │
│  └──────────────────────────────│────────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼────────────────────────────────┐   │
│  │                     CSTP Layer (NEW)                          │   │
│  │                                                               │   │
│  │   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │   │
│  │   │   Server    │  │   Client    │  │   Agent Card        │  │   │
│  │   │  (HTTP)     │  │  (HTTP)     │  │   (.well-known)     │  │   │
│  │   └─────────────┘  └─────────────┘  └─────────────────────┘  │   │
│  │                                                               │   │
│  └───────────────────────────────────────────────────────────────┘   │
│                              │                                       │
└──────────────────────────────│───────────────────────────────────────┘
                               │
                               ▼ HTTP/JSON-RPC
┌─────────────────────────────────────────────────────────────────────┐
│                        Remote Agents                                 │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐ │
│   │  Claude-Ops │  │  Membrain   │  │  Security-Policy-Agent     │ │
│   └─────────────┘  └─────────────┘  └─────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 Directory Structure

```
cognition-agent-decisions/
├── src/agent_decisions/          # Existing CLI (unchanged)
│   ├── cli.py
│   ├── journal.py
│   └── models.py
│
├── skills/cognition-engines/     # Existing skill (unchanged)  
│   ├── scripts/
│   │   ├── query.py
│   │   ├── check.py
│   │   └── index.py
│   └── guardrails/
│       └── default.yaml
│
├── a2a/                          # NEW: CSTP implementation
│   ├── __init__.py
│   ├── server.py                 # CSTP HTTP server
│   ├── client.py                 # CSTP HTTP client
│   ├── agent_card.py             # Agent Card generation
│   ├── cstp/
│   │   ├── __init__.py
│   │   ├── methods.py            # CSTP method handlers
│   │   ├── models.py             # Request/response models
│   │   └── errors.py             # CSTP error codes
│   └── tests/
│       ├── test_server.py
│       ├── test_client.py
│       └── test_cstp_methods.py
│
├── docs/
│   └── CSTP-v0.7.0-DESIGN.md     # This document
│
└── pyproject.toml                # Add [a2a] optional deps
```

---

## 3. Protocol Specification

### 3.1 Transport

- **Protocol:** JSON-RPC 2.0 over HTTP/1.1
- **Content-Type:** `application/json`
- **Endpoint:** `POST /cstp`
- **A2A Compatibility:** Methods prefixed with `cstp.` to avoid collision

### 3.2 Agent Card

Served at `GET /.well-known/agent.json`:

```json
{
  "name": "emerson-cognition",
  "description": "Decision intelligence for AI agents",
  "version": "0.7.0",
  "url": "https://agent.example.com",
  "capabilities": {
    "cstp": {
      "version": "1.0",
      "methods": [
        "cstp.announceIntent",
        "cstp.queryDecisions", 
        "cstp.checkGuardrails"
      ]
    }
  },
  "authentication": {
    "schemes": ["bearer"]
  },
  "contact": "emerson@example.com"
}
```

### 3.3 CSTP Methods

#### 3.3.1 `cstp.announceIntent`

Announce intent before taking action. Allows other agents to provide context or objections.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.announceIntent",
  "id": "req-001",
  "params": {
    "intent": "Deploy authentication service to production",
    "context": "PR #42 approved, all tests passing",
    "category": "architecture",
    "stakes": "high",
    "confidence": 0.85,
    "agent": {
      "id": "emerson",
      "url": "https://emerson.example.com"
    },
    "correlationId": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-001",
  "result": {
    "received": true,
    "correlationId": "550e8400-e29b-41d4-a716-446655440000",
    "similarDecisions": [
      {
        "id": "dec-123",
        "title": "Deployed auth service v2.1",
        "outcome": "success",
        "date": "2026-01-15T10:30:00Z",
        "notes": "Required 30-min rollback window"
      }
    ],
    "guardrailStatus": {
      "allowed": true,
      "violations": []
    },
    "suggestions": [
      "Consider deploying during low-traffic window (2-4 AM EST)"
    ]
  }
}
```

#### 3.3.2 `cstp.queryDecisions`

Search decision history for similar past decisions.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.queryDecisions",
  "id": "req-002",
  "params": {
    "query": "database migration strategy",
    "filters": {
      "category": "architecture",
      "minConfidence": 0.7,
      "dateAfter": "2026-01-01T00:00:00Z"
    },
    "limit": 10
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-002",
  "result": {
    "decisions": [
      {
        "id": "dec-456",
        "title": "Use blue-green deployment for DB migration",
        "category": "architecture",
        "confidence": 0.9,
        "outcome": "success",
        "date": "2026-01-20T14:00:00Z",
        "distance": 0.23
      }
    ],
    "total": 1,
    "queryTimeMs": 45
  }
}
```

#### 3.3.3 `cstp.checkGuardrails`

Check if an action is allowed by the remote agent's guardrails.

**Request:**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.checkGuardrails",
  "id": "req-003",
  "params": {
    "action": {
      "description": "Deploy to production without code review",
      "category": "process",
      "stakes": "high",
      "confidence": 0.6,
      "context": {
        "affectsProduction": true,
        "codeReviewCompleted": false
      }
    }
  }
}
```

**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": "req-003",
  "result": {
    "allowed": false,
    "violations": [
      {
        "guardrailId": "no-production-without-review",
        "message": "Production changes require completed code review",
        "severity": "block"
      },
      {
        "guardrailId": "no-high-stakes-low-confidence",
        "message": "High-stakes decisions require 50% confidence or more",
        "severity": "warn"
      }
    ],
    "evaluated": 4,
    "evaluatedAt": "2026-02-04T21:00:00Z"
  }
}
```

### 3.4 Error Codes

| Code | Name | Description |
|------|------|-------------|
| -32700 | ParseError | Invalid JSON |
| -32600 | InvalidRequest | Invalid JSON-RPC request |
| -32601 | MethodNotFound | Method does not exist |
| -32602 | InvalidParams | Invalid method parameters |
| -32603 | InternalError | Internal server error |
| -32001 | AuthenticationRequired | Missing or invalid auth token |
| -32002 | RateLimited | Too many requests |
| -32003 | QueryFailed | ChromaDB query failed |
| -32004 | GuardrailEvalFailed | Guardrail evaluation error |

---

## 4. Security

### 4.1 Authentication

- **Bearer Token:** Required for all CSTP methods
- **Token Format:** Opaque string, validated by server
- **Header:** `Authorization: Bearer <token>`

### 4.2 Authorization

- **Read-only by default:** `queryDecisions` and `checkGuardrails`
- **Intent sharing:** Requires explicit permission flag
- **Per-agent ACLs:** Future enhancement

### 4.3 Data Privacy

- **No raw decision content:** Only titles, outcomes, metadata shared
- **Opt-in indexing:** Agents choose which decisions are queryable
- **Correlation IDs:** For audit trail, not PII

---

## 5. Implementation Plan

### Phase 1: Foundation (Week 1)
- [ ] Create `feat/cstp-v0.7` branch
- [ ] Set up `a2a/` directory structure
- [ ] Implement `CstpServer` class with FastAPI
- [ ] Implement Agent Card endpoint
- [ ] Add `[a2a]` optional dependencies to pyproject.toml

### Phase 2: Methods (Week 2)
- [ ] Implement `cstp.queryDecisions` (wraps existing query.py)
- [ ] Implement `cstp.checkGuardrails` (wraps existing check.py)
- [ ] Implement `cstp.announceIntent` (new)
- [ ] Add request/response models with Pydantic

### Phase 3: Client (Week 3)
- [ ] Implement `CstpClient` class
- [ ] Add CLI: `uv run a2a/client.py query "context" --agent https://...`
- [ ] Add CLI: `uv run a2a/client.py check --agent https://...`
- [ ] Add retry logic and error handling

### Phase 4: Testing & Docs (Week 4)
- [ ] Unit tests for server and client
- [ ] Integration test: agent queries own server
- [ ] Update README with A2A usage
- [ ] Sync skill to workspace

---

## 6. Configuration

### 6.1 Server Config (`a2a/config.yaml`)

```yaml
server:
  host: "0.0.0.0"
  port: 8100
  cors_origins: ["*"]

auth:
  enabled: true
  tokens:
    - name: "emerson"
      token: "${CSTP_TOKEN_EMERSON}"
    - name: "claude-ops"
      token: "${CSTP_TOKEN_CLAUDE}"

cstp:
  query:
    max_results: 50
    min_score: 0.3
  guardrails:
    config_path: "guardrails/default.yaml"
  intent:
    store_received: true
    auto_respond: true
```

### 6.2 Client Config

```yaml
agents:
  - name: "security-policy"
    url: "https://security.example.com"
    token: "${CSTP_TOKEN_SECURITY}"
  - name: "claude-ops"
    url: "https://claude-ops.example.com"
    token: "${CSTP_TOKEN_CLAUDE}"

defaults:
  timeout_seconds: 30
  retry_count: 3
```

---

## 7. Future Enhancements (v0.8+)

1. **Decision Broadcast** — Push decisions to subscribed agents
2. **Federated Search** — Query multiple agents in parallel
3. **Consensus Protocol** — Multi-agent agreement before high-stakes actions
4. **Outcome Sync** — Share decision outcomes for calibration
5. **gRPC Binding** — Lower latency for high-frequency queries
6. **Agent Discovery** — Registry service for finding agents

---

## 8. Open Questions

1. **Token rotation:** How to rotate CSTP tokens without downtime?
2. **Rate limiting:** Per-agent or global limits?
3. **Decision visibility:** Who can see which decisions?
4. **Conflict resolution:** What if guardrails contradict?

---

## 9. References

- [A2A Protocol Specification](https://a2a-protocol.org/latest/specification/)
- [cognition-agent-decisions README](../README.md)
- Decision: b5614ac0 (Client+Server together)
- Decision: e675cf9c (Guardrails on server)
- Decision: aba645a3 (Feature branch approach)
