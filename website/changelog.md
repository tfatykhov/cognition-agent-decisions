# Changelog

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
