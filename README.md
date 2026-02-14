# Cognition Engines for agent-decisions

**Accelerators & Guardrails for Multi-Agent Decision Intelligence**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

This project extends [agent-decisions](https://github.com/tfatykhov/agent-decisions) with **Cognition Engines** — the intelligence layer that enables:

- **Accelerators**: Cross-agent learning through semantic decision querying and pattern detection
- **Guardrails**: Policy enforcement that prevents violations before they occur

Based on Cisco Outshift's [Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence) architecture.

## Architecture

![Cognition Engines Architecture](docs/images/architecture.png)

**Components:**
- **Top:** AI Agents (humans + bots) connect to the Cognition Engines brain
- **Left (Accelerators):** Semantic Index, Pattern Detection, Cross-Agent Query
- **Right (Guardrails):** Policy Validation, Enforcement Hooks, Violation Alerts
- **Bottom:** Decision Store (ChromaDB + YAML files)

## Prerequisites

### Required
- **Python 3.10+**
- **ChromaDB** — Vector database for semantic search
- **Gemini API key** — For embeddings (free tier available)

### Recommended
- **[agent-decisions](https://github.com/tfatykhov/agent-decisions)** — Decision journal with Brier scoring

Cognition Engines works best with agent-decisions for:
- Consistent YAML schema for decisions
- Confidence calibration tracking (Brier scores)
- Multi-reason support with strength scoring
- K-line context bundles

**Without agent-decisions:** Cognition Engines can work with any YAML decision files that have these fields:
```yaml
title: "Decision title"
category: architecture | process | integration | tooling | security
confidence: 0.85  # 0.0-1.0
date: "2026-02-04T03:45:00Z"
context: "What you're deciding"
```

### ChromaDB (Vector Database)

**Option 1: Docker (Recommended)**
```bash
docker run -d \
  --name chromadb \
  -p 8000:8000 \
  -v chromadb_data:/chroma/chroma \
  chromadb/chroma:latest
```

**Option 2: Local Python**
```bash
pip install chromadb
# Runs embedded (no separate server needed)
```

### Embeddings Provider

You need an embeddings API. Supported providers:

| Provider | Model | Dimensions | Setup |
|----------|-------|------------|-------|
| **Gemini** (default) | text-embedding-004 | 768 | `export GEMINI_API_KEY=your_key` |
| OpenAI | text-embedding-3-small | 1536 | `export OPENAI_API_KEY=your_key` |
| Local | sentence-transformers | varies | `pip install sentence-transformers` |

**Get a Gemini API key:** https://aistudio.google.com/apikey (free tier available)

### Environment Variables

```bash
# Required
export GEMINI_API_KEY="your_gemini_api_key"

# Optional (if using Docker ChromaDB)
export CHROMA_HOST="localhost"
export CHROMA_PORT="8000"
```

Or create a `.env` file:
```
GEMINI_API_KEY=your_gemini_api_key
CHROMA_HOST=localhost
CHROMA_PORT=8000
```

## Quick Start

### Option 1: Docker (Recommended)

```bash
# Clone the repo
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cd cognition-agent-decisions

# Configure
cp .env.example .env
# Edit .env with your GEMINI_API_KEY and CSTP_AUTH_TOKENS

# Start (includes ChromaDB)
docker-compose up -d

# Verify
curl http://localhost:8100/health
# {"status":"healthy"}
```

See [docs/DOCKER.md](docs/DOCKER.md) for full deployment guide.

### Option 2: Local Installation

```bash
# Install dependencies
pip install -e .

# Index existing decisions
cognition index /path/to/decisions/

# Query similar decisions
cognition query "choosing database for agent memory"

# Check guardrails before a decision
cognition check --category architecture --stakes high --confidence 0.7

# Detect patterns
cognition patterns --min-decisions 10
```

## OpenClaw Skill Installation

If you're using OpenClaw, install as a skill:

```bash
# Copy to skills directory
cp -r skills/cognition-engines ~/.openclaw/workspace/skills/

# Or clone directly
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cp -r cognition-agent-decisions/skills/cognition-engines ~/.openclaw/workspace/skills/
```

Then use via uv:
```bash
uv run ~/.openclaw/workspace/skills/cognition-engines/scripts/query.py "your query"
uv run ~/.openclaw/workspace/skills/cognition-engines/scripts/check.py --stakes high
```

## Framework Compatibility

Cognition Engines is **agent-framework agnostic**. It's Python + ChromaDB — works anywhere.

### LangChain / LangGraph

```python
from cognition_engines.accelerators import SemanticIndex
from cognition_engines.guardrails import GuardrailEngine

# Add to your agent's decision step
def make_decision(context: str, confidence: float):
    # Query similar past decisions
    index = SemanticIndex()
    similar = index.query(context, top_k=5)
    
    # Check guardrails
    engine = GuardrailEngine()
    result = engine.check({"stakes": "high", "confidence": confidence})
    
    if not result.allowed:
        raise ValueError(f"Blocked: {result.violations}")
    
    return proceed_with_decision()
```

### AutoGen

```python
# In your AutoGen agent config
from cognition_engines.accelerators import SemanticIndex

class DecisionAgent(AssistantAgent):
    def __init__(self):
        self.decision_index = SemanticIndex()
    
    def before_decide(self, context):
        similar = self.decision_index.query(context)
        return f"Similar past decisions: {similar}"
```

### CrewAI

```python
from crewai import Agent, Task
from cognition_engines.guardrails import GuardrailEngine

# Create a guardrail-aware agent
guardrails = GuardrailEngine()

@tool
def check_decision(stakes: str, confidence: float) -> str:
    result = guardrails.check({"stakes": stakes, "confidence": confidence})
    return "Allowed" if result.allowed else f"Blocked: {result.message}"
```

### Any Python Agent

```python
# Direct script usage
import subprocess

# Query similar decisions
result = subprocess.run(
    ["python", "scripts/query.py", "your context"],
    capture_output=True, text=True
)
similar_decisions = result.stdout

# Check guardrails
result = subprocess.run(
    ["python", "scripts/check.py", "--stakes", "high", "--confidence", "0.8"],
    capture_output=True, text=True
)
```

## Multi-Agent Shared Memory

When using an **external vector database**, multiple agents can share the same decision memory and guardrails:

![Multi-Agent Shared Memory Architecture](docs/images/multi-agent-architecture.png)

**Benefits:**
- 🔍 **Cross-agent queries** — "Has anyone in my team seen this before?"
- 🛡️ **Shared guardrails** — Org-level policies all agents inherit
- 📊 **Collective learning** — One agent's lessons benefit all
- 🔄 **Consistent decisions** — Same context → same guardrail checks

**Setup:**
```bash
# Point all agents to the same vector database
export CHROMA_HOST="your-shared-db.example.com"
export CHROMA_PORT="8000"
```

## Remote Access (CSTP)

Cognition Engines supports **CSTP (Cognition State Transfer Protocol)**, exposing decision intelligence via JSON-RPC 2.0.

**Endpoint:** `POST /cstp`

**Method: `cstp.queryDecisions`**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.queryDecisions",
  "params": {
    "query": "database migration",
    "bridgeSide": "function",
    "filters": { 
      "category": "architecture", 
      "minConfidence": 0.8,
      "project": "owner/repo"
    }
  },
  "id": 1
}
```

**Method: `cstp.checkGuardrails`**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.checkGuardrails",
  "params": {
    "action": {
      "description": "Deploy to production",
      "category": "process",
      "stakes": "high",
      "confidence": 0.85,
      "context": {
        "affectsProduction": true,
        "codeReviewCompleted": true
      }
    }
  },
  "id": 2
}
```

**Method: `cstp.recordDecision`**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.recordDecision",
  "params": {
    "decision": "Use PostgreSQL for agent memory storage",
    "confidence": 0.85,
    "category": "architecture",
    "stakes": "high",
    "context": "Choosing database for long-term storage",
    "project": "owner/repo",
    "feature": "memory-persistence",
    "pr": 42,
    "reasons": [
      {"type": "analysis", "text": "ACID compliance needed", "strength": 0.9}
    ],
    "tags": ["database", "infrastructure"],
    "pattern": "Choose proven technology for critical data paths",
    "reviewIn": "30d"
  },
  "id": 3
}
```

Response:
```json
{
  "result": {
    "success": true,
    "id": "abc12345",
    "path": "decisions/2026/02/2026-02-05-decision-abc12345.yaml",
    "indexed": true,
    "deliberation_auto": true,
    "deliberation_inputs_count": 2,
    "quality_score": 0.85,
    "bridge_auto": true,
    "timestamp": "2026-02-05T00:48:00Z"
  }
}
```

**Method: `cstp.getDecision`**
Retrieve full decision details by ID.
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.getDecision",
  "params": { "id": "abc12345" },
  "id": 4
}
```

**Method: `cstp.getReasonStats`**
Analyze which reason types correlate with success.
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.getReasonStats",
  "params": { "minReviewed": 5 },
  "id": 5
}
```

**Method: `cstp.attributeOutcomes`**
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.attributeOutcomes",
  "params": {
    "project": "owner/repo",
    "stabilityDays": 14
  },
  "id": 6
}
```

**Method: `cstp.recordThought`** *(New in v0.10.0)*

Capture reasoning during work. Links to a decision for full deliberation trace.
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.recordThought",
  "params": {
    "text": "Exploring option A - direct YAML update seems simpler but less scalable",
    "decision_id": "abc12345"
  },
  "id": 7
}
```

**Method: `cstp.updateDecision`** *(New in v0.10.0)*

Update a decision after work is complete (record-at-start workflow).
```json
{
  "jsonrpc": "2.0",
  "method": "cstp.updateDecision",
  "params": {
    "id": "abc12345",
    "updates": {
      "decision": "Used PostgreSQL with connection pooling",
      "context": "Final outcome: deployed with PgBouncer, 3ms p99 latency"
    }
  },
  "id": 8
}
```

See [docs/features/](docs/features/) for full feature specifications.

## MCP Server (F022)

Cognition Engines provides a native **Model Context Protocol (MCP)** server, allowing AI agents (Claude Desktop, OpenClaw, etc.) to use decision intelligence tools directly.

**Tools Provided (9):**
- `query_decisions`: Search past decisions with hybrid retrieval (semantic + BM25)
- `check_action`: Validate actions against guardrails
- `log_decision`: Record a new decision with tags, patterns, and quality scoring
- `review_outcome`: Record the outcome of a past decision
- `get_stats`: Get calibration statistics (Brier score, rolling windows, drift)
- `get_decision`: Retrieve full decision details with deliberation trace
- `get_reason_stats`: Analyze which reasoning types predict success
- `update_decision`: Update a decision after work completes
- `record_thought`: Capture reasoning during work

**Connect via Streamable HTTP:**
```bash
# MCP endpoint (handles POST for tools and GET for events):
http://localhost:8000/mcp
```

**Connect via Stdio:**
```bash
python -m a2a.mcp_server
```

## Deliberation Traces (F023) & Reasoning Capture (F028)

Decisions are more than just the final choice - they are the result of a thinking process. Deliberation Traces capture this process automatically.

**Auto-Capture:**
When an agent uses CSTP tools (`query_decisions`, `check_action`) before making a decision, the server automatically tracks these as "inputs" to the deliberation. When `log_decision` is called, these inputs are attached to the decision record.

**Explicit Thoughts:**
Use `cstp.recordThought` to capture reasoning during work:
```json
{"method": "cstp.recordThought", "params": {"text": "Option B is better - avoids Docker filesystem access", "decision_id": "abc123"}}
```

- **Zero client changes**: The server tracks inputs by `agent_id` or MCP session.
- **Provenance**: See exactly which past decisions or guardrails influenced the choice.
- **Traceability**: Response includes `deliberation_auto: true` and input count.

```yaml
deliberation:
  inputs:
    - id: "q-a1b2c3d4"
      type: "query"
      text: "Queried 'database choice': 5 results (hybrid)"
    - id: "g-e5f6g7h8"
      type: "guardrail"
      text: "Checked 'deploy to prod': Allowed"
  steps: ...
```

## Bridge-Definitions (F024)

Based on Minsky's *Society of Mind* (Ch 12), Bridge-Definitions separate a decision into:
- **Structure**: What it looks like (patterns, code shapes, tools)
- **Function**: What it does (purpose, problem solved)

**Directional Search:**
Use the `bridgeSide` parameter in `queryDecisions` to search specifically by intent or form:
- `--bridge-side function`: "I have this problem, what solves it?"
- `--bridge-side structure`: "I see this pattern, what is it for?"

**Auto-Extraction:**
If you don't provide explicit bridge definitions, the system auto-extracts them from your decision context (`bridge_auto: true`).

**Optional Operators:**
- **Tolerance**: Features that don't matter (e.g., "log level")
- **Enforcement**: Features that MUST be present
- **Prevention**: Features that MUST NOT be present

## Related Decisions (F025)

Every decision automatically links to the decisions found during pre-decision queries. This creates lightweight graph edges without a graph database.

```yaml
related_to:
  - id: abc12345
    summary: "Used PostgreSQL for agent memory"
    distance: 0.234
  - id: def45678
    summary: "Adopted retry pattern for API calls"
    distance: 0.312
```

- **Auto-populated**: Extracted from query results in the deliberation trace
- **Zero config**: Works with existing query/check/record workflow
- **Deduplication**: Keeps the closest distance when same decision appears across multiple queries

## Decision Quality (F027)

Decisions are scored for retrieval quality based on tags, patterns, and bridge definitions:

- **Tags**: Reusable keywords for filtering (`--tag infrastructure --tag timeout`)
- **Patterns**: Abstract lessons ("Override system defaults when they don't match actual workload")
- **Quality Score**: 0.0-1.0 based on completeness of tags, patterns, context, and bridge definitions
- **Smart Bridge Extractors**: Auto-generate structure/function descriptions from decision text

**Two-level thinking:** Every decision should capture both the operational level (what you did) and the conceptual level (what pattern it represents). The `pattern` field makes decisions findable by purpose, not just keywords.

## Guardrail Example

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

*Inspired by Cisco Outshift's [Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence) architecture.*

![Roadmap Architecture](docs/images/roadmap-architecture.png)

See [docs/features/INDEX.md](docs/features/INDEX.md) for the complete feature index.

### Shipped

| Version | Features | Status |
|---------|----------|--------|
| v0.5.0 | Semantic Decision Index | ✅ Shipped |
| v0.6.0 | Pattern Detection + Enhanced Guardrails | ✅ Shipped |
| v0.7.0 | Cross-Agent Federation (CSTP) | ✅ Shipped |
| v0.7.2 | Project Context & Attribution | ✅ Shipped |
| v0.8.0 | CSTP Server, Docker, Web Dashboard (F001-F011) | ✅ Shipped |
| v0.9.0 | Hybrid Retrieval, Drift Alerts, Confidence Variance (F014-F017) | ✅ Shipped |
| v0.10.0 | MCP Server, Deliberation Traces, Bridge-Definitions, Decision Quality (F019-F028) | ✅ Shipped |

### v0.10.0 — Decision Intelligence with Auto-Capture (Current)
- **F019 List Guardrails**: Discover active guardrail rules
- **F022 MCP Server**: 9 native MCP tools at `/mcp` (Streamable HTTP)
- **F023 Deliberation Traces**: Auto-capture query/check as structured inputs
- **F024 Bridge-Definitions**: Dual-indexing for structure (form) and function (purpose)
- **F025 Related Decisions**: Auto-linked predecessors from pre-decision queries
- **F027 Decision Quality**: Tags, patterns, quality scores, smart bridge extractors
- **F028 Reasoning Capture**: `recordThought` for inline reasoning capture

### Next: Research-Driven Features
Based on MIT/Google scaling research and ai16z autonomous agent patterns:

| Feature | Description |
|---------|-------------|
| F020 Structured Reasoning Traces | Step-by-step reasoning chain capture |
| F029 Task Router | Classify tasks by decomposability, recommend agent architecture |
| F030 Circuit Breaker Guardrails | Stateful closed/open/half-open guardrails that trip on failure patterns |
| F031 Source Trust Scoring | Track information source reliability, weight query results |
| F032 Error Amplification Tracking | Causal chains across multi-agent decisions |
| F033 Censor Layer | Proactive failure pattern warnings (Minsky Ch 27) |
| F034 Decomposed Confidence | Per-reason confidence weights (Minsky Ch 28) |

### v1.0.0 — Multi-Agent Cognition Network

| Feature | Description |
|---------|-------------|
| F035 Semantic State Transfer | Export decision context in portable bundles |
| F036 Reasoning Continuity | Another agent can resume a decision thread |
| F037 Collective Innovation | Multi-agent structured deliberation protocol |
| F038 Cross-Agent Federation | Multi-instance CSTP with trust levels and discovery |
| F039 Protocol Stack | Three-layer SSTP/CSTP/LSTP support |

### Cognition State Protocols (F039)

Based on [Cisco Outshift's Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence):

| Protocol | Layer | Use Case |
|----------|-------|----------|
| **SSTP** | Semantic | Human-auditable, policy-governed decisions. Cross-vendor strategic coordination. |
| **CSTP** | Compressed | Low-bandwidth environments (Edge, WAN). Abstracted feature representations. |
| **LSTP** | Latent | High-fidelity inference continuity. Local clusters with unified execution. |

**Our focus:** SSTP first - it's the decision-making layer. CSTP/LSTP for future performance optimization.

## Project Structure

```
cognition-agent-decisions/
├── src/
│   └── cognition_engines/
│       ├── accelerators/          # Query, patterns, learning
│       └── guardrails/            # Definitions, enforcement
├── a2a/                           # CSTP Protocol (Server/Client)
│   ├── cstp/
│   │   ├── dispatcher.py          # JSON-RPC method routing (10 methods)
│   │   ├── query_service.py       # Hybrid retrieval (semantic + BM25)
│   │   ├── decision_service.py    # Record, update, retrieve decisions
│   │   ├── calibration_service.py # Brier scoring, rolling windows
│   │   ├── guardrails_service.py  # Policy evaluation
│   │   ├── deliberation_tracker.py # F023 Auto-capture
│   │   ├── bridge_extractor.py    # F024 Auto-extraction
│   │   ├── drift_service.py       # F015 Calibration drift
│   │   ├── attribution_service.py # F010 Outcome attribution
│   │   └── reason_stats_service.py # Reason-type analytics
│   ├── mcp_server.py              # F022 MCP Server (9 tools)
│   ├── mcp_schemas.py             # F022 MCP Pydantic models
│   └── server.py                  # FastAPI / JSON-RPC server
├── dashboard/                     # Web dashboard (Flask)
│   ├── app.py                     # Decision list, detail, review, calibration
│   ├── cstp_client.py             # HTTP client for CSTP server
│   └── templates/                 # Jinja2 templates
├── guardrails/                    # YAML guardrail definitions
├── tests/                         # Test suite
├── docs/
│   └── features/                  # All feature specs (F001-F039)
└── skills/
    └── cognition-engines/         # OpenClaw skill
```

## Related Projects

- [agent-decisions](https://github.com/tfatykhov/agent-decisions) — Core decision journal
- [Membrain](https://github.com/tfatykhov/membrain) — Neuromorphic memory (future integration)

## License

Apache 2.0 — See [LICENSE](LICENSE)
