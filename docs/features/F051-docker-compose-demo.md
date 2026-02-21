# F051: Docker-Compose Full Stack Demo

**Status:** Proposed
**Priority:** P1
**Category:** Adoption
**Related:** F049 (Dashboard), F050 (SQLite Storage)

## Problem

Onboarding requires reading docs, configuring env vars, setting up ChromaDB, understanding the MCP protocol, and building your own agent integration. This creates a high barrier to evaluation. Most potential users will never get past "how do I even try this?"

Competing frameworks (e.g., AgentOps, Helicone) ship one-command demos. We don't.

## Solution

A single `docker compose up` that launches the entire Cognition Engines stack with a pre-built sample agent that generates realistic decision-making activity, pre-loaded demo data, and the dashboard - all visible in under 60 seconds.

### What Ships

```
demo/
  docker-compose.yml      # Orchestrates all services
  demo-agent/
    Dockerfile
    agent.py              # Sample agent that makes decisions
    scenarios/            # Pre-built decision scenarios
  seed-data/
    decisions.db          # Pre-loaded SQLite with ~50 demo decisions
    graph_edges.jsonl     # Pre-loaded graph relationships
  README.md               # 3-step quickstart
```

### Architecture

```
docker compose up
  │
  ├── cstp-server (port 8100)
  │     CSTP MCP server + SQLite storage
  │     Pre-loaded with seed data
  │
  ├── dashboard (port 8080)
  │     Flask dashboard, connected to cstp-server
  │     Shows calibration curves, deliberation viewer
  │
  ├── chromadb (port 8000)
  │     Vector store for semantic search
  │     Auto-indexed from seed data on startup
  │
  └── demo-agent (runs once, then loops)
        Python agent that:
        - Makes decisions using pre_action → record_thought → update
        - Demonstrates guardrail checks (some blocked)
        - Reviews past decisions with outcomes
        - Generates calibration data over time
```

### Demo Agent Scenarios

The demo agent cycles through realistic scenarios:

1. **Architecture Decision** - "Should we use Redis or Memcached for caching?" Queries similar decisions, checks guardrails, records with reasons, reviews outcome.
2. **Guardrail Block** - Attempts a high-stakes/low-confidence decision. Gets blocked. Demonstrates safety.
3. **Decision Update Flow** - Records a plan, captures reasoning thoughts, updates with actual outcome.
4. **Calibration Review** - Reviews 5 past decisions with outcomes, then checks calibration stats.
5. **Graph Linking** - Creates related decisions and shows auto-linking in action.

Each scenario runs with realistic delays (2-5s between steps) so the dashboard live-updates visibly.

### Seed Data

Pre-loaded SQLite database with ~50 decisions across categories:
- 10 architecture decisions (7 reviewed: 5 success, 1 partial, 1 failure)
- 10 tooling decisions (6 reviewed: all success)
- 10 process decisions (5 reviewed: 4 success, 1 abandoned)
- 10 security decisions (4 reviewed: 3 success, 1 failure)
- 10 integration decisions (3 reviewed: all success)

This gives interesting calibration curves out of the box - enough data to show patterns, with intentional miscalibration in some buckets to demonstrate the value of calibration tracking.

### Quickstart (README.md)

```bash
git clone https://github.com/tfatykhov/cognition-agent-decisions
cd cognition-agent-decisions/demo
docker compose up

# Open dashboard: http://localhost:8080
# Watch the demo agent make decisions in real-time
# API available at: http://localhost:8100/cstp
```

### Demo Dashboard Experience

When you open the dashboard at `:8080`, you see:
1. **Overview** - 50+ decisions, calibration chart shows realistic spread
2. **Decisions list** - Mix of categories, stakes levels, outcomes
3. **Calibration** - Brier score, confidence buckets, some visibly miscalibrated
4. **Deliberation Viewer** - Live updates as demo agent runs new scenarios
5. **Decision Detail** - Click any decision to see full trace, graph neighbors

## Implementation

### Phase 1: Seed Data Generator (P1)
- Python script that generates realistic seed data directly into SQLite
- Configurable: number of decisions, review rate, category distribution
- Outputs `decisions.db` + `graph_edges.jsonl`

### Phase 2: Demo Agent (P1)
- Simple Python script using `httpx` to call CSTP JSON-RPC
- Scenarios defined as YAML or Python dataclasses
- Runs in a loop with configurable interval
- Logs activity to stdout for `docker compose logs` visibility

### Phase 3: Docker Compose (P1)
- Multi-service compose file
- Health checks on all services
- Volume mounts for persistence (optional)
- Environment variable defaults that just work

### Phase 4: Polish (P2)
- GIF/video of the demo in action for README
- "Try it in GitHub Codespaces" button
- Optional: demo with Claude Code MCP connection

## Success Criteria

- `docker compose up` to working dashboard: < 60 seconds
- Zero configuration required
- Demo agent visibly making decisions within 30 seconds of startup
- Dashboard shows meaningful calibration data immediately
- README is 20 lines or less to get started

## Risks

- **ChromaDB startup time** - May need 10-20s to initialize. Mitigate: health check + retry in demo agent.
- **Seed data staleness** - Pre-built DB may drift from schema changes. Mitigate: generate seed data as part of CI.
- **Port conflicts** - Users may have 8080/8100 in use. Mitigate: document override via `.env`.
