# Cognition Engines Demo

One command to see decision intelligence in action.

## Quick Start

```bash
cd demo/

# 1. Generate seed data (first time only)
python3 seed_data.py

# 2. Launch everything
docker compose up --build

# 3. Open the dashboard
#    Login: admin / demo
open http://localhost:8080
```

## What You'll See

| Service | URL | What it does |
|---------|-----|-------------|
| **Dashboard** | [localhost:8080](http://localhost:8080) | Calibration curves, decision list, deliberation viewer |
| **CSTP Server** | [localhost:8100](http://localhost:8100) | JSON-RPC + MCP endpoint at `/mcp` |
| **ChromaDB** | [localhost:8000](http://localhost:8000) | Vector store for semantic search |
| **Demo Agent** | (logs only) | MCP client making decisions in real-time |

The demo starts with **~30 pre-loaded decisions** across 5 categories, so the dashboard is interesting immediately. The demo agent adds new decisions every 60 seconds via MCP.

## Watch the Agent Work

```bash
docker compose logs -f demo-agent
```

The agent cycles through 5 scenarios:

1. **Architecture Decision** - Full `pre_action` → `record_thought` → `update_decision` flow
2. **Guardrail Block** - High-stakes + low-confidence decision gets blocked
3. **Review Decisions** - Query similar decisions, check calibration
4. **Session Context** - Fetch accumulated decision intelligence
5. **Ready Check** - See what needs attention

## Connect Your Own Agent

The CSTP server exposes MCP at `http://localhost:8100/mcp`. Connect any MCP client:

### Claude Code
```bash
npx mcp-remote@latest http://localhost:8100/mcp
```

### Python (MCP SDK)
```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8100/mcp") as (r, w, _):
    async with ClientSession(r, w) as session:
        await session.initialize()
        result = await session.call_tool("pre_action", {
            "description": "Your decision here",
            "auto_record": True,
        })
```

See `demo-agent/agent.py` for a complete reference implementation.

### FORGE Protocol

The demo agent follows the [FORGE protocol](https://github.com/tfatykhov/cognition-engines-marketplace/tree/main/forge) — a Claude Code plugin that defines how agents should interact with Cognition Engines:

**F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

Install FORGE in your Claude Code project to get automatic decision intelligence integration. See the [FORGE docs](https://cognition-engines.ai/guide/forge) for details.

## Configuration

Override ports or intervals via environment variables:

```bash
CSTP_PORT=9100 DASHBOARD_PORT=9080 DEMO_INTERVAL=120 docker compose up
```

## Cleanup

```bash
docker compose down -v   # removes volumes too
```
