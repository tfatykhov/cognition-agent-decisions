# Changelog

## v0.15.0 - SQLite Storage & Performance
*February 21, 2026*

SQLite-backed storage with 8-42x performance gains, enriched search results, YAML auto-migration, and dashboard server-side integration.

### F050: SQLite Storage Layer
- **SQLite backend with WAL mode** - Full ACID compliance, concurrent reads, ~900 lines of battle-tested storage code
- **Normalized schema** - Separate tables for tags, reasons, bridge definitions, and deliberation traces
- **FTS5 full-text search** - Keyword search on decision text, context, and tags
- **Factory pattern** - `CSTP_STORAGE=sqlite` env var switches backend; `CSTP_DB_PATH` for file location
- **Abstract `DecisionStore` ABC** - Clean interface for future storage backends

### Auto-Migration
- **YAML → SQLite migration on startup** - Automatic, safe, uses upserts (re-runnable)
- **Standalone migration script** - `scripts/migrate_yaml_to_sqlite.py` with 17 tests
- **Zero data loss** - All fields preserved including bridge definitions, tags, reasons, and project context

### Performance
- **queryDecisions: 0.37s** (was 3.16s with YAML — **8.5x faster**)
- **getCalibration: 0.06s** (was 2.54s — **42x faster**)
- **getDecision: 5.8ms** (was 27ms — **4.7x faster**)
- **listDecisions: 6.7ms**, getStats: 8ms

### Enriched Search
- **Bridge in search results** - `DecisionSummary` now includes structure/function bridge definitions (~200 bytes each)
- **Enriched pre_action** - Relevant decisions include outcome, reasons, and lessons learned
- **Deliberation on-demand** - Full traces (2-5KB) only via `getDecision`, not in list results

### Dashboard Integration
- **Server-side filtering** - Dashboard wired to `listDecisions`/`getStats` APIs instead of client-side YAML scanning
- **Decision detail page** - Full text, recorded_by attribution, strength bars, graph neighbor links
- **Calibration service refactored** - Uses `DecisionStore.list()` instead of YAML file globbing

### Bug Fixes
- Fix `dict`-type `project` field handling in SQLite storage
- Fix `reindex_decisions()` to delegate to `reindex_decision()` for full metadata rebuild
- Fix deliberation tracking in `pre_action` for MCP visibility
- Fix `safe_auto_link()` in `pre_action` auto_record path

## v0.14.0 - Multi-Agent Isolation & Live Deliberation
*February 16, 2026*

Multi-agent deliberation isolation, live deliberation viewer dashboard, memory compaction, decision graph with auto-linking, and quality enforcement.

### Multi-Agent Deliberation Isolation
- **Composite tracker keys** - `agent:{id}:decision:{id}` scoping prevents thought cross-contamination when multiple agents share an MCP connection
- **`agent_id` on all MCP tools** - `pre_action`, `get_session_context`, `ready`, `record_thought`, `log_decision` all accept `agent_id` for attribution and isolation
- **`decision_id` scoping** - `record_thought` and `log_decision` accept `decision_id` to scope deliberation consumption to specific decisions
- **`cstp.debugTracker`** - Live inspection endpoint for in-memory deliberation state

### F049: Live Deliberation Viewer
- New `/deliberation` dashboard page with real-time tracker state
- Session cards organized by composite key with agent/decision badges
- HTMX auto-refresh (5s) with Alpine.js expand state preservation
- Color-coded by age (fresh/stale), type badges for input sources
- Composite key parsing links decision IDs to detail pages

### F041: Memory Compaction
- Semantic decay: full → summary → digest → wisdom compaction levels
- `cstp.getCompacted` and `cstp.getWisdom` endpoints
- Wisdom and compacted results integrated into `get_session_context`
- Automatic compaction on startup and on review

### F044: Agent Work Discovery
- `cstp.ready` endpoint surfaces prioritized cognitive actions
- Action types: overdue reviews, calibration drift, stale decisions
- Filter by priority, type, category

### F045: Decision Graph Storage Layer
- `cstp.linkDecisions` - typed edges (`relates_to`, `supersedes`, `depends_on`)
- `cstp.getGraph` - subgraph queries with depth and edge type filters
- `cstp.getNeighbors` - lightweight neighbor queries
- Auto-linking on `recordDecision` from related decisions
- JSONL persistence, NetworkX backend, thread-safe

### F048: Multi-Vector-DB Support
- `VectorStore` and `EmbeddingProvider` abstractions
- ChromaDB and MemoryStore backends
- Factory pattern with `VECTOR_BACKEND` env var

### Quality & Process
- **`low-quality-recording` guardrail upgraded to block** - Decisions missing tags, pattern, or reasons are now rejected
- **`log_decision` demoted to last resort** - `pre_action(auto_record: true)` is the primary recording path
- **14+ MCP tools** (3 PRIMARY: `pre_action`, `get_session_context`, `ready`)

### Documentation
- Updated all docs with correct MCP flow: `pre_action` → `record_thought` → `update_decision`
- Multi-agent isolation guide
- Agent system prompt templates updated
- All 33+ feature specs on website

### No Breaking Changes
All features are additive. `agent_id` defaults to `"mcp-client"` when not provided. Existing clients work unchanged.

---

## v0.11.0 - Pre-Action API, Dashboard & Website
*February 15, 2026*

A complete agent workflow in two calls: `pre_action` (query + guardrails + record in one shot) and `get_session_context` (full cognitive context for session start). Plus a production dashboard, pluggable vector storage, and a documentation website.

### Features
- **F046: Pre-Action Hook** - All-in-one `cstp.preAction` combines query, guardrails, calibration, pattern extraction, and optional recording into a single call
- **F047: Session Context** - `cstp.getSessionContext` delivers agent profile, relevant decisions, guardrails, calibration by category, and confirmed patterns in JSON or markdown
- **F048 P1: Pluggable Storage** - `VectorStore` and `EmbeddingProvider` abstractions extracted from hardcoded ChromaDB/Gemini; in-memory backend for testing
- **F027: Decision Quality** - Tags, patterns, quality scoring, smart bridge extractors for better retrieval
- **F028: Reasoning Capture** - `cstp.recordThought` for chain-of-thought steps, quality enforcement guardrail

### Dashboard
- Full web dashboard (Flask + HTMX + Alpine.js + Chart.js)
- Decision explorer with search, filters, and detail views
- Calibration charts, analytics overview, date filter presets
- Dark theme design system

### MCP
- **11 MCP tools** (up from 7) via Streamable HTTP at `/mcp`
- `pre_action` and `get_session_context` marked as PRIMARY entry points
- Claude Code / Claude Desktop integration via `npx mcp-remote@latest`
- Fixed `$ref`/`$defs` schema issues for LLM compatibility

### Website
- Documentation site at [cognition-engines.ai](https://cognition-engines.ai)
- VitePress with dark theme, local search, Mermaid diagram support
- Guide, Reference, and Feature Specs sections

### Specs Added
- F029-F032: Research-driven specs (task routing, circuit breakers, trust scoring, error tracking)
- F033-F034: Censor layer, decomposed confidence
- F035-F039: Multi-agent federation (state transfer, reasoning continuity, collective innovation, protocol stack)
- F040-F045: Beads-inspired specs (task graphs, memory compaction, dependencies, distributed merge, work discovery, graph storage)
- F048: Multi-vector-DB support

### No Breaking Changes
All features are additive. Existing JSON-RPC and MCP clients work unchanged.

---

## v0.10.0 - Decision Intelligence with Auto-Capture
*February 8, 2026*

Every decision now automatically captures its full cognitive context - deliberation traces, bridge-definitions, and related decision links - with zero client changes.

### Features
- **F022: MCP Server** - 7 native MCP tools at `/mcp`
- **F023: Deliberation Traces** - auto-capture query/check as structured inputs
- **F024: Bridge-Definitions** - structure/function dual descriptions with directional search
- **F025: Related Decisions** - auto-populated graph edges from query results
- `cstp.getDecision` - full decision details by ID
- `cstp.getReasonStats` - reason-type calibration analytics
- Agent Quick Start Guide for onboarding other agents

### No Breaking Changes
All features are additive and backward-compatible.

## v0.8.0 - Decision Intelligence Platform
*February 5, 2026*

- CSTP server with JSON-RPC 2.0 API
- Hybrid retrieval (BM25 + semantic)
- Drift alerts and confidence variance monitoring
- Docker deployment with dashboard
