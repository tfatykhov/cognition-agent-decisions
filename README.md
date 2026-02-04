# Cognition Engines for agent-decisions

**Accelerators & Guardrails for Multi-Agent Decision Intelligence**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

This project extends [agent-decisions](https://github.com/tfatykhov/agent-decisions) with **Cognition Engines** — the intelligence layer that enables:

- **Accelerators**: Cross-agent learning through semantic decision querying and pattern detection
- **Guardrails**: Policy enforcement that prevents violations before they occur

Based on Cisco Outshift's [Internet of Cognition](https://outshift.cisco.com/blog/from-connection-to-cognition-scaling-superintelligence) architecture.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Cognition Engines                      │
├────────────────────────┬────────────────────────────────┤
│      Accelerators      │          Guardrails            │
│  ┌──────────────────┐  │  ┌──────────────────────────┐  │
│  │ Semantic Index   │  │  │ Guardrail Definitions    │  │
│  │ Pattern Detection│  │  │ Enforcement Hooks        │  │
│  │ Cross-Agent Query│  │  │ Violation Handling       │  │
│  └──────────────────┘  │  └──────────────────────────┘  │
├────────────────────────┴────────────────────────────────┤
│                    Decision Store                        │
│              (ChromaDB + YAML files)                     │
└─────────────────────────────────────────────────────────┘
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

| Version | Features |
|---------|----------|
| v0.5.0 | Semantic Decision Index |
| v0.6.0 | Pattern Detection Engine |
| v0.7.0 | Guardrail Definition Language |
| v0.8.0 | Enforcement Hooks |
| v1.0.0 | Multi-Agent Federation |

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
