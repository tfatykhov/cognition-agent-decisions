# AGENTS.md — Cognition Engines for Agent-Decisions

> **Version:** 0.7.0  
> **Python:** ≥ 3.11  
> **License:** MIT  
> **Build system:** hatchling  
> **Package manager:** uv (preferred) / pip

This document is the single source of truth for AI agents working on this codebase.
Read it **first** before making any change.

---

## 1. Project Identity

**Cognition Engines** provides an intelligence layer for AI agents built on two pillars:

| Pillar | Purpose | Core class |
|--------|---------|------------|
| **Accelerators** | Cross-agent learning via semantic decision querying and pattern detection | `SemanticIndex`, `PatternDetector` |
| **Guardrails** | Policy enforcement that prevents violations before they occur | `GuardrailEngine`, `AuditLog` |

The system exposes these capabilities over **CSTP (Cognition State Transfer Protocol)**, a JSON-RPC 2.0 API served by FastAPI.

Upstream dependency: [agent-decisions](https://github.com/tfatykhov/agent-decisions) (decision journal with Brier scoring).

---

## 2. Repository Layout

```
cognition-agent-decisions/
├── src/
│   └── cognition_engines/           # Core library (pure Python, no web deps)
│       ├── __init__.py
│       ├── accelerators/
│       │   ├── __init__.py
│       │   └── semantic_index.py    # SemanticIndex: ChromaDB + Gemini embeddings
│       ├── guardrails/
│       │   ├── __init__.py
│       │   ├── engine.py            # GuardrailEngine: YAML rule loading & evaluation
│       │   ├── evaluators.py        # v2 condition evaluators (field, semantic, temporal, aggregate, compound)
│       │   └── audit.py             # AuditLog: guardrail evaluation trail
│       └── patterns/
│           ├── __init__.py
│           └── detector.py          # PatternDetector: calibration, category analysis, anti-pattern detection
│
├── a2a/                             # A2A / CSTP server layer (FastAPI + Pydantic)
│   ├── __init__.py
│   ├── server.py                    # FastAPI app factory, lifespan, routes
│   ├── config.py                    # Config dataclasses (server, agent, auth): YAML + env loading
│   ├── auth.py                      # Bearer token authentication with constant-time comparison
│   ├── models/
│   │   ├── __init__.py              # AgentCard, HealthResponse, AgentCapabilities
│   │   ├── agent_card.py
│   │   ├── health.py
│   │   └── jsonrpc.py               # JsonRpcRequest, JsonRpcResponse, error codes
│   └── cstp/
│       ├── __init__.py              # Public re-exports for the CSTP package
│       ├── dispatcher.py            # CstpDispatcher: JSON-RPC method routing + all handler functions
│       ├── models.py                # Pydantic request/response models for CSTP methods
│       ├── query_service.py         # Query logic: semantic + BM25 hybrid search
│       ├── bm25_index.py            # BM25 keyword search index
│       ├── guardrails_service.py    # Guardrail evaluation service (loads YAML, caches engine)
│       ├── decision_service.py      # Record & retrieve decisions (YAML file I/O + ChromaDB indexing)
│       ├── calibration_service.py   # Brier score calibration, bucket analysis, recommendations
│       ├── attribution_service.py   # Automatic outcome attribution for stable decisions
│       ├── drift_service.py         # Calibration drift detection (recent vs historical)
│       ├── reindex_service.py       # Full re-indexing of decision corpus
│       └── tests/                   # CSTP-specific unit tests
│
├── guardrails/                      # YAML guardrail definitions (loaded at runtime)
│   ├── cornerstone.yaml             # Non-negotiable block-level rules
│   └── templates/
│       ├── financial.yaml           # Finance-domain guardrails
│       └── production-safety.yaml   # Production deployment guardrails
│
├── dashboard/                       # Web dashboard (Flask, separate deployable)
│   ├── app.py                       # Flask app: decisions list, detail, review, calibration views
│   ├── cstp_client.py               # Async HTTP client for CSTP server
│   ├── config.py, auth.py, models.py
│   ├── templates/                   # Jinja2 templates
│   ├── static/                      # CSS/JS
│   ├── tests/                       # Dashboard-specific tests
│   ├── Dockerfile                   # Separate Dockerfile for dashboard
│   └── pyproject.toml               # Dashboard dependencies
│
├── tests/                           # Main test suite (pytest)
│   ├── test_semantic_index.py
│   ├── test_guardrails.py
│   ├── test_guardrails_service.py
│   ├── test_patterns.py
│   ├── test_evaluators.py
│   ├── test_audit.py
│   ├── test_decision_service.py
│   ├── test_query_service.py
│   ├── test_a2a_server.py
│   ├── test_config_env.py
│   ├── test_attribution_service.py
│   ├── test_calibration_service.py
│   ├── test_f002_query_decisions.py
│   ├── test_f003_check_guardrails.py
│   ├── test_f007_record_decision.py
│   ├── test_f008_review_decision.py
│   └── test_f009_get_calibration.py
│
├── docs/                            # Design & feature documentation
│   ├── CSTP-v0.7.0-DESIGN.md       # Full CSTP protocol specification
│   ├── DOCKER.md                    # Docker deployment guide
│   ├── WORKFLOWS.md                 # Developer & code-review agent workflows
│   ├── specs/                       # Feature specifications (F001–F020)
│   ├── features/                    # Feature implementation checklists
│   └── images/                      # Architecture diagrams
│
├── ProductDocumentation/            # End-user documentation suite
│   ├── 01-Product-Overview.md
│   ├── 02-Architecture.md
│   ├── 03-Module-Reference.md
│   ├── 04-API-Reference.md
│   ├── 05-CLI-Reference.md
│   ├── 06-Installation-Guide.md
│   ├── 07-Configuration-Guide.md
│   ├── 08-Dashboard-Guide.md
│   └── 09-Guardrails-Authoring.md
│
├── skills/cognition-engines/        # OpenClaw skill integration
│   ├── SKILL.md
│   ├── scripts/                     # CLI scripts (query.py, check.py, etc.)
│   └── guardrails/                  # Skill-bundled guardrail definitions
│
├── config/
│   └── server.yaml                  # Default CSTP server configuration
│
├── bin/
│   └── cognition                    # CLI entry point script
│
├── Dockerfile                       # Multi-stage production Dockerfile (python:3.11-slim)
├── docker-compose.yml               # CSTP server + ChromaDB orchestration
├── pyproject.toml                   # Project metadata, dependencies, tool config
├── .env.example                     # Environment variable template
└── README.md                        # User-facing project overview
```

---

## 3. Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                     AI Agents (clients)                   │
│         (LangChain, AutoGen, CrewAI, any Python)         │
└────────────────────────┬─────────────────────────────────┘
                         │  JSON-RPC 2.0 / Bearer auth
                         ▼
┌──────────────────────────────────────────────────────────┐
│                     A2A Layer (FastAPI)                    │
│  server.py → CstpDispatcher → Service handlers            │
│  Endpoints: POST /cstp, GET /health, GET /.well-known/... │
└──────┬──────────────┬───────────────┬────────────────────┘
       │              │               │
       ▼              ▼               ▼
┌────────────┐ ┌──────────────┐ ┌──────────────┐
│ Accelerators│ │  Guardrails   │ │   Patterns   │
│ SemanticIndex│ │ GuardrailEngine│ │PatternDetector│
└──────┬──────┘ └──────┬───────┘ └──────┬───────┘
       │              │               │
       ▼              ▼               ▼
┌──────────────────────────────────────────────────────────┐
│              Storage Layer                                │
│  ChromaDB (vectors) + YAML files (decisions/guardrails)   │
└──────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Core library has zero web dependencies** — `src/cognition_engines/` uses only `pyyaml`, `chromadb`, `rank-bm25`. No FastAPI, no Pydantic.
2. **A2A layer wraps the core** — `a2a/` adds FastAPI, Pydantic, and HTTP concerns. This separation is intentional.
3. **Singleton pattern** — Core classes use module-level singletons (`get_index()`, `get_engine()`, `get_dispatcher()`).
4. **YAML-first configuration** — Guardrails, decisions, and server config are all YAML-based with env var expansion (`${VAR_NAME}`).

---

## 4. CSTP Protocol — Method Reference

All methods are dispatched via `POST /cstp` as JSON-RPC 2.0 requests. Authentication: `Authorization: Bearer <token>`.

| Method | Handler function | Service module | Purpose |
|--------|-----------------|----------------|---------|
| `cstp.queryDecisions` | `_handle_query_decisions` | `query_service.py` | Semantic + BM25 hybrid search over indexed decisions |
| `cstp.checkGuardrails` | `_handle_check_guardrails` | `guardrails_service.py` | Evaluate action context against loaded guardrail rules |
| `cstp.listGuardrails` | `_handle_list_guardrails` | `guardrails_service.py` | List all active guardrail definitions |
| `cstp.recordDecision` | `_handle_record_decision` | `decision_service.py` | Create a new decision (YAML file + ChromaDB index) |
| `cstp.reviewDecision` | `_handle_review_decision` | `decision_service.py` | Add outcome/review to an existing decision |
| `cstp.getCalibration` | `_handle_get_calibration` | `calibration_service.py` | Brier score analysis and calibration recommendations |
| `cstp.attributeOutcomes` | `_handle_attribute_outcomes` | `attribution_service.py` | Auto-attribute success/failure based on stability window |
| `cstp.checkDrift` | `_handle_check_drift` | `drift_service.py` | Compare recent vs historical calibration for drift |
| `cstp.reindex` | `_handle_reindex` | `reindex_service.py` | Re-index all decisions with fresh embeddings |

### Handler Registration

All handlers are registered in `dispatcher.py → register_methods()`. To add a new CSTP method:

1. Create the service function in a new or existing `*_service.py` file under `a2a/cstp/`.
2. Create the handler wrapper `_handle_<method_name>` in `dispatcher.py`.
3. Register it in `register_methods()`.
4. Add Pydantic request/response models to `a2a/cstp/models.py` if needed.
5. Add tests under `tests/test_f0XX_<method_name>.py`.

---

## 5. Core Module API Quick Reference

### SemanticIndex (`src/cognition_engines/accelerators/semantic_index.py`)

```python
from cognition_engines.accelerators import SemanticIndex

index = SemanticIndex()
index.ensure_collection()
index.index_decision({"title": "...", "context": "...", "confidence": 0.85})
results = index.query("database migration", n_results=5, category="architecture")
count = index.count()
```

- **Embeddings:** Gemini `text-embedding-004` (768 dimensions)
- **Vector store:** ChromaDB (HTTP API, configurable via `CHROMA_URL`)
- **Collection name:** `cognition_decisions` (configurable via `CHROMA_COLLECTION`)

### GuardrailEngine (`src/cognition_engines/guardrails/engine.py`)

```python
from cognition_engines.guardrails import GuardrailEngine

engine = GuardrailEngine()
engine.load_from_directory(Path("guardrails"))
allowed, results = engine.check({"stakes": "high", "confidence": 0.4})
guardrails_list = engine.list_guardrails()
```

**Guardrail YAML format:**

```yaml
- id: unique-rule-id
  description: Human-readable description
  condition_stakes: high          # condition_<field>: value
  condition_confidence: "< 0.5"   # supports operators: <, >, <=, >=, ==, !=
  action: block                   # block | warn
  message: "Reason for the rule"
  scope: ProjectName              # optional: limits rule to specific projects
```

### PatternDetector (`src/cognition_engines/patterns/detector.py`)

```python
from cognition_engines.patterns import PatternDetector

detector = PatternDetector(decisions=decision_list)
detector.load_from_directory(Path("decisions"))
report = detector.calibration_report()   # Brier scores by bucket
categories = detector.category_analysis() # Stats per category
antipatterns = detector.detect_antipatterns()
full = detector.full_report()
```

### Evaluators (`src/cognition_engines/guardrails/evaluators.py`)

v2 condition evaluators supporting advanced guardrail conditions:

- `FieldCondition` — Simple field comparison
- `SemanticCondition` — Semantic similarity against past decisions
- `TemporalCondition` — Time-window based checks
- `AggregateCondition` — Statistical aggregate checks
- `CompoundCondition` — AND/OR logic combining multiple conditions

---

## 6. Development Setup

### Prerequisites

- Python 3.11+
- ChromaDB instance (Docker recommended: `chromadb/chroma:0.4.22`)
- Gemini API key for embeddings

### Installation

```powershell
# Clone
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cd cognition-agent-decisions

# Create .env from template
Copy-Item .env.example .env
# Edit .env: set GEMINI_API_KEY and CSTP_AUTH_TOKENS

# Install with all dependencies (core + a2a + dev)
python -m pip install -e ".[all]"
```

### Environment Variables (Key)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `GEMINI_API_KEY` | **Yes** | — | Gemini embeddings API key |
| `CSTP_AUTH_TOKENS` | **Yes** | — | `agent1:token1,agent2:token2` format |
| `CHROMA_URL` | No | `http://chromadb:8000` | ChromaDB connection URL |
| `CSTP_HOST` | No | `0.0.0.0` | Server bind address |
| `CSTP_PORT` | No | `8100` | Server bind port |
| `LOG_LEVEL` | No | `INFO` | Logging level |
| `DECISIONS_PATH` | No | `decisions` | Path for decision YAML storage |
| `CHROMA_COLLECTION` | No | `decisions_gemini` | ChromaDB collection name |
| `GUARDRAILS_PATHS` | No | — | Colon-separated paths to guardrail YAML dirs |

---

## 7. Testing

### Mandatory Rule

> **Every new feature or fix MUST have corresponding unit tests.**
> **Always run the full test suite before committing.**

### Commands

```powershell
# Run full test suite (from project root)
python -m pytest

# Run with verbose output and coverage
python -m pytest -v --cov=a2a --cov-report=term-missing

# Run a specific test file
python -m pytest tests/test_guardrails.py -v

# Run a specific test
python -m pytest tests/test_guardrails.py::test_function_name -v

# Run only CSTP service tests
python -m pytest tests/test_f002_query_decisions.py tests/test_f003_check_guardrails.py -v
```

### Test Configuration

Defined in `pyproject.toml`:

- `asyncio_mode = "auto"` — async tests run automatically
- `testpaths = ["tests"]` — test discovery root
- `addopts = "-v --cov=a2a --cov-report=term-missing"` — default verbose + coverage

### Test Conventions

1. Test files are named `test_<module>.py` or `test_f0XX_<feature>.py` for feature-specific tests.
2. Use `pytest-asyncio` for async handler and service tests.
3. Mock external dependencies (ChromaDB, Gemini API) — never make real external calls in tests.
4. Each test file should test one module or one CSTP method.

---

## 8. Code Quality & Linting

### Tools

| Tool | Config location | Purpose |
|------|----------------|---------|
| **ruff** | `pyproject.toml [tool.ruff]` | Linting + import sorting |
| **mypy** | `pyproject.toml [tool.mypy]` | Static type checking (strict) |

### Ruff Rules

```toml
line-length = 100
target-version = "py311"
select = ["E", "F", "I", "N", "W", "UP", "B", "C4", "SIM"]
ignore = ["E501", "SIM108", "I001", "UP045", "SIM110", "SIM105", "SIM102"]
```

### Running Linters

```powershell
# Lint check
python -m ruff check .

# Auto-fix
python -m ruff check --fix .

# Type check
python -m mypy src/ a2a/
```

---

## 9. Docker Deployment

### Architecture

- **Multi-stage Dockerfile** (`python:3.11-slim`):
  - Builder stage: installs dependencies with `uv`
  - Runtime stage: copies only site-packages + app code
  - Runs as non-root user (`appuser`)
  - Health check: `curl http://localhost:8100/health`

### Commands

```powershell
# Build and start (CSTP server + ChromaDB)
docker-compose up -d

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker-compose logs -f cstp-server

# Health check
curl http://localhost:8100/health
```

### Services

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `cstp-server` | Custom (Dockerfile) | 8100 | CSTP JSON-RPC server |
| `chromadb` | `chromadb/chroma:0.4.22` | 8000 | Vector database |

---

## 10. Coding Conventions

### Style

- **Python 3.11+** features encouraged: `match` statements, `type X = ...` aliases, `X | Y` union syntax.
- **Dataclasses** with `@dataclass(slots=True)` for config/model objects in the core library.
- **Pydantic v2 models** only in the `a2a/` layer.
- **Type hints** on all function signatures. `mypy --strict` must pass.
- **Docstrings** on all public classes and functions (Google style).
- **Line length:** 100 characters max.

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `query_service.py` |
| Classes | `PascalCase` | `SemanticIndex` |
| Functions | `snake_case` | `query_decisions` |
| Constants | `UPPER_SNAKE` | `EMBEDDING_DIM` |
| CSTP methods | `cstp.camelCase` | `cstp.queryDecisions` |
| Handler functions | `_handle_snake_case` | `_handle_query_decisions` |
| Test files | `test_<module>.py` or `test_f0XX_<feature>.py` | `test_f002_query_decisions.py` |

### Patterns to Follow

1. **Service pattern:** CSTP methods delegate to `*_service.py` modules. Handlers in `dispatcher.py` are thin wrappers.
2. **Singleton access:** Use `get_index()`, `get_engine()`, `get_dispatcher()` — never instantiate global instances directly.
3. **Error handling in handlers:** Catch specific exceptions, return `JsonRpcError` with appropriate error codes defined in `dispatcher.py`.
4. **No runtime imports in core:** `src/cognition_engines/` must not import from `a2a/`.

### Error Codes (JSON-RPC)

```python
PARSE_ERROR      = -32700  # Invalid JSON
INVALID_REQUEST  = -32600  # Bad JSON-RPC structure
METHOD_NOT_FOUND = -32601  # Unknown method
INVALID_PARAMS   = -32602  # Bad params
QUERY_FAILED     = -32003  # Query service error
RATE_LIMITED     = -32002  # Rate limit exceeded
GUARDRAIL_EVAL_FAILED = -32004  # Guardrail evaluation error
RECORD_FAILED    = -32005  # Decision recording error
REVIEW_FAILED    = -32006  # Decision review error
DECISION_NOT_FOUND = -32007  # Decision ID not found
ATTRIBUTION_FAILED = -32008  # Attribution error
```

---

## 11. Adding a New Feature — Checklist

1. **Check existing specs:** Look in `docs/specs/` for related feature specs (F001–F020).
2. **Design:** If the feature introduces a new CSTP method, follow the pattern in `docs/CSTP-v0.7.0-DESIGN.md`.
3. **Implement core logic** in `src/cognition_engines/` if it's framework-agnostic.
4. **Implement CSTP handler** in `a2a/cstp/`:
   - Service function in `*_service.py`
   - Handler in `dispatcher.py`
   - Register in `register_methods()`
   - Models in `models.py`
5. **Write tests** in `tests/test_f0XX_<feature>.py`.
6. **Run full test suite:** `python -m pytest`
7. **Update guardrails** if the feature involves policy decisions (add YAML to `guardrails/`).
8. **Update documentation:**
   - `README.md` for user-facing summaries
   - `ProductDocumentation/` for detailed guides
   - `docs/specs/` for the feature spec
9. **Verify linting:** `python -m ruff check .`

---

## 12. Key Files to Read First

When starting any work on this project, read these files in order:

1. **This file** (`AGENTS.md`) — You're here
2. **`README.md`** — User-facing overview and quick start
3. **`pyproject.toml`** — Dependencies, build config, tool settings
4. **`a2a/cstp/dispatcher.py`** — All CSTP method handlers (the primary entry point for server logic)
5. **`src/cognition_engines/guardrails/engine.py`** — Core guardrail engine
6. **`src/cognition_engines/accelerators/semantic_index.py`** — Core semantic search
7. **`docs/CSTP-v0.7.0-DESIGN.md`** — Full protocol specification
8. **`config/server.yaml`** — Default server configuration

---

## 13. Common Pitfalls

| Pitfall | What to do instead |
|---------|-------------------|
| Importing `fastapi` in `src/cognition_engines/` | Core library must stay web-framework-free. Web concerns belong in `a2a/`. |
| Making real HTTP calls to ChromaDB/Gemini in tests | Always mock external APIs. Tests must run offline. |
| Forgetting to register a new handler | New CSTP methods must be registered in `register_methods()` in `dispatcher.py`. |
| Hardcoding paths with forward slashes | Use `pathlib.Path` for all file operations. Project runs on Windows. |
| Creating config without env var fallback | Follow the established pattern: YAML → env var → default. See `config.py`. |
| Editing guardrail YAML without testing | Guardrail YAML is loaded and evaluated at runtime. Always add unit tests for new rules. |
| Adding dependencies without updating `pyproject.toml` | All dependencies must be declared in `pyproject.toml` under the appropriate optional group. |
| Using `pydantic` in core library | Pydantic is only in the `a2a/` layer (optional `[a2a]` dependency group). Core uses dataclasses. |

---

## 14. Dashboard (Separate Application)

The `dashboard/` directory is a **standalone Flask application** with its own Dockerfile and `pyproject.toml`. It communicates with the CSTP server via `cstp_client.py` (async HTTP client).

**Key routes:**

- `GET /health` — Health check (no auth)
- `GET /decisions` — Paginated decision list with filters
- `GET /decisions/<id>` — Decision detail view
- `GET /decisions/<id>/review` — Review form (GET) / submit review (POST)
- `GET /calibration` — Calibration dashboard with Brier scores and drift detection

**Dashboard has its own test suite** under `dashboard/tests/`.

---

## 15. CI/CD

GitHub Actions workflows are in `.github/workflows/`. When modifying CI:

- Ensure all tests pass before merging: `python -m pytest`
- Maintain coverage for the `a2a/` package

---

## 16. Useful Commands Summary

```powershell
# Install
python -m pip install -e ".[all]"

# Test (full suite)
python -m pytest

# Test (specific)
python -m pytest tests/test_guardrails.py -v

# Lint
python -m ruff check .

# Lint auto-fix
python -m ruff check --fix .

# Type check
python -m mypy src/ a2a/

# Run CSTP server locally
python -m a2a.server --host 0.0.0.0 --port 8100

# Docker
docker-compose up -d --build

# Health check
curl http://localhost:8100/health
```
