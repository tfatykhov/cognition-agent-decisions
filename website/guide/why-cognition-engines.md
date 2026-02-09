# Why Cognition Engines?

AI agents make thousands of decisions. Most tooling treats these as opaque log entries or metrics. Cognition Engines treats them as **first-class artifacts** with structure, feedback, and recall.

Here's how it compares to the tools you already know.

## Decisions Are Artifacts, Not Logs

Observability platforms (Datadog, LangSmith, Langfuse) capture **traces** — what happened, in what order, how long it took. That's useful for debugging, but a trace doesn't tell you *why* an agent chose path A over path B, or whether it would make the same choice again.

Cognition Engines records decisions with:

- **Structured reasons** (typed: analysis, pattern, empirical, intuition, …)
- **Confidence scores** that become calibration data
- **Stakes levels** that feed into guardrails
- **Context** that enables semantic recall later

A decision is a *claim about the world* with attached justification — not a log line.

## Outcome Feedback Loop

Most guardrail and evaluation tools are **one-directional**: they check inputs and flag problems. They don't close the loop.

Cognition Engines supports a full lifecycle:

1. **Record** a decision with confidence
2. **Review** the outcome when it's known
3. **Calibrate** — are 0.8-confidence decisions actually succeeding 80% of the time?
4. **Adjust** — surface overconfidence or systematic blind spots

This is how expert judgment improves. Without outcome tracking, you're flying blind on whether your agent's decision quality is improving or degrading.

## Bridge-Definitions Connect Structure to Purpose

Inspired by Minsky's *Society of Mind* (Ch. 12), bridge-definitions link the **structural form** of a decision to its **functional purpose**:

- *"We chose Redis"* is structure (what)
- *"We needed shared state across instances"* is function (why)

When an agent searches past decisions, it can search by either axis independently:

- **"What solves shared-state problems?"** → finds the Redis decision by function
- **"Where else did we use Redis?"** → finds it by structure

Two independent recall paths mean better retrieval. If both paths point to the same answer, confidence goes up — Minsky's parallel-bundle principle (Ch. 18).

Traditional vector search treats the whole decision as a single embedding. Bridge-definitions give you two.

## Deliberation Traces Are Automatic

Many systems require clients to manually instrument their reasoning chains. Cognition Engines captures deliberation traces **from normal API usage** — no client changes needed.

When an agent:
1. Queries similar past decisions
2. Checks guardrails
3. Records a decision

The server automatically links steps 1 and 2 as **inputs** to step 3. The result is a trace showing *what the agent considered before deciding*, built from the calls it was already making.

Zero instrumentation overhead. Zero client SDK changes.

## Built for AI Agents, Not Dashboards

Most decision and governance tools assume a human is in the loop — approval workflows, visual dashboards, manual review queues. Cognition Engines is designed for agents operating autonomously at speed:

| Concern | Dashboard-First Tools | Cognition Engines |
|---------|----------------------|-------------------|
| Primary consumer | Human analyst | AI agent |
| Decision format | Free text / UI form | Structured JSON-RPC |
| Recall mechanism | Manual search | Semantic + hybrid retrieval |
| Guardrails | Human approval gates | Programmatic rules, agent-evaluated |
| Feedback loop | Periodic human review | Continuous outcome tracking |
| Integration | SDK / UI | JSON-RPC + MCP (7 tools) |

The dashboard exists (for humans who want to inspect agent behavior), but the system is designed API-first for autonomous agents.

## Summary

| Capability | Observability Tools | Guardrail Tools | Cognition Engines |
|-----------|--------------------|-----------------|--------------------|
| Capture what happened | ✅ Traces | ❌ | ✅ Decisions |
| Capture *why* | ❌ | ❌ | ✅ Typed reasons |
| Block bad actions | ❌ | ✅ Rules | ✅ Guardrails |
| Learn from outcomes | ❌ | ❌ | ✅ Calibration |
| Recall past decisions | ❌ | ❌ | ✅ Hybrid search |
| Dual-axis retrieval | ❌ | ❌ | ✅ Bridge-definitions |
| Auto deliberation traces | ❌ | ❌ | ✅ Zero-instrument |

Cognition Engines doesn't replace your observability stack — it sits alongside it, giving your agents a structured memory of *what they decided and why*, with feedback that makes future decisions better.

---

**Next:** [Golden Path Walkthrough](/guide/golden-path) — Try it hands-on in 10 minutes.
