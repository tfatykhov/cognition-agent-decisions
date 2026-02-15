# Cognition Engines

**Decision Intelligence for AI Agents**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/docs-cognition--engines.ai-6366f1)](https://cognition-engines.ai)

Cognition Engines gives AI agents a memory of their decisions — what they decided, why, and whether it worked. Agents query past decisions before acting, guardrails prevent known mistakes, and calibration tracking reveals whether the agent is actually getting better over time.

## Key Capabilities

- **Decision Memory**: Semantic search over past decisions with hybrid retrieval (vector + BM25)
- **Guardrails**: Policy enforcement that blocks unsafe actions before they happen
- **Calibration**: Brier scoring tracks whether confidence predictions match actual outcomes
- **Deliberation Traces**: Auto-captures the reasoning chain (queries, guardrail checks) leading to each decision
- **Bridge Search**: Query by structure ("what does it look like?") or function ("what problem does it solve?")
- **MCP + JSON-RPC**: Framework-agnostic — works with Claude Code, Claude Desktop, OpenClaw, LangChain, or raw curl
- **Pluggable Storage**: VectorStore abstraction supports ChromaDB (default), with Weaviate, pgvector, Qdrant planned

## Quick Start

### Docker (Recommended)

```bash
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cd cognition-agent-decisions

cp .env.example .env
# Edit .env: set GEMINI_API_KEY and CSTP_AUTH_TOKENS

docker-compose up -d
curl http://localhost:8100/health
```

### Connect Claude Code

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "decisions": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "http://YOUR_HOST:8100/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer YOUR_CSTP_TOKEN"
      ]
    }
  }
}
```

On Windows, prefix with `"command": "cmd", "args": ["/c", "npx", ...]`.

### Connect Claude Desktop

Same config in `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows).

## How It Works

```
Session start    → get_session_context  (load cognitive context)
       ↓
Decision point   → pre_action           (query + guardrails + record)
       ↓
During work      → record_thought       (capture reasoning)
       ↓
After work       → update_decision      (finalize decision text)
       ↓
Later            → review_outcome       (log success/failure)
```

### Primary MCP Tools

| Tool | Purpose |
|------|---------|
| `pre_action` **(PRIMARY)** | All-in-one: queries similar decisions, evaluates guardrails, fetches calibration, extracts patterns, optionally records. One call replaces 3. |
| `get_session_context` **(PRIMARY)** | Full cognitive context at session start: agent profile, relevant decisions, guardrails, calibration by category, ready queue, confirmed patterns. JSON or markdown output. |
| `ready` **(PRIMARY)** | Prioritized cognitive maintenance queue: overdue reviews, calibration drift, stale decisions. Filter by priority, type, category. |

### Granular MCP Tools

| Tool | Purpose |
|------|---------|
| `query_decisions` | Semantic/hybrid search over past decisions |
| `check_action` | Standalone guardrail validation |
| `log_decision` | Record a decision with confidence, reasons, tags, pattern |
| `review_outcome` | Record success/failure for calibration |
| `get_stats` | Calibration statistics (Brier score, accuracy, drift) |
| `get_decision` | Full decision details by ID |
| `get_reason_stats` | Which reasoning types predict success |
| `update_decision` | Update decision text/context after work |
| `record_thought` | Capture reasoning steps during work |

### Graph Tools

| Tool | Purpose |
|------|---------|
| `link_decisions` | Create typed edges between decisions (`relates_to`, `supersedes`, `depends_on`) |
| `get_graph` | Query subgraph around a decision with configurable depth and edge type filters |

## JSON-RPC API

All tools are also available via JSON-RPC 2.0 at `POST /cstp`:

```bash
curl -X POST http://localhost:8100/cstp \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "cstp.preAction",
    "params": {
      "action": {
        "description": "Refactor auth to use JWT",
        "category": "architecture",
        "stakes": "high",
        "confidence": 0.85
      },
      "tags": ["auth", "refactor"],
      "pattern": "Stateless auth scales better than session-based"
    },
    "id": 1
  }'
```

**Available methods:** `cstp.queryDecisions`, `cstp.checkGuardrails`, `cstp.recordDecision`, `cstp.reviewDecision`, `cstp.getCalibration`, `cstp.getDecision`, `cstp.getReasonStats`, `cstp.updateDecision`, `cstp.recordThought`, `cstp.preAction`, `cstp.getSessionContext`, `cstp.ready`, `cstp.linkDecisions`, `cstp.getGraph`, `cstp.checkDrift`, `cstp.reindex`, `cstp.listGuardrails`, `cstp.attributeOutcomes`

## Architecture

![Cognition Engines Architecture](docs/architecture.png)

### Pluggable Storage (F048)

Vector storage and embeddings are abstracted behind `VectorStore` and `EmbeddingProvider` interfaces:

```bash
# Default: ChromaDB + Gemini
VECTOR_BACKEND=chromadb
EMBEDDING_PROVIDER=gemini

# Testing: in-memory (no external services)
VECTOR_BACKEND=memory

# Coming soon: Weaviate, pgvector, Qdrant, OpenAI, Ollama
```

## Core Concepts

### Deliberation Traces (F023)

When an agent calls `query_decisions` or `check_action` before recording a decision, the server auto-captures these as deliberation inputs. The full reasoning chain is attached to the decision record — zero client changes needed.

### Bridge Definitions (F024)

Based on Minsky's *Society of Mind*. Decisions are indexed by both **structure** (what it looks like) and **function** (what it does). Use `bridgeSide` to search by intent or form:

```json
{"method": "cstp.queryDecisions", "params": {"query": "rate limiting", "bridgeSide": "function"}}
```

### Decision Quality (F027)

Decisions are scored for retrieval quality based on completeness of tags, patterns, context, and bridge definitions. The `pattern` field captures the abstract lesson — making decisions findable by purpose, not just keywords.

### Guardrails

```yaml
# guardrails/cornerstone.yaml
id: no-high-stakes-low-confidence
description: High-stakes decisions require minimum confidence
condition:
  stakes: high
  confidence: "< 0.5"
action: block
message: "High-stakes decisions require ≥50% confidence"
```

## Roadmap

See [docs/features/INDEX.md](docs/features/INDEX.md) for the complete feature catalog and [TODO.md](TODO.md) for prioritized work items.

| Version | Features | Status |
|---------|----------|--------|
| v0.8.0 | Core CSTP Server, Docker, Dashboard (F001-F011) | ✅ Shipped |
| v0.9.0 | Hybrid Retrieval, Drift Alerts, Calibration (F014-F017) | ✅ Shipped |
| v0.10.0 | MCP Server, Deliberation Traces, Bridge Definitions, Quality (F019-F028) | ✅ Shipped |
| v0.11.0 | Pre-Action Hook, Session Context, Dashboard, Website, Pluggable Storage (F027-F028, F046-F048) | ✅ Shipped |
| v0.12.0 | Agent Work Discovery, Graph Storage, Pluggable Storage (F044, F045, F048) | ✅ Shipped |
| v0.13.0 | Memory Compaction, Circuit Breakers (F041, F030) | 🚧 In Progress |

### Upcoming

| Priority | Features |
|----------|----------|
| **P0** | F044 Agent Work Discovery (`cstp.ready`) |
| **P1** | F041 Memory Compaction, F045 Graph Storage, F030 Circuit Breakers, Weaviate/pgvector backends |
| **P2** | F034 Decomposed Confidence, F040 Task-Decision Graph, F033 Censor Layer |
| **P3** | F035-F039 Multi-Agent Federation, F043 Distributed Merge |

### Research Foundations

- [Cisco Outshift — Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence) (SSTP/CSTP/LSTP protocol layers)
- Minsky — *Society of Mind* (bridge definitions, censor layer, decomposed confidence)
- [Beads](https://github.com/steveyegge/beads) (task graphs, memory compaction, work discovery)
- Context Graphs, MemoBrain, Graph-Constrained Reasoning (ICML 2025)

## Project Structure

```
cognition-agent-decisions/
├── a2a/cstp/                  # CSTP services
│   ├── dispatcher.py          # JSON-RPC routing (15 methods)
│   ├── query_service.py       # Hybrid retrieval
│   ├── decision_service.py    # Record, update, retrieve
│   ├── calibration_service.py # Brier scoring, rolling windows
│   ├── guardrails_service.py  # Policy evaluation
│   ├── preaction_service.py   # F046 Pre-action hook
│   ├── session_context_service.py # F047 Session context
│   ├── deliberation_tracker.py # F023 Auto-capture
│   ├── vectordb/              # F048 Pluggable vector storage
│   │   ├── chromadb.py        # ChromaDB backend
│   │   └── memory.py          # In-memory backend (testing)
│   └── embeddings/            # F048 Pluggable embeddings
│       └── gemini.py          # Gemini backend
├── a2a/mcp_server.py          # MCP Server (11 tools)
├── a2a/server.py              # FastAPI server
├── dashboard/                 # Web dashboard (Flask)
├── docs/features/             # Feature specs (F001-F048)
├── guardrails/                # YAML guardrail definitions
├── tests/                     # Test suite
├── website/                   # VitePress docs (cognition-engines.ai)
├── CLAUDE.md                  # Claude Code project context
└── TODO.md                    # Prioritized roadmap
```

## Documentation

- **Website**: [cognition-engines.ai](https://cognition-engines.ai)
- **API Reference**: [cognition-engines.ai/reference/api](https://cognition-engines.ai/reference/api)
- **MCP Quick Start**: [cognition-engines.ai/reference/mcp-quickstart](https://cognition-engines.ai/reference/mcp-quickstart)
- **Feature Specs**: [docs/features/INDEX.md](docs/features/INDEX.md)

## License

Apache 2.0 — See [LICENSE](LICENSE)
