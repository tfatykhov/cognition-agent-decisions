# Module Reference

This document provides a detailed breakdown of every module, class, and function in the Cognition Engines codebase.

---

## 1. Core Library — `src/cognition_engines/`

### 1.1 Accelerators — `accelerators/`

#### `semantic_index.py`

The heart of the decision memory system. Provides vector-based similarity search over decisions using ChromaDB and Google Gemini embeddings.

##### Module-Level Functions

| Function | Description |
|----------|-------------|
| `load_gemini_key()` | Loads Gemini API key from secrets files if not present in environment |
| `api_request(method, url, data)` | Makes HTTP requests to ChromaDB REST API |
| `generate_embedding(text)` | Generates a 768-dimensional embedding vector via Gemini `text-embedding-004` |
| `get_api_base()` | Returns the ChromaDB API base URL from environment |
| `get_or_create_collection()` | Ensures the `cognition_decisions` collection exists in ChromaDB |
| `decision_to_text(decision)` | Converts a decision dict into searchable text (title + category + context + reasons) |
| `decision_id(decision)` | Generates a deterministic MD5 hash ID from decision title |
| `get_index()` | Returns the singleton `SemanticIndex` instance |

##### `SemanticIndex` Class

| Method | Description |
|--------|-------------|
| `__init__()` | Initializes with `collection_id = None` |
| `ensure_collection()` | Lazily creates/gets the ChromaDB collection |
| `index_decision(decision)` | Indexes a single decision: generates embedding, constructs metadata, upserts to ChromaDB |
| `index_decisions(decisions)` | Batch indexes a list of decisions, returns count |
| `query(context, n_results, category, min_confidence)` | Generates embedding for query text, performs filtered vector search, returns ranked results |
| `count()` | Returns the number of indexed decisions in the collection |

**Metadata stored per decision:**

- `title`, `category`, `confidence`, `stakes`, `date`, `status`, `outcome`, `project`, `feature`, `pr`, `reason_types`

---

### 1.2 Guardrails — `guardrails/`

#### `engine.py`

The main guardrail evaluation engine. Loads YAML guardrail definitions and evaluates them against decision contexts.

##### Data Classes

| Class | Fields | Description |
|-------|--------|-------------|
| `GuardrailCondition` | `field`, `operator`, `value` | A condition that must match for a guardrail to apply (e.g., `stakes == "high"`) |
| `GuardrailRequirement` | `field`, `expected` | A requirement that must be met (e.g., `code_review_completed == true`) |
| `Guardrail` | `id`, `description`, `conditions`, `requirements`, `scope`, `action`, `message` | Full guardrail definition |
| `GuardrailResult` | `guardrail_id`, `passed`, `action`, `message`, `failed_requirements` | Result of evaluating one guardrail |

##### `GuardrailEngine` Class

| Method | Description |
|--------|-------------|
| `load_from_yaml(content)` | Parses YAML string and loads guardrail definitions. Returns count loaded |
| `load_from_file(path)` | Loads guardrails from a single YAML file |
| `load_from_directory(directory)` | Recursively loads all `.yaml`/`.yml` files from a directory |
| `evaluate(context)` | Evaluates all guardrails against a context dict, returns list of `GuardrailResult` |
| `check(context)` | Convenience method: returns `(allowed: bool, results: list)` |
| `list_guardrails()` | Returns list of all loaded guardrail definitions as dicts |

**Condition operators:** `=`, `!=`, `<`, `>`, `<=`, `>=`, `in`, `not in`

##### Module-Level Functions

| Function | Description |
|----------|-------------|
| `parse_condition(field, value)` | Parses a condition from YAML format, detecting operator from string prefix |
| `parse_guardrail(data)` | Parses a full guardrail from YAML dict (supports flat `condition_*` and nested formats) |
| `get_engine()` | Returns the singleton `GuardrailEngine` instance |
| `load_default_guardrails()` | Loads guardrails from `guardrails/` directory |

#### `evaluators.py`

Advanced condition evaluators for the v2 guardrail format. Provides pluggable evaluation strategies.

| Class | Type | Description |
|-------|------|-------------|
| `ConditionEvaluator` | Protocol | Abstract protocol for condition evaluators |
| `FieldCondition` | Evaluator | Simple field comparison with extended operators |
| `SemanticCondition` | Evaluator | Checks semantic similarity to past decisions matching criteria. Fields: `query_field`, `threshold`, `filter_outcome`, `filter_since_days`, `min_matches` |
| `TemporalCondition` | Evaluator | Time-window check: "Was a similar decision made within N hours?" |
| `AggregateCondition` | Evaluator | Statistical check across decision history: "Is category success rate below 50%?" |
| `CompoundCondition` | Evaluator | AND/OR logical composition of multiple conditions |

`parse_condition_v2(condition_def)` — Factory function that creates the appropriate evaluator from a YAML condition definition.

#### `audit.py`

Audit trail system for guardrail evaluations.

| Class | Description |
|-------|-------------|
| `GuardrailEvaluation` | Record of a single guardrail check: `guardrail_id`, `matched`, `passed`, `action`, `message` |
| `AuditRecord` | Complete audit for one decision: list of evaluations, `overall_allowed`, optional `override` with reason |
| `AuditLog` | Manager that creates records, saves to JSON files, queries violations, and computes aggregate stats |

**Output formats:** JSON files (`audit/YYYY-MM-DD-<decision_id>.json`) and embeddable YAML blocks.

---

### 1.3 Patterns — `patterns/`

#### `detector.py`

Analyzes decision history for patterns, calibration accuracy, and anti-patterns.

##### Data Classes

| Class | Description |
|-------|-------------|
| `CalibrationBucket` | Confidence range bucket: computes predicted rate, actual success rate, and Brier score |
| `CategoryStats` | Per-category statistics: count, average confidence, success rate |
| `AntiPattern` | Detected anti-pattern: type, description, severity, affected decisions |

##### `PatternDetector` Class

| Method | Description |
|--------|-------------|
| `load_from_directory(directory)` | Recursively loads all YAML decision files |
| `calibration_report()` | Generates Brier scores for 5 confidence buckets (0-0.2, 0.2-0.4, ..., 0.8-1.0) |
| `category_analysis()` | Success rates and patterns per category, identifies concerning categories |
| `detect_antipatterns()` | Detects: overcalibration, flip-flopping, anchoring, blind spots, hot-hand fallacy |
| `full_report()` | Combines calibration + category + antipattern reports |

---

## 2. A2A Layer — `a2a/`

### 2.1 `server.py` — FastAPI Application

| Function | Description |
|----------|-------------|
| `lifespan(app)` | Async context manager: loads config, initializes `AuthManager`, creates `CstpDispatcher`, registers methods, initializes MCP `StreamableHTTPSessionManager` and runs it within the lifespan context |
| `create_app(config)` | Factory: creates FastAPI app with CORS, lifespan, routes, and MCP mount at `/mcp` |
| `_mount_mcp(app)` | Mounts the MCP Streamable HTTP handler as a raw ASGI app at `/mcp`; returns 503 if MCP SDK not installed |
| `_register_routes(app)` | Registers `/health`, `/.well-known/agent.json`, and `POST /cstp` |
| `run_server(host, port, config_path)` | Entry point: loads config, creates app, runs uvicorn |

### 2.2 `mcp_server.py` — MCP Server

Exposes CSTP capabilities as MCP tools for native integration with MCP-compliant agents (Claude Desktop, Claude Code, OpenClaw, etc.).

| Component | Description |
|-----------|-------------|
| `mcp_app` | `Server("cstp-decisions")` instance — importable for mounting in ASGI apps |
| `list_tools()` | Returns 5 `Tool` definitions with JSON Schema auto-generated from Pydantic models |
| `call_tool(name, arguments)` | Dispatches tool calls to `_handle_*` functions; returns `TextContent` with JSON result |
| `_handle_query_decisions()` | Validates input via `QueryDecisionsInput`, calls `query_service.query_decisions()` |
| `_handle_check_action()` | Validates input via `CheckActionInput`, calls `guardrails_service.evaluate_guardrails()` |
| `_handle_log_decision()` | Validates input via `LogDecisionInput`, calls `decision_service.record_decision()` |
| `_handle_review_outcome()` | Validates input via `ReviewOutcomeInput`, calls `decision_service.review_decision()` |
| `_handle_get_stats()` | Validates input via `GetStatsInput`, calls `calibration_service.get_calibration()` |
| `run_stdio()` | Runs the MCP server with stdio transport (`async with stdio_server()`) |
| `main()` | Entry point: `asyncio.run(run_stdio())` |

**Transports:**

- **stdio** — `python -m a2a.mcp_server` (local or `docker exec -i cstp python -m a2a.mcp_server`)
- **Streamable HTTP** — Mounted at `/mcp` on port 8100 via `StreamableHTTPSessionManager` in `server.py` lifespan

### 2.3 `mcp_schemas.py` — MCP Input Schemas

Pydantic models that define the JSON Schema MCP clients see during tool discovery. They map to existing CSTP dataclass models but use Pydantic for automatic schema generation required by the MCP protocol.

| Schema | MCP Tool | Key Fields |
|--------|----------|------------|
| `QueryDecisionsInput` | `query_decisions` | `query` (str), `limit` (1–50), `retrieval_mode` (semantic/keyword/hybrid), `filters` (QueryFiltersInput) |
| `QueryFiltersInput` | (nested) | `category`, `stakes`, `project`, `has_outcome` |
| `CheckActionInput` | `check_action` | `description` (str), `category`, `stakes` (low/medium/high/critical), `confidence` (0.0–1.0) |
| `LogDecisionInput` | `log_decision` | `decision` (str), `confidence` (float), `category`, `stakes`, `context`, `reasons` (ReasonInput[]), `tags`, `project`, `feature`, `pr` |
| `ReasonInput` | (nested) | `type` (authority/analogy/analysis/pattern/intuition), `text` (str) |
| `ReviewOutcomeInput` | `review_outcome` | `id` (str), `outcome` (success/partial/failure/abandoned), `actual_result`, `lessons`, `notes` |
| `GetStatsInput` | `get_stats` | `category`, `project`, `window` (30d/60d/90d/all) |

### 2.4 `config.py` — Configuration Management

| Class | Description |
|-------|-------------|
| `AuthToken` | Agent + token pair |
| `AuthConfig` | `enabled` flag + list of `AuthToken`; `validate_token()` with constant-time comparison |
| `AgentConfig` | Agent identity: name, description, version, URL, contact |
| `ServerConfig` | HTTP settings: host, port, CORS origins |
| `Config` | Composite config with `from_yaml(path)`, `from_env()`, `_from_dict(data)` class methods |

**Config loading priority:** YAML file → Environment variables → Defaults

### 2.5 `auth.py` — Authentication

| Component | Description |
|-----------|-------------|
| `AuthManager` | Wraps `Config`, validates bearer tokens, returns agent ID |
| `verify_bearer_token()` | FastAPI `Depends` function for route-level auth |
| `set_auth_manager()` / `get_auth_manager()` | Global singleton management |

### 2.6 `models/` — Shared Models

| File | Classes |
|------|---------|
| `jsonrpc.py` | `JsonRpcRequest`, `JsonRpcResponse`, `JsonRpcError`, error codes (PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INTERNAL_ERROR) |
| `agent_card.py` | `AgentCard`, `AgentCapabilities` for `/.well-known/agent.json` |
| `health.py` | `HealthResponse` with status, version, uptime, timestamp |

---

## 3. CSTP Services — `a2a/cstp/`

### 3.1 `dispatcher.py` — Method Router

| Component | Description |
|-----------|-------------|
| `CstpDispatcher` | Registry of method name → async handler; dispatches requests, catches errors, returns JSON-RPC responses |
| `register_methods(dispatcher)` | Registers all 9 method handlers: `queryDecisions`, `checkGuardrails`, `listGuardrails`, `recordDecision`, `reviewDecision`, `getCalibration`, `attributeOutcomes`, `checkDrift`, `reindex` |
| Custom error codes | `QUERY_FAILED` (-32003), `RATE_LIMITED` (-32002), `GUARDRAIL_EVAL_FAILED` (-32004), `RECORD_FAILED` (-32005), `REVIEW_FAILED` (-32006), `DECISION_NOT_FOUND` (-32007), `ATTRIBUTION_FAILED` (-32008) |

### 3.2 `query_service.py` — Semantic Search

| Component | Description |
|-----------|-------------|
| `QueryResult` | Single result: id, title, category, confidence, distance |
| `QueryResponse` | Wrapper with results list, query, timing |
| `query_decisions()` | Full query pipeline: embedding, ChromaDB search, metadata filtering, optional BM25 hybrid |
| `load_all_decisions()` | Loads YAML files from disk for BM25 indexing |

### 3.3 `decision_service.py` — Decision Recording & Review

| Component | Description |
|-----------|-------------|
| `BridgeDefinition` | Dataclass: structure, function, tolerance, enforcement, prevention |
| `Reason` | Decision reason with type, text, strength |
| `PreDecisionProtocol` | Tracks whether query was run and guardrails were checked before recording |
| `ProjectContext` | Project, feature, PR, file, line, commit associations |
| `ReasoningStep` | Step in a reasoning trace: step number, thought, output, confidence, tags |
| `RecordDecisionRequest` | Full request with validation: decision text, confidence, category, stakes, reasons, review_in |
| `RecordDecisionResponse` | Success indicator, generated ID, file path, index status |
| `ReviewDecisionRequest` | Review request: decision ID, outcome, actual result, lessons |
| `review_decision()` | Loads decision YAML, updates with outcome and review metadata, reindexes in ChromaDB |
| `build_decision_yaml()` | Constructs the YAML dictionary structure |
| `write_decision_file()` | Writes to `decisions/YYYY/MM/YYYY-MM-DD-decision-<id>.yaml` |
| `generate_embedding(text)` | Gemini embedding for ChromaDB indexing |
| `ensure_collection_exists()` | ChromaDB collection management |

### 3.4 `calibration_service.py` — Confidence Calibration

| Component | Description |
|-----------|-------------|
| `GetCalibrationRequest` | Filters: agent, category, stakes, date range, window, project, feature |
| `CalibrationResult` | Overall: Brier score, accuracy, calibration gap, interpretation |
| `ConfidenceBucket` | Per-bucket: decisions, success rate, expected rate, gap, interpretation |
| `ConfidenceStats` | Distribution stats: mean, std_dev, min, max, bucket counts |
| `CalibrationRecommendation` | Actionable recommendation with type, message, severity |
| `get_reviewed_decisions()` | Loads reviewed decisions matching filters from YAML files |
| `calculate_calibration()` | Computes Brier score: `mean((confidence - outcome)²)` |
| `calculate_buckets()` | Splits into 5 confidence buckets and computes per-bucket stats |
| `calculate_confidence_stats()` | Habituation detection: identifies low-variance confidence patterns |
| `generate_recommendations()` | Produces actionable advice based on calibration gaps |

### 3.5 `attribution_service.py` — Outcome Attribution

| Component | Description |
|-----------|-------------|
| `AttributeOutcomesRequest` | Project, since date, stability days, dry_run flag |
| `find_pending_decisions()` | Finds pending decisions for a project |
| `is_pr_stable()` | Checks if PR is older than stability window (simplified) |
| `update_decision_outcome()` | Atomic file update: marks as reviewed with outcome + reason |
| `attribute_outcomes()` | Main pipeline: find pending → check stability → update files |

### 3.6 `drift_service.py` — Calibration Drift Detection

| Component | Description |
|-----------|-------------|
| `CheckDriftRequest` | Thresholds for Brier and accuracy, category/project filters |
| `DriftAlert` | Alert: type (brier_degradation/accuracy_drop), recent vs. historical values, change %, severity |
| `check_drift()` | Compares 30-day calibration against 90-day+ baseline |
| `generate_drift_recommendations()` | Actionable recommendations based on drift alerts |

### 3.7 `guardrails_service.py` — Guardrail Evaluation (CSTP)

| Component | Description |
|-----------|-------------|
| `evaluate_guardrails(context)` | Loads guardrails (cached 5 min), evaluates, returns violations/warnings |
| `list_guardrails(scope)` | Lists active guardrails, optionally filtered by scope |
| `log_guardrail_check()` | Structured audit logging |

### 3.8 `reindex_service.py` — Collection Rebuild

| Component | Description |
|-----------|-------------|
| `reindex_decisions()` | Full pipeline: delete collection → create → load decisions → generate embeddings → batch insert |
| `ReindexResult` | Success, count indexed, errors, duration |

### 3.9 `bm25_index.py` — Keyword Search

| Component | Description |
|-----------|-------------|
| `BM25Index` | Wraps `rank-bm25` BM25Okapi algorithm |
| `BM25Index.from_decisions()` | Builds index from decision dicts |
| `BM25Index.search()` | Returns ranked `(doc_id, score)` pairs |
| `tokenize(text)` | Simple word tokenization with lowercasing |
| `merge_results()` | Weighted merge of semantic + keyword results (default 70/30) |
| `get_cached_index()` | 5-minute TTL cache with count-based invalidation |

### 3.10 `deliberation_tracker.py` — Deliberation Traces

Tracks input/reasoning steps across API calls to build full deliberation traces.

| Component | Description |
|-----------|-------------|
| `TrackedInput` | Dataclass: type (query/check), content, timestamp, source |
| `TrackerSession` | Per-agent session state with inputs list and start time |
| `DeliberationTracker` | Singleton manager for active deliberation sessions |
| `track_query(agent_id, query)` | Hooks into `queryDecisions` to record search inputs |
| `track_check(agent_id, action)` | Hooks into `checkGuardrails` to record constraint inputs |
| `track_lookup(agent_id, id)` | Hooks into `getDecision` to record reference inputs |
| `auto_attach_deliberation(agent_id)` | Returns and clears tracked inputs for `recordDecision` |

### 3.11 `bridge_extractor.py` — Bridge Auto-Extraction

Extracts structure/function pairs from decision text when not explicitly provided.

| Component | Description |
|-----------|-------------|
| `auto_extract_bridge(text, context)` | Main entry point: heuristic extraction pipeline |
| `_score_as_function(text)` | Scorer: how likely is text to be a function/purpose? |
| `_score_as_structure(text)` | Scorer: how likely is text to be a structure/pattern? |

### 3.12 `bridge_hook.py` — Shared Hook

| Component | Description |
|-----------|-------------|
| `maybe_auto_extract_bridge(req)` | Wraps extraction logic for use in `decision_service` |

### 3.13 `models.py` — CSTP Data Models

| Model | Used By |
|-------|---------|
| `QueryFilters` | `cstp.queryDecisions` — category, confidence, stakes, status, project, feature, PR, has_outcome |
| `QueryDecisionsRequest` | `cstp.queryDecisions` — query text, bridge_side (structure/function), filters, limit |
| `DecisionSummary` | Query results — id, title, category, confidence, distance, reasons |
| `QueryDecisionsResponse` | Wrapper with decisions, total, timing, retrieval mode, scores |
| `ActionContext` | `cstp.checkGuardrails` — description, category, stakes, confidence, context dict |
| `CheckGuardrailsRequest` | Action + agent info |
| `GuardrailViolation` | Block/warn result with id, name, message, severity, suggestion |
| `CheckGuardrailsResponse` | allowed flag, violations, warnings, evaluated count |

---

## 4. Dashboard — `dashboard/`

### `app.py` — Flask Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Redirects to `/decisions` |
| `/health` | GET | Health check (no auth) |
| `/decisions` | GET | Paginated decision list with category/status filters |
| `/decisions/<id>` | GET | Decision detail view |
| `/decisions/<id>/review` | GET/POST | Review form for recording outcomes |
| `/calibration` | GET | Calibration dashboard with drift detection |

### `cstp_client.py` — CSTP Client

Async HTTP client for communicating with the CSTP server. Uses `httpx` for non-blocking requests.

| Method | Description |
|--------|-------------|
| `health_check()` | Check CSTP server health |
| `list_decisions()` | Query decisions with pagination |
| `get_decision(id)` | Get single decision by ID |
| `review_decision()` | Submit decision review |
| `get_calibration()` | Get calibration statistics |
| `check_drift()` | Check for calibration drift |

---

## 5. CLI — `bin/cognition`

| Command | Description |
|---------|-------------|
| `cognition index <dir>` | Index all YAML decisions from a directory |
| `cognition query <context>` | Search for similar decisions |
| `cognition check --stakes high --confidence 0.8` | Evaluate guardrails for a context |
| `cognition guardrails` | List all loaded guardrails |
| `cognition count` | Count indexed decisions |
| `cognition patterns calibration` | Confidence calibration report (Brier scores) |
| `cognition patterns categories` | Category success analysis |
| `cognition patterns antipatterns` | Detect decision anti-patterns |
| `cognition patterns full` | Complete pattern report (JSON) |

---

## 6. Test Suite — `tests/`

| Test File | Coverage |
|-----------|----------|
| `test_a2a_server.py` | FastAPI app creation, health endpoint, agent card, CSTP dispatch |
| `test_decision_service.py` | Decision recording, YAML generation, validation |
| `test_query_service.py` | Semantic query pipeline |
| `test_guardrails.py` | Core guardrail engine evaluation |
| `test_guardrails_service.py` | CSTP guardrail service |
| `test_evaluators.py` | v2 condition evaluators |
| `test_audit.py` | Audit trail creation and querying |
| `test_patterns.py` | Pattern detection and calibration |
| `test_calibration_service.py` | Calibration computation and recommendations |
| `test_attribution_service.py` | Outcome attribution pipeline |
| `test_semantic_index.py` | ChromaDB semantic index |
| `test_config_env.py` | Configuration loading |
| `test_f002_query_decisions.py` | F002 feature: query decisions |
| `test_f003_check_guardrails.py` | F003 feature: check guardrails |
| `test_f007_record_decision.py` | F007 feature: record decision |
| `test_f008_review_decision.py` | F008 feature: review decision |
| `test_f009_get_calibration.py` | F009 feature: get calibration |
