# TODO — Cognition Engines Roadmap

Prioritized work items. Check off as completed. See `docs/features/` for full specs.

## P0 — Ship Next (v0.12.0)

### F048: Multi-Vector-DB Support
Extract ChromaDB coupling behind a provider abstraction.
- [ ] Define `VectorStore` ABC in `a2a/cstp/vectordb/__init__.py`
- [ ] Define `EmbeddingProvider` ABC in `a2a/cstp/embeddings/__init__.py`
- [ ] Extract ChromaDB HTTP logic from `query_service.py` into `vectordb/chromadb.py`
- [ ] Extract ChromaDB indexing from `decision_service.py` into `vectordb/chromadb.py`
- [ ] Extract Gemini embedding logic into `embeddings/gemini.py`
- [ ] Implement `MemoryStore` (in-memory backend for tests)
- [ ] Add factory with `VECTOR_BACKEND` env var selection
- [ ] Update `query_service.py` and `decision_service.py` to use `VectorStore` interface
- [ ] Verify all existing tests pass (zero behavior change)
- [ ] Add tests for `MemoryStore` backend
- Spec: `docs/features/F048-multi-vectordb.md`

### F044: Agent Work Discovery
`cstp.ready` endpoint that surfaces prioritized cognitive actions.
- [ ] Implement `ready_service.py` with action types: `review_outcome`, `calibration_drift`, `stale_pending`
- [ ] Add `cstp.ready` JSON-RPC method to dispatcher
- [ ] Add `ready` MCP tool (PRIMARY level)
- [ ] Add `--min-priority` and `--type` filtering
- [ ] Add tests
- [ ] Add `cstp.py ready` CLI command
- Spec: `docs/features/F044-agent-work-discovery.md`

### Bug fixes / improvements
- [ ] Fix F047 MCP handler: `format` param not forwarded to `SessionContextRequest` (returns JSON instead of markdown via MCP)
- [ ] Merge F046/F047 feature branch PR if still open (`fix/session-context-format-param`)
- [ ] Add date-range filtering to `cstp.queryDecisions` (`dateFrom`/`dateTo` params)

## P1 — High Priority

### F041: Memory Compaction
Semantic decay for old resolved decisions.
- [ ] Define compaction levels (full → summary → digest → wisdom)
- [ ] Implement time-based compaction in query responses
- [ ] Add `cstp.compact` endpoint for manual trigger
- [ ] Add `cstp.getWisdom` for category-level distilled principles
- [ ] LLM-generated summaries for summary/digest levels
- [ ] `preserve: true` flag to skip compaction
- Spec: `docs/features/F041-memory-compaction.md`

### F045: Decision Graph Storage Layer (P1 — NetworkX foundation)
- [ ] Add `networkx` dependency
- [ ] Initialize graph from existing `related_to` data on startup
- [ ] Implement `cstp.linkDecisions` (create typed edges)
- [ ] Implement `cstp.getGraph` (subgraph query with depth + edge type filter)
- [ ] JSONL persistence for graph edges
- [ ] Edge types: `relates_to`, `supersedes`, `depends_on`
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
- [ ] Add F048 architecture diagram
- [ ] Version badge update to v0.11.0+

## Done ✅
- [x] F001-F011: Core CSTP server (v0.8.0)
- [x] F014-F017: Calibration + hybrid retrieval (v0.9.0)
- [x] F019: List guardrails (v0.9.1)
- [x] F022-F028: MCP, deliberation traces, bridge-definitions, decision quality (v0.10.0)
- [x] F046: Pre-Action Hook API
- [x] F047: Session Context Endpoint
- [x] MCP tool descriptions updated (PRIMARY vs Granular)
- [x] Claude Code / Desktop MCP setup docs
- [x] Custom domain base path fix
