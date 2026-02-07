# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI AGENTS                                   │
│        (LangChain, AutoGen, CrewAI, Custom Python Agents)           │
└──────────────┬────────────────────────────────────┬─────────────────┘
               │  JSON-RPC 2.0 over HTTP            │  CLI
               │  (Bearer Token Auth)                │
               ▼                                     ▼
┌──────────────────────────────────┐    ┌────────────────────────────┐
│          A2A LAYER               │    │        CLI LAYER           │
│   ┌─────────────────────────┐    │    │   bin/cognition            │
│   │   FastAPI Server        │    │    │   ├── index <dir>          │
│   │   (a2a/server.py)       │    │    │   ├── query <context>      │
│   │   ├── POST /cstp        │    │    │   ├── check --stakes high  │
│   │   ├── GET  /health      │    │    │   ├── patterns calibration │
│   │   └── GET  /.well-known │    │    │   ├── guardrails           │
│   │          /agent.json    │    │    │   └── count                │
│   └────────────┬────────────┘    │    └────────────────────────────┘
│                │                 │
│   ┌────────────▼────────────┐    │
│   │  CSTP Dispatcher        │    │    ┌────────────────────────────┐
│   │  (a2a/cstp/dispatcher)  │    │    │      WEB DASHBOARD         │
│   │                         │    │    │  (dashboard/app.py)        │
│   │  Methods:               │    │    │  Flask + Jinja2            │
│   │  ├── queryDecisions     │    │    │  ├── /decisions            │
│   │  ├── checkGuardrails    │    │    │  ├── /decisions/<id>       │
│   │  ├── listGuardrails     │    │    │  ├── /decisions/<id>/review│
│   │  ├── recordDecision     │    │    │  ├── /calibration          │
│   │  ├── reviewDecision     │    │    │  └── /health               │
│   │  ├── getCalibration     │    │    └────────────────────────────┘
│   │  ├── attributeOutcomes  │    │
│   │  ├── checkDrift         │    │
│   │  └── reindex            │    │
│   └────────────┬────────────┘    │
└────────────────┼─────────────────┘
                 │
    ┌────────────▼──────────────────────────────────────────┐
    │                    CSTP SERVICES                       │
    │  ┌──────────────┐  ┌───────────────┐  ┌────────────┐  │
    │  │query_service  │  │decision_svc   │  │calibration │  │
    │  │(semantic +    │  │(record + YAML │  │_service    │  │
    │  │ BM25 hybrid)  │  │ + ChromaDB)   │  │(Brier +    │  │
    │  └──────────────┘  └───────────────┘  │ buckets)   │  │
    │  ┌──────────────┐  ┌───────────────┐  └────────────┘  │
    │  │guardrails_svc│  │attribution    │  ┌────────────┐  │
    │  │(YAML-based   │  │_service       │  │drift_svc   │  │
    │  │ evaluation)  │  │(PR stability) │  │(30d vs 90d)│  │
    │  └──────────────┘  └───────────────┘  └────────────┘  │
    │  ┌──────────────┐  ┌───────────────┐                  │
    │  │reindex_svc   │  │bm25_index     │                  │
    │  │(full rebuild)│  │(keyword search│                  │
    │  └──────────────┘  └───────────────┘                  │
    └───────────────────────┬───────────────────────────────┘
                            │
    ┌───────────────────────▼───────────────────────────────┐
    │                  CORE ENGINES                          │
    │  (src/cognition_engines/)                              │
    │                                                        │
    │  ┌─────────────────────────────────────────────────┐   │
    │  │ ACCELERATORS                                     │   │
    │  │ ├── SemanticIndex (ChromaDB + Gemini embeddings) │   │
    │  │ └── PatternDetector (calibration, anti-patterns) │   │
    │  └─────────────────────────────────────────────────┘   │
    │  ┌─────────────────────────────────────────────────┐   │
    │  │ GUARDRAILS                                       │   │
    │  │ ├── GuardrailEngine (YAML loader + evaluator)    │   │
    │  │ ├── Evaluators (field, semantic, temporal,        │   │
    │  │ │               aggregate, compound)              │   │
    │  │ └── AuditLog (JSON-based audit trail)             │   │
    │  └─────────────────────────────────────────────────┘   │
    └───────────────────────┬───────────────────────────────┘
                            │
    ┌───────────────────────▼───────────────────────────────┐
    │                  STORAGE LAYER                         │
    │  ┌────────────────┐  ┌─────────────────────────────┐   │
    │  │   ChromaDB     │  │   YAML Decision Files       │   │
    │  │   (vectors +   │  │   decisions/YYYY/MM/         │   │
    │  │    metadata)   │  │   YYYY-MM-DD-decision-*.yaml │   │
    │  └────────────────┘  └─────────────────────────────┘   │
    │  ┌────────────────┐  ┌─────────────────────────────┐   │
    │  │  Guardrail     │  │   Audit Trail               │   │
    │  │  YAML Files    │  │   audit/*.json               │   │
    │  └────────────────┘  └─────────────────────────────┘   │
    └───────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. A2A Layer (`a2a/`)

The **Agent-to-Agent** layer is the network-facing surface of Cognition Engines.

| File | Purpose |
|------|---------|
| `server.py` | FastAPI application with lifespan management, CORS, and route registration |
| `config.py` | Multi-source configuration: YAML file → environment variables → defaults |
| `auth.py` | Bearer token authentication with constant-time comparison (`secrets.compare_digest`) |
| `__init__.py` | Package exports |

**Endpoints:**

- `POST /cstp` — JSON-RPC 2.0 dispatch (authenticated)
- `GET /health` — Health check with uptime (unauthenticated)
- `GET /.well-known/agent.json` — A2A agent card for discovery (unauthenticated)

### 2. CSTP Services (`a2a/cstp/`)

Each JSON-RPC method is backed by a dedicated service module:

| Service | Method | Description |
|---------|--------|-------------|
| `query_service.py` | `cstp.queryDecisions` | Semantic search over ChromaDB with optional BM25 hybrid |
| `decision_service.py` | `cstp.recordDecision` | Record new decisions as YAML + ChromaDB index |
| `guardrails_service.py` | `cstp.checkGuardrails` | Evaluate context against all loaded guardrails |
| `guardrails_service.py` | `cstp.listGuardrails` | List active guardrail definitions |
| `calibration_service.py` | `cstp.getCalibration` | Compute Brier scores and confidence buckets |
| `attribution_service.py` | `cstp.attributeOutcomes` | Auto-attribute outcomes via PR stability |
| `drift_service.py` | `cstp.checkDrift` | Compare 30-day vs. 90-day+ calibration |
| `reindex_service.py` | `cstp.reindex` | Delete and rebuild ChromaDB collection |
| `dispatcher.py` | (router) | Maps JSON-RPC method names to async handlers |
| `models.py` | (shared) | Pydantic-style dataclasses for request/response objects |
| `bm25_index.py` | (internal) | BM25Okapi keyword index with caching and score merging |

### 3. Core Engines (`src/cognition_engines/`)

The library-level logic, usable independently of the HTTP server.

#### Accelerators (`accelerators/`)

| Class | File | Description |
|-------|------|-------------|
| `SemanticIndex` | `semantic_index.py` | ChromaDB HTTP API wrapper with Gemini embedding generation, decision indexing, filtered vector query |

#### Guardrails (`guardrails/`)

| Class | File | Description |
|-------|------|-------------|
| `GuardrailEngine` | `engine.py` | Loads YAML guardrails, evaluates conditions + requirements, returns pass/block/warn results |
| `GuardrailCondition` | `engine.py` | Parsed condition with operator support (`<`, `>`, `=`, `!=`, `in`) |
| `GuardrailRequirement` | `engine.py` | Boolean requirement check (field must be `true`) |
| `Guardrail` | `engine.py` | Full guardrail definition with scope, conditions, requirements, action, message |
| `ConditionEvaluator` | `evaluators.py` | Protocol for pluggable evaluators |
| `FieldCondition` | `evaluators.py` | v2 field comparison with extended operators |
| `SemanticCondition` | `evaluators.py` | Checks semantic similarity to past decisions |
| `TemporalCondition` | `evaluators.py` | Time-window based conditions |
| `AggregateCondition` | `evaluators.py` | Statistical aggregate checks (e.g., success rate < 50%) |
| `CompoundCondition` | `evaluators.py` | AND/OR logical composition of conditions |
| `AuditLog` | `audit.py` | Manages JSON audit trail for guardrail evaluations |
| `AuditRecord` | `audit.py` | Per-decision audit record with override support |

#### Patterns (`patterns/`)

| Class | File | Description |
|-------|------|-------------|
| `PatternDetector` | `detector.py` | Loads YAML decisions, generates calibration reports, detects anti-patterns, produces category analysis |
| `CalibrationBucket` | `detector.py` | Confidence bucket with Brier score computation |
| `AntiPattern` | `detector.py` | Detected anti-pattern (e.g., overcalibration, flip-flopping) |

### 4. Web Dashboard (`dashboard/`)

A Flask-based web UI for human-friendly decision browsing and outcome review.

| File | Description |
|------|-------------|
| `app.py` | Flask routes: decisions list, detail, review, calibration |
| `config.py` | Dashboard-specific config (CSTP URL, auth, port) |
| `auth.py` | HTTP Basic Auth decorator |
| `cstp_client.py` | Async CSTP client for backend communication |
| `models.py` | Dashboard-specific data models |
| `templates/` | Jinja2 HTML templates (base, decisions, decision, review, calibration) |
| `static/` | CSS/JS assets |

### 5. Guardrail Definitions (`guardrails/`)

| File | Description |
|------|-------------|
| `cornerstone.yaml` | Non-negotiable block-level rules (production review, confidence minimum, backtest requirement) |
| `templates/financial.yaml` | Template for financial/trading projects (risk assessment, position limits, audit trail) |
| `templates/production-safety.yaml` | Template for production deployments (code review, CI, rollback, no-Friday deploys) |

### 6. CLI (`bin/cognition`)

A standalone Python CLI providing all core operations without the HTTP server.

---

## Data Flow

### Query Flow

```
Agent → POST /cstp → Dispatcher → query_service
                                      ├── Generate embedding (Gemini API)
                                      ├── Query ChromaDB (semantic)
                                      ├── Optionally build BM25 index (keyword)
                                      ├── Merge and rank results
                                      └── Return JSON-RPC response
```

### Record Flow

```
Agent → POST /cstp → Dispatcher → decision_service
                                      ├── Validate request
                                      ├── Check guardrails (pre-decision protocol)
                                      ├── Build YAML structure
                                      ├── Write YAML file to disk
                                      ├── Generate embedding (Gemini API)
                                      ├── Index in ChromaDB
                                      └── Return decision ID + path
```

### Guardrail Flow

```
Agent → POST /cstp → Dispatcher → guardrails_service
                                      ├── Load guardrails from YAML (cached 5 min)
                                      ├── Match conditions against context
                                      ├── Evaluate requirements
                                      ├── Collect violations + warnings
                                      ├── Log audit trail
                                      └── Return allowed/blocked + details
```

---

## Deployment Architecture

```
┌────────────────────────────────────────────────────────────┐
│                   Docker Compose                            │
│                                                             │
│  ┌──────────────────┐         ┌─────────────────────┐      │
│  │   cstp-server     │         │     chromadb         │      │
│  │   (Python 3.11)   │ ──────▶ │   (chromadb/chroma)  │      │
│  │   Port: 8100      │  HTTP   │   Port: 8000         │      │
│  │                    │         │                      │      │
│  │   Volumes:         │         │   Volume:            │      │
│  │   ├── config/ (ro) │         │   └── chroma_data    │      │
│  │   ├── guardrails/  │         │                      │      │
│  │   └── decisions/   │         │   Health:            │      │
│  │                    │         │   /api/v1/heartbeat   │      │
│  │   Health:          │         └─────────────────────┘      │
│  │   /health          │                                      │
│  └──────────────────┘                                       │
│                                                             │
│  Network: cstp-network (bridge)                             │
└────────────────────────────────────────────────────────────┘
```

**Docker Image:** Multi-stage build (`python:3.11-slim`)

- **Builder stage:** Installs `uv` and Python dependencies from `pyproject.toml`
- **Runtime stage:** Copies installed packages, app code, creates non-root user
- **Security:** Runs as `appuser` (non-root), read-only config mounts

---

## Security Model

| Layer | Mechanism |
|-------|-----------|
| **Transport** | HTTPS (reverse proxy recommended for production) |
| **Authentication** | Bearer token per agent, validated with `secrets.compare_digest` |
| **Authorization** | Agent ID embedded in each request; audit trail records who did what |
| **Secrets** | Environment variables or `${VAR}` expansion in YAML config |
| **Container** | Non-root user, minimal base image, no-cache pip installs |
| **CORS** | Configurable allowed origins (defaults to `*`) |
| **CSRF** | Dashboard uses Flask-WTF CSRF protection |
