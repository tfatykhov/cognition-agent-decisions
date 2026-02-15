# P0 Implementation Plan — v0.12.0

## Context

The P0 roadmap has 4 items. One is already done (F047 bug fix, merged in `0fac94c`). The remaining three are: F048 Multi-Vector-DB Support (extract ChromaDB/Gemini behind ABCs), F044 Agent Work Discovery (`cstp.ready` endpoint), and date-range filtering for `cstp.queryDecisions`. F048 is the foundation — it refactors the storage and embedding layers that all other features depend on.

## Implementation Order

1. ~~**F048: Multi-Vector-DB Support** (XL)~~ — **DONE** (branch `feat/f048-multi-vectordb`, 446 tests pass)
2. **Date-range filtering** (S) — rides on the refactored query_service
3. **F044: Agent Work Discovery** (M) — standalone feature, benefits from MemoryStore for testing
4. ~~F047 format param bug~~ — already merged, mark done in TODO.md

---

## 1. F048: Multi-Vector-DB Support

### Problem
ChromaDB HTTP API v2 is hardcoded in 3 service files (`query_service.py`, `decision_service.py`, `reindex_service.py`). Gemini embedding calls are duplicated in 4 places. Config is scattered across module-level globals. This makes it impossible to swap backends or test without mocking low-level HTTP calls.

### Approach: 7 steps

#### Step 1: Define ABCs

**Create `a2a/cstp/embeddings/__init__.py`** — `EmbeddingProvider` ABC:
- `async embed(text: str) -> list[float]`
- `async embed_batch(texts: list[str]) -> list[list[float]]` (default: sequential)
- Properties: `dimensions: int`, `model_name: str`, `max_length: int`

**Create `a2a/cstp/vectordb/__init__.py`** — `VectorStore` ABC + `VectorResult` dataclass:
- `async initialize() -> None`
- `async upsert(doc_id, document, embedding, metadata) -> bool`
- `async query(embedding, n_results, where) -> list[VectorResult]`
- `async delete(ids) -> bool`
- `async count() -> int`
- `async reset() -> bool` (for reindex)
- `async get_collection_id() -> str | None`

No `hybrid_query()` on the ABC — hybrid search stays orchestrated in the dispatcher (semantic via VectorStore + BM25 via `bm25_index.py`), matching current behavior. Future backends can add native hybrid support.

#### Step 2: Extract GeminiEmbeddings

**Create `a2a/cstp/embeddings/gemini.py`** — `GeminiEmbeddings(EmbeddingProvider)`:
- Extract from `query_service.py` lines 60-147 (`_get_secrets_paths`, `_load_gemini_key`, `_generate_embedding`)
- Merge with `decision_service.py` lines 870-893 (same logic, different function)
- Use `x-goog-api-key` header (secure pattern from query_service, not URL param)
- Model: `gemini-embedding-001`, dimensions: 768

#### Step 3: Extract ChromaDBStore

**Create `a2a/cstp/vectordb/chromadb.py`** — `ChromaDBStore(VectorStore)`:
- Extract query logic from `query_service.py` lines 150-265
- Extract indexing from `decision_service.py` lines 945-1034 (`ensure_collection_exists`, `index_to_chromadb`)
- Extract lifecycle from `reindex_service.py` lines 46-197 (`_delete_collection`, `_create_collection`, `_clear_collection`, `_add_to_collection`)
- Config via constructor: `url`, `collection`, `tenant`, `database` (read from env vars with same defaults)

#### Step 4: Implement MemoryStore

**Create `a2a/cstp/vectordb/memory.py`** — `MemoryStore(VectorStore)`:
- In-memory dict storage with cosine distance similarity
- Implement ChromaDB-style `where` matching (`$gte`, `$lte`, `$in`, `$contains`, `$or`)
- Used for tests and development without ChromaDB

#### Step 5: Factory functions

**Create `a2a/cstp/vectordb/factory.py`**:
- `create_vector_store()` — reads `VECTOR_BACKEND` env var (`chromadb` | `memory`)
- `get_vector_store()` — singleton accessor
- `set_vector_store(store)` — injection for tests

**Create `a2a/cstp/embeddings/factory.py`**:
- `create_embedding_provider()` — reads `EMBEDDING_PROVIDER` env var (`gemini`)
- `get_embedding_provider()` / `set_embedding_provider(provider)` — singleton + injection

#### Step 6: Refactor service files

**`a2a/cstp/query_service.py`**:
- Remove: `CHROMA_URL`, `GEMINI_API_KEY`, `TENANT`, `DATABASE`, `COLLECTION_NAME`, `_get_secrets_paths`, `_load_gemini_key`, `_async_request`, `_generate_embedding`, `_get_collection_id`
- Keep: `QueryResult`, `QueryResponse`, `load_all_decisions()`, `merge_results()` (BM25)
- Modify `query_decisions()`: use `get_vector_store().query()` + `get_embedding_provider().embed()`

**`a2a/cstp/decision_service.py`**:
- Remove: `CHROMA_URL`, `CHROMA_COLLECTION`, `CHROMA_TENANT`, `CHROMA_DATABASE`, `generate_embedding`, `ensure_collection_exists`, `index_to_chromadb`
- Keep: all dataclasses, `build_embedding_text()`, `record_decision()`, review/update functions
- Modify: replace `index_to_chromadb(...)` with `get_vector_store().upsert(...)`, replace `generate_embedding()` with `get_embedding_provider().embed()`

**`a2a/cstp/reindex_service.py`**:
- Remove: all ChromaDB imports and HTTP functions
- Modify: use `store.reset()` + `provider.embed()` + `store.upsert()`

**`src/cognition_engines/accelerators/semantic_index.py`**: NO CHANGES (different collection, different model, must not import from `a2a/`)

#### Step 7: Update tests

- Replace `@patch("a2a.cstp.query_service._generate_embedding")` patterns with `set_embedding_provider(mock)` / `set_vector_store(MemoryStore())`
- All existing test assertions must pass unchanged (zero behavior change)
- Add new tests:
  - `tests/test_f048_memory_store.py` — MemoryStore CRUD, where-clause matching
  - `tests/test_f048_chromadb_store.py` — ChromaDBStore with mocked httpx
  - `tests/test_f048_embeddings.py` — GeminiEmbeddings with mocked httpx
  - `tests/test_f048_factory.py` — env-var-based creation, injection

### Files modified
- `a2a/cstp/query_service.py` — major refactor
- `a2a/cstp/decision_service.py` — major refactor
- `a2a/cstp/reindex_service.py` — major refactor
- All test files that mock ChromaDB/embedding internals

### Files created
- `a2a/cstp/vectordb/__init__.py` — VectorStore ABC + VectorResult
- `a2a/cstp/vectordb/chromadb.py` — ChromaDBStore
- `a2a/cstp/vectordb/memory.py` — MemoryStore
- `a2a/cstp/vectordb/factory.py` — singleton factory
- `a2a/cstp/embeddings/__init__.py` — EmbeddingProvider ABC
- `a2a/cstp/embeddings/gemini.py` — GeminiEmbeddings
- `a2a/cstp/embeddings/factory.py` — singleton factory

---

## 2. Date-Range Filtering for queryDecisions

### Problem
`QueryFilters` already has `date_after`/`date_before` fields (models.py:15-16) that are parsed from `dateAfter`/`dateBefore` params but **never wired** into the actual ChromaDB where-clause or MCP schema.

### Approach

1. **`a2a/cstp/query_service.py`** — add `date_from`/`date_to` params to `query_decisions()`, include in `where` dict passed to `store.query()`:
   - `date_from` → `{"date": {"$gte": date_from}}`
   - `date_to` → `{"date": {"$lte": date_to}}`
   - Both → combine with `$and`

2. **`a2a/cstp/dispatcher.py`** — pass `request.filters.date_after`/`date_before` through to `query_decisions()` (formatted as `YYYY-MM-DD` strings)

3. **`a2a/mcp_schemas.py`** — add `date_from`/`date_to` string fields to `QueryFiltersInput`

4. **`a2a/mcp_server.py`** — forward the fields in `_build_query_params()`

5. **Tests** — extend `test_query_service.py` or add `test_f048_date_filter.py`

### Files modified
- `a2a/cstp/query_service.py`
- `a2a/cstp/dispatcher.py`
- `a2a/mcp_schemas.py`
- `a2a/mcp_server.py`
- Tests

---

## 3. F044: Agent Work Discovery

### Problem
No standalone endpoint for agents to discover what maintenance work needs attention. `session_context_service.py` has basic ready queue logic but it's embedded in the session context response, not independently queryable or filterable.

### Approach

1. **Create `a2a/cstp/ready_service.py`**:
   - `ReadyAction` dataclass (type, priority, reason, suggestion, decision_id, category)
   - `ReadyQueueRequest` dataclass with `from_params()` (min_priority, action_types, limit)
   - `ReadyQueueResponse` dataclass with `to_dict()`
   - `async get_ready_queue(request, agent_id) -> ReadyQueueResponse`
   - Action finders:
     - `_find_overdue_reviews(decisions)` — decisions past `review_by` date with no outcome
     - `_find_stale_pending(decisions)` — pending decisions older than 30 days
     - `_find_calibration_drift()` — categories where recent Brier score degraded >20% vs historical (uses `calibration_service`)

2. **Update `a2a/cstp/dispatcher.py`**:
   - Add `_handle_ready()` handler
   - Register `cstp.ready` in `register_methods()`

3. **Update `a2a/mcp_schemas.py`**:
   - Add `ReadyQueueInput` Pydantic model

4. **Update `a2a/mcp_server.py`**:
   - Add `ready` tool to `list_tools()` (PRIMARY level)
   - Add `_handle_ready_mcp()` handler in `call_tool()`

5. **Create `tests/test_f044_ready.py`**:
   - Model tests (from_params, to_dict)
   - Service tests with mocked `load_all_decisions()`
   - Priority and type filtering
   - Dispatcher round-trip

### Files created
- `a2a/cstp/ready_service.py`
- `tests/test_f044_ready.py`

### Files modified
- `a2a/cstp/dispatcher.py`
- `a2a/mcp_schemas.py`
- `a2a/mcp_server.py`

---

## 4. Mark F047 Bug as Done

Update `TODO.md` to check off:
- [x] Fix F047 MCP handler: `format` param not forwarded
- [x] Merge F046/F047 feature branch PR

---

## Verification

After each feature:
```bash
# All tests pass
python -m pytest

# Lint clean
ruff check src/ tests/ a2a/

# Type check
mypy src/ a2a/
```

End-to-end for F048: Start server with `VECTOR_BACKEND=chromadb`, record a decision, query it — verify identical response format. Then test with `VECTOR_BACKEND=memory` for the in-memory path.

End-to-end for F044: Call `cstp.ready` via JSON-RPC, verify it returns overdue reviews and stale decisions. Test via MCP tool.
