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

**New in v0.7.0:** Cognition Engines now supports **CSTP (Cognition State Transfer Protocol)**, allowing remote agents to query your decision history via JSON-RPC.

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

**Method: `cstp.recordDecision`** *(New in v0.7.1)*
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

**Method: `cstp.attributeOutcomes`** *(New in v0.7.2)*
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

See [CSTP Design](docs/CSTP-v0.7.0-DESIGN.md) for full protocol details.

## MCP Server (F022)

Cognition Engines provides a native **Model Context Protocol (MCP)** server, allowing AI agents (Claude Desktop, OpenClaw, etc.) to use decision intelligence tools directly.

**Tools Provided:**
- `query_decisions`: Search past decisions to learn from history
- `check_action`: Validate actions against guardrails
- `log_decision`: Record a new decision
- `review_outcome`: Record the outcome of a past decision
- `get_stats`: Get calibration statistics (Brier score, etc.)
- `get_decision`: Retrieve full decision details
- `get_reason_stats`: Analyze reasoning patterns

**Connect via HTTP (SSE):**
The server exposes an MCP endpoint at `/mcp` (Server-Sent Events).
```bash
# Connect your agent to:
http://localhost:8000/mcp
```

**Connect via Stdio:**
```bash
python -m a2a.mcp_server
```

## Deliberation Traces (F023)

Decisions are more than just the final choice—they are the result of a thinking process. Deliberation Traces capture this process automatically.

**Auto-Capture:**
When an agent uses CSTP tools (`query_decisions`, `check_action`) before making a decision, the server automatically tracks these as "inputs" to the deliberation. When `log_decision` is called, these inputs are attached to the decision record.

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

| Version | Features | Status |
|---------|----------|--------|
| v0.5.0 | Semantic Decision Index | ✅ Shipped |
| v0.6.0 | Pattern Detection Engine | ✅ Shipped |
| v0.6.0 | Enhanced Guardrails + Audit Trail | ✅ Shipped |
| v0.7.0 | Cross-Agent Federation (CSTP) | ✅ Shipped |
| v0.7.2 | Project Context & Attribution | ✅ Shipped |
| v0.9.0 | Hybrid Retrieval + Drift Alerts | ✅ Shipped |
| v0.9.1 | F022 MCP Server | ✅ Shipped |
| v0.9.2 | F023 Deliberation Traces | ✅ Shipped |
| v0.9.3 | F024 Bridge-Definitions | ✅ Shipped |
| v0.9.4 | F025 Related Decisions | ✅ Shipped |
| v1.0.0 | Multi-Agent Cognition Network | Planned |

### v0.7.0 — Cross-Agent Federation
- **Cross-agent query**: `query.py --scope=org` — search all agents' decisions
- **Federated ChromaDB**: Shared collection or cross-instance queries
- **Guardrail inheritance**: Org-level GATs that all agents inherit
- **Agent-specific overrides**: Local rules with audit trail

### v0.9.0 — Hybrid Retrieval & Stability
- **Hybrid Search**: Semantic + keyword matching (BM25) for precision
- **Drift Alerts**: Detect when decision patterns change over time
- **Confidence Variance**: Track uncertainty across agent decisions

### v0.9.1+ — Decision Intelligence Features
- **F022 MCP Server**: Native integration for Claude Desktop and OpenClaw
- **F023 Deliberation Traces**: Capture the *process* of thinking, not just the result
- **F024 Bridge-Definitions**: Dual-indexing for structure (form) and function (purpose)
- **F025 Related Decisions**: Auto-linked predecessors from pre-decision queries

### v1.0.0 — Multi-Agent Cognition Network
- **Semantic State Transfer**: Export decision context in portable format
- **Reasoning continuity**: Another agent can "resume" a decision thread
- **Collective innovation**: Agents reason together on novel problems
- **COGs + GATs**: Full cognitive amplifiers and guardrail technologies
- **Full protocol stack**: LSTP/CSTP/SSTP support based on use case

### Cognition State Protocols (Future)

Based on [Cisco Outshift's Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence):

| Protocol | Layer | Use Case |
|----------|-------|----------|
| **SSTP** | Semantic | Human-auditable, policy-governed decisions. Cross-vendor strategic coordination. |
| **CSTP** | Compressed | Low-bandwidth environments (Edge, WAN). Abstracted feature representations. |
| **LSTP** | Latent | High-fidelity inference continuity. Local clusters with unified execution. |

**Our focus:** SSTP first — it's the decision-making layer. CSTP/LSTP for future performance optimization.

## Project Structure

```
cognition-agent-decisions/
├── src/
│   └── cognition_engines/
│       ├── accelerators/     # Query, patterns, learning
│       └── guardrails/       # Definitions, enforcement
├── a2a/                      # CSTP Protocol (Server/Client)
│   ├── cstp/
│   │   ├── bridge_extractor.py    # F024 Auto-extraction
│   │   ├── bridge_hook.py         # F024 Bridge logic
│   │   ├── deliberation_tracker.py # F023 Auto-capture
│   │   └── ...
│   ├── mcp_server.py         # F022 MCP Server
│   ├── mcp_schemas.py        # F022 MCP Pydantic models
│   └── server.py             # FastAPI / JSON-RPC server
├── guardrails/               # YAML guardrail definitions
├── tests/                    # Test suite
├── docs/                     # Documentation
└── examples/                 # Usage examples
```

## Related Projects

- [agent-decisions](https://github.com/tfatykhov/agent-decisions) — Core decision journal
- [Membrain](https://github.com/tfatykhov/membrain) — Neuromorphic memory (future integration)

## License

Creative Commons — See [LICENSE](LICENSE)
