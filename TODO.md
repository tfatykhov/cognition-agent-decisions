# TODO — Cognition Engines Roadmap

Prioritized work items. Check off as completed. See `docs/features/` for full specs.

## P0 — Ship Next (v0.12.0)

### F048: Multi-Vector-DB Support ✅
Extract ChromaDB coupling behind a provider abstraction.
- [x] Define `VectorStore` ABC in `a2a/cstp/vectordb/__init__.py`
- [x] Define `EmbeddingProvider` ABC in `a2a/cstp/embeddings/__init__.py`
- [x] Extract ChromaDB HTTP logic from `query_service.py` into `vectordb/chromadb.py`
- [x] Extract ChromaDB indexing from `decision_service.py` into `vectordb/chromadb.py`
- [x] Extract Gemini embedding logic into `embeddings/gemini.py`
- [x] Implement `MemoryStore` (in-memory backend for tests)
- [x] Add factory with `VECTOR_BACKEND` env var selection
- [x] Update `query_service.py` and `decision_service.py` to use `VectorStore` interface
- [x] Verify all existing tests pass (zero behavior change)
- [x] Add tests for `MemoryStore` backend
- Spec: `docs/features/F048-multi-vectordb.md`

### F044: Agent Work Discovery ✅
`cstp.ready` endpoint that surfaces prioritized cognitive actions.
- [x] Implement `ready_service.py` with action types: `review_outcome`, `calibration_drift`, `stale_pending`
- [x] Add `cstp.ready` JSON-RPC method to dispatcher
- [x] Add `ready` MCP tool (PRIMARY level)
- [x] Add `--min-priority` and `--type` filtering
- [x] Add tests
- [ ] Add `cstp.py ready` CLI command
- Spec: `docs/features/F044-agent-work-discovery.md`

### Bug fixes / improvements
- [x] Fix F047 MCP handler: `format` param not forwarded to `SessionContextRequest` (returns JSON instead of markdown via MCP)
- [x] Merge F046/F047 feature branch PR if still open (`fix/session-context-format-param`)
- [x] Fix #120: `pre_action` auto_record now attaches deliberation, related decisions, and bridge extraction

## P1 — High Priority

### F041: Memory Compaction ✅
Semantic decay for old resolved decisions.
- [x] Define compaction levels (full → summary → digest → wisdom)
- [x] Implement time-based compaction in query responses (`cstp.getCompacted`)
- [x] Add `cstp.compact` endpoint for manual trigger
- [x] Add `cstp.getWisdom` for category-level distilled principles
- [x] `preserve: true` flag via `cstp.setPreserve`
- [ ] LLM-generated summaries for summary/digest levels (P2)
- [ ] Integrate compacted results into `get_session_context`
- Spec: `docs/features/F041-memory-compaction.md`

### F045: Decision Graph Storage Layer ✅
- [x] Add `networkx` dependency
- [x] Initialize graph from existing `related_to` data on startup
- [x] Implement `cstp.linkDecisions` (create typed edges)
- [x] Implement `cstp.getGraph` (subgraph query with depth + edge type filter)
- [x] JSONL persistence for graph edges (`GRAPH_DATA_PATH` env var)
- [x] Edge types: `relates_to`, `supersedes`, `depends_on`
- [x] Thread safety (asyncio.Lock)
- [x] GraphStore ABC + factory pattern
- [ ] Add `cstp.getNeighbors` (lightweight neighbor query)
- [ ] Auto-linking in `recordDecision` flow
- [ ] MCP tool registration for graph endpoints
- Spec: `docs/features/F045-graph-storage-layer.md`

### F030: Circuit Breaker Guardrails
Adaptive guardrails that trip based on outcome patterns.
- [ ] Track failure counts per category/pattern
- [ ] Auto-trip after N failures in a window
- [ ] `cstp.listBreakers` endpoint
- [ ] Manual reset via `cstp.resetBreaker`
- Spec: `docs/features/F030-circuit-breaker-guardrails.md`

### Weaviate backend (F048 P2)
- [ ] Implement `vectordb/weaviate.py` with native hybrid search
- [ ] Map `hybrid_query` to Weaviate's `alpha` fusion parameter
- [ ] Add Docker compose example
- [ ] Integration tests

### pgvector backend (F048 P2)
- [ ] Implement `vectordb/pgvector.py`
- [ ] SQL-based hybrid search (pgvector + pg_trgm)
- [ ] Add Docker compose example
- [ ] Integration tests

## P2 — Medium Priority

### F034: Decomposed Confidence
Break confidence into epistemic, aleatory, and model components.
- [ ] Add confidence components to decision model
- [ ] Calibration per component type
- [ ] Update `recordDecision` to accept components
- Spec: `docs/features/F034-decomposed-confidence.md`

### F040: Task-Decision Graph
Link decisions to executable tasks with dependencies.
- [ ] Task data model (id, decision_id, status, assignee, dependencies)
- [ ] `cstp.createTask`, `cstp.updateTask`, `cstp.listTasks` endpoints
- [ ] Task completion triggers outcome review
- Spec: `docs/features/F040-task-decision-graph.md`

### F045 P2: Salience + Dual Retrieval
- [ ] PageRank-based salience scoring
- [ ] `cstp.computeSalience`, `cstp.getHighSalience` endpoints
- [ ] Dual retrieval: merge semantic (ChromaDB) + structural (graph) results
- [ ] Salience-based compaction priority (upgrade F041)

### F033: Censor Layer
- [ ] Implement Minsky Ch 27 censor for blocking bad decision patterns
- Spec: `docs/features/F033-censor-layer.md`

### Dashboard: Live Deliberation Viewer
- [ ] Show open thought sessions from `cstp.debugTracker` in dashboard UI
- [ ] Real-time updates (polling or SSE)
- [ ] Per-session breakdown: agent key, input count, thought text, age
- [ ] Visual indicator for thought accumulation and consumption

### Other improvements
- [ ] Add date-range filtering to `cstp.queryDecisions` (`dateFrom`/`dateTo` params)

### Embedding providers (F048 P3)
- [ ] `embeddings/openai.py` — text-embedding-3-small/large
- [ ] `embeddings/ollama.py` — Local models (nomic-embed-text)
- [ ] `EMBEDDING_PROVIDER` env var selection

## P3 — Future

### F035-F039: Multi-Agent & Federation
- [ ] F035: Semantic State Transfer
- [ ] F036: Reasoning Continuity
- [ ] F037: Collective Innovation
- [ ] F038: Cross-Agent Federation
- [ ] F039: Cognition Protocol Stack
- Specs: `docs/features/F035-*.md` through `F039-*.md`

### F043: Distributed Decision Merge
- [ ] Content-addressable decision IDs
- [ ] Offline recording with local SQLite cache
- [ ] Sync/merge protocol with conflict detection
- Spec: `docs/features/F043-distributed-merge.md`

### F045 P3-P4: Advanced Graph
- [ ] `contradicts` and `blocks` edge types
- [ ] Graph-constraint guardrails
- [ ] Auto-edge detection on `recordDecision`
- [ ] Graph visualization in dashboard (D3.js)
- [ ] Optional Neo4j backend

### Other
- [ ] F020: Structured Reasoning Traces
- [ ] F029: Task Router
- [ ] F031: Source Trust Scoring
- [ ] F032: Error Amplification Tracking

## Website / Docs
- [ ] Update website for custom domain (cognition-engines.ai) — done ✅
- [ ] Add F046/F047 guide pages
- [x] Add F048 architecture diagram
- [ ] Version badge update to v0.11.0+

## Done ✅
- [x] F001-F011: Core CSTP server (v0.8.0)
- [x] F014-F017: Calibration + hybrid retrieval (v0.9.0)
- [x] F019: List guardrails (v0.9.1)
- [x] F022-F028: MCP, deliberation traces, bridge-definitions, decision quality (v0.10.0)
- [x] F046: Pre-Action Hook API
- [x] F047: Session Context Endpoint
- [x] F047: Fix MCP handler `format` param forwarding
- [x] F048 P1: Multi-Vector-DB Support — VectorStore/EmbeddingProvider ABCs, ChromaDB + MemoryStore backends, factory pattern (v0.12.0)
- [x] F044: Agent Work Discovery — `cstp.ready` endpoint with review_outcome, calibration_drift, stale_pending action types, MCP tool, priority/category/type filtering, warnings for partial results
- [x] MCP tool descriptions updated (PRIMARY vs Granular)
- [x] Claude Code / Desktop MCP setup docs
- [x] Custom domain base path fix
- [x] F045 P1: Decision Graph Storage Layer — GraphStore ABC + factory, NetworkX + MemoryGraphStore backends, JSONL persistence, `cstp.linkDecisions` + `cstp.getGraph` endpoints, graph init from `related_to` YAML data
- [x] F041: Memory Compaction — 4 levels (full/summary/digest/wisdom), `cstp.compact`, `cstp.getCompacted`, `cstp.getWisdom`, `cstp.setPreserve`
- [x] Fix #120: pre_action auto_record deliberation/related/bridge attachment
