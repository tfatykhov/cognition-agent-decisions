# F001: CSTP Server Infrastructure

| Field | Value |
|-------|-------|
| Feature ID | F001 |
| Status | Draft |
| Priority | P0 (Foundation) |
| Depends On | None |
| Blocks | F002, F003, F004 |
| Decision | a42a3514 |

---

## Summary

Create the CSTP HTTP server infrastructure with Agent Card support and JSON-RPC 2.0 endpoint.

## Goals

1. FastAPI-based HTTP server
2. Agent Card endpoint at `/.well-known/agent.json`
3. JSON-RPC 2.0 handler at `POST /cstp`
4. Bearer token authentication
5. Health check endpoint

## Non-Goals

- Method implementations (F002-F004)
- gRPC support
- Push notifications

---

## Specification

### Directory Structure

```
cognition-agent-decisions/
└── a2a/
    ├── __init__.py
    ├── server.py           # FastAPI application
    ├── agent_card.py       # Agent Card generation
    ├── jsonrpc.py          # JSON-RPC 2.0 handler
    ├── auth.py             # Bearer token auth
    ├── config.py           # Server configuration
    └── models/
        ├── __init__.py
        ├── requests.py     # JSON-RPC request models
        └── responses.py    # JSON-RPC response models
```

### Agent Card Endpoint

**GET** `/.well-known/agent.json`

```json
{
  "name": "cognition-engines",
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
  }
}
```

### JSON-RPC Endpoint

**POST** `/cstp`

**Headers:**
- `Content-Type: application/json`
- `Authorization: Bearer <token>`

**Request format:**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.<method>",
  "id": "request-id",
  "params": { ... }
}
```

**Success response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "result": { ... }
}
```

**Error response:**
```json
{
  "jsonrpc": "2.0",
  "id": "request-id",
  "error": {
    "code": -32601,
    "message": "Method not found",
    "data": { ... }
  }
}
```

### Authentication

```python
# a2a/auth.py
from fastapi import HTTPException, Header

async def verify_token(authorization: str = Header(...)) -> str:
    """Verify Bearer token and return agent ID."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid authorization header")
    
    token = authorization[7:]
    agent_id = validate_token(token)  # Check against config
    
    if not agent_id:
        raise HTTPException(401, "Invalid token")
    
    return agent_id
```

### Configuration

```yaml
# config/server.yaml
server:
  host: "0.0.0.0"
  port: 8100
  cors_origins: ["*"]

agent:
  name: "cognition-engines"
  version: "0.7.0"
  url: "https://agent.example.com"

auth:
  enabled: true
  tokens:
    - agent: "emerson"
      token: "${CSTP_TOKEN_EMERSON}"
    - agent: "claude-ops"
      token: "${CSTP_TOKEN_CLAUDE}"
```

### Health Check

**GET** `/health`

```json
{
  "status": "healthy",
  "version": "0.7.0",
  "uptime_seconds": 3600
}
```

---

## Implementation Tasks

- [ ] Create `a2a/` directory structure
- [ ] Implement `server.py` with FastAPI
- [ ] Implement `agent_card.py` with Pydantic model
- [ ] Implement `jsonrpc.py` request/response handling
- [ ] Implement `auth.py` Bearer token verification
- [ ] Implement `config.py` with YAML loading
- [ ] Add health check endpoint
- [ ] Create `pyproject.toml` optional deps: `[a2a]`
- [ ] Add CLI: `uv run a2a/server.py --port 8100`
- [ ] Write tests for server, auth, jsonrpc

---

## Acceptance Criteria

1. `GET /.well-known/agent.json` returns valid Agent Card
2. `POST /cstp` with valid JSON-RPC returns 200 (stub response)
3. `POST /cstp` without Bearer token returns 401
4. `GET /health` returns healthy status
5. Server starts with `uv run a2a/server.py`
6. All tests pass

---

## Dependencies

```toml
# pyproject.toml [project.optional-dependencies]
a2a = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
]
```
