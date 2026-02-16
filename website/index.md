---
layout: home

hero:
  name: Cognition Engines
  text: Decision Intelligence for AI Agents
  tagline: "Query past decisions, enforce guardrails, and track calibration - all in two API calls. v0.11.0: Pre-Action Hook, Dashboard, and Pluggable Storage."
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
    details: 11 MCP tools for Claude Code, Claude Desktop, OpenClaw, and any MCP-compliant agent. Two PRIMARY tools (pre_action, get_session_context) handle the full workflow.
  - icon: ⚡
    title: JSON-RPC API
    details: CSTP protocol over HTTP. Query, check, record, review - all via simple JSON-RPC 2.0 calls. Built on FastAPI with ChromaDB for semantic search.
---

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

<style>
.contact-card {
  margin: 2rem auto;
  max-width: 480px;
  padding: 2rem;
  border-radius: 12px;
  background: var(--vp-c-bg-soft);
  border: 1px solid var(--vp-c-divider);
  text-align: center;
}
.contact-card h2 {
  margin: 0 0 0.5rem;
  font-size: 1.4rem;
  border-top: none;
}
.contact-card p {
  margin: 0.4rem 0;
  color: var(--vp-c-text-2);
}
.contact-card a {
  color: var(--vp-c-brand-1);
  text-decoration: none;
  font-weight: 500;
}
.contact-card a:hover {
  text-decoration: underline;
}
.contact-card .email {
  font-size: 1.1rem;
  margin: 1rem 0;
}
.contact-card .links {
  display: flex;
  justify-content: center;
  gap: 1.5rem;
  margin-top: 1rem;
}
</style>

<div class="contact-card">
  <h2>📬 Get in Touch</h2>
  <p><strong>Timur Fatykhov</strong></p>
  <p class="email">
    <a href="mailto:timur.fatykhov@cognition-engines.ai">timur.fatykhov@cognition-engines.ai</a>
  </p>
  <div class="links">
    <a href="https://github.com/tfatykhov/cognition-agent-decisions">GitHub</a>
    <a href="https://github.com/tfatykhov/cognition-agent-decisions/issues">Issues</a>
    <a href="/contact">More →</a>
  </div>
</div>

