---
layout: home

hero:
  name: Cognition Engines
  text: Decision Intelligence for AI Agents
  tagline: "Query past decisions, enforce guardrails, and track calibration - all in two API calls. v0.14.0: Multi-Agent Isolation, Live Deliberation, and FORGE Plugin."
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
  - icon:
      src: /icon-query.png
      alt: Query
      width: 48
      height: 48
    title: Query Before Deciding
    details: Semantic search across past decisions. Find what worked, what failed, and why. Directional search by structure ("where did we use this pattern?") or function ("what solved this problem?").
  - icon:
      src: /icon-guardrails.png
      alt: Guardrails
      width: 48
      height: 48
    title: Guardrails
    details: Policy enforcement that prevents violations before they occur. Block high-stakes decisions with low confidence. Require code review for production changes.
  - icon:
      src: /icon-deliberation.png
      alt: Deliberation
      width: 48
      height: 48
    title: Deliberation Traces
    details: Every query and guardrail check automatically linked to the resulting decision. Full provenance of how each choice was made - zero client changes needed.
  - icon:
      src: /icon-bridge.png
      alt: Bridge
      width: 48
      height: 48
    title: Bridge-Definitions
    details: Describe decisions by both structure (what it looks like) and function (what it solves). Inspired by Minsky's Society of Mind Ch 12 - connecting patterns to purposes.
  - icon:
      src: /icon-related.png
      alt: Related
      width: 48
      height: 48
    title: Related Decisions
    details: Pre-decision query results automatically linked as lightweight graph edges. See which past decisions influenced each new choice, with semantic distance scores.
  - icon:
      src: /icon-calibration.png
      alt: Calibration
      width: 48
      height: 48
    title: Calibration & Analytics
    details: Track Brier scores, success rates, and confidence calibration over time. Reason-type analytics show which reasoning patterns predict success.
  - icon:
      src: /icon-forge.png
      alt: FORGE
      width: 48
      height: 48
    title: MCP + FORGE Plugin
    details: 14+ MCP tools for Claude Code, Claude Desktop, OpenClaw, and any MCP-compliant agent. FORGE plugin automates the full decision loop with hooks and commands.
  - icon:
      src: /icon-api.png
      alt: API
      width: 48
      height: 48
    title: JSON-RPC API
    details: CSTP protocol over HTTP. Query, check, record, review - all via simple JSON-RPC 2.0 calls. Built on FastAPI with ChromaDB for semantic search.
---

## How It Works

## FORGE - The Decision Loop

**F**etch → **O**rient → **R**esolve → **G**o → **E**xtract

You forge decisions in the Cognition Engine - deliberately, under pressure, with intention. Every decision flows through this loop, creating a compounding record of organizational judgment.

| Phase | What happens |
|-------|-------------|
| **Fetch** | Load context and past decisions |
| **Orient** | Check guardrails and constraints |
| **Resolve** | Decide and record with reasoning |
| **Go** | Execute |
| **Extract** | Evaluate outcomes and distill patterns |

Available as a [Claude Code plugin](https://github.com/tfatykhov/cognition-engines-marketplace) with hooks, commands, and skills that automate the entire loop.

## How It Works

Two calls cover the full agent workflow:

```
Session start  → get_session_context  (cognitive context: profile, calibration, patterns)
Decision point → pre_action           (query + guardrails + record in one call)
```

The server auto-captures deliberation traces, bridge-definitions, and related decision links - zero client changes needed.

```json
{
  "allowed": true,
  "similar_decisions": [...],
  "guardrail_results": [...],
  "calibration_context": {"brier_score": 0.024, "accuracy": 0.963},
  "decision_id": "abc123"
}
```
