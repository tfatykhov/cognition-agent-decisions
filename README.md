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

### ChromaDB (Vector Database)

Cognition Engines uses ChromaDB for semantic similarity search. You have two options:

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

| Version | Features | Status |
|---------|----------|--------|
| v0.5.0 | Semantic Decision Index | ✅ Shipped |
| v0.6.0 | Pattern Detection Engine | ✅ Shipped |
| v0.6.0 | Enhanced Guardrails + Audit Trail | ✅ Shipped |
| v0.7.0 | Cross-Agent Federation | 🔜 Next |
| v0.8.0 | Outcome-Based Learning | Planned |
| v1.0.0 | Multi-Agent Cognition Network | Planned |

## Project Structure

```
cognition-agent-decisions/
├── src/
│   └── cognition_engines/
│       ├── accelerators/     # Query, patterns, learning
│       └── guardrails/       # Definitions, enforcement
├── guardrails/               # YAML guardrail definitions
├── tests/                    # Test suite
├── docs/                     # Documentation
└── examples/                 # Usage examples
```

## Related Projects

- [agent-decisions](https://github.com/tfatykhov/agent-decisions) — Core decision journal
- [Membrain](https://github.com/tfatykhov/membrain) — Neuromorphic memory (future integration)

## License

Apache 2.0 — See [LICENSE](LICENSE)
