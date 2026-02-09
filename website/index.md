---
layout: home

hero:
  name: Cognition Engines
  text: Decision Intelligence for AI Agents
  tagline: Every decision automatically captures its full cognitive context - deliberation traces, bridge-definitions, and related decision links.
  image:
    src: /logo.png
    alt: Cognition Engines
  actions:
    - theme: brand
      text: Get Started
      link: /guide/what-is-cognition-engines
    - theme: alt
      text: Agent Quick Start
      link: /guide/agent-quickstart
    - theme: alt
      text: View on GitHub
      link: https://github.com/tfatykhov/cognition-agent-decisions

features:
  - icon: 🔍
    title: Query Before Deciding
    details: Semantic search across past decisions. Find what worked, what failed, and why. Directional search by structure ("where did we use this pattern?") or function ("what solved this problem?").
  - icon: 🛡️
    title: Guardrails
    details: Policy enforcement that prevents violations before they occur. Block high-stakes decisions with low confidence. Require code review for production changes.
  - icon: 🧠
    title: Deliberation Traces
    details: Every query and guardrail check automatically linked to the resulting decision. Full provenance of how each choice was made - zero client changes needed.
  - icon: 🌉
    title: Bridge-Definitions
    details: Describe decisions by both structure (what it looks like) and function (what it solves). Inspired by Minsky's Society of Mind Ch 12 - connecting patterns to purposes.
  - icon: 🔗
    title: Related Decisions
    details: Pre-decision query results automatically linked as lightweight graph edges. See which past decisions influenced each new choice, with semantic distance scores.
  - icon: 📊
    title: Calibration & Analytics
    details: Track Brier scores, success rates, and confidence calibration over time. Reason-type analytics show which reasoning patterns predict success.
  - icon: 🔌
    title: MCP Integration
    details: 7 native MCP tools for Claude Desktop, OpenClaw, and any MCP-compliant agent. Streamable HTTP at /mcp - plug into any AI agent system.
  - icon: ⚡
    title: JSON-RPC API
    details: CSTP protocol over HTTP. Query, check, record, review - all via simple JSON-RPC 2.0 calls. Built on FastAPI with ChromaDB for semantic search.
---

## How It Works

Every significant decision follows a simple protocol. The server handles the rest automatically.

```
1. Query  →  "What solved problems like this?"
2. Check  →  "Am I allowed to do this?"
3. Record →  "Here's what I decided and why"
```

The server auto-captures:
- **Deliberation trace** from your queries and checks
- **Bridge-definition** extracted from your decision text
- **Related decisions** linked from your query results

```json
{
  "id": "abc123",
  "deliberation_auto": true,
  "deliberation_inputs_count": 2,
  "bridge_auto": true,
  "related_count": 5
}
```

