# Provisional Patent Application Outline
# Cognition Engines: Decision Intelligence System for AI Agents

**Inventor:** Timur Fatykhov
**Date:** February 9, 2026
**Status:** DRAFT - For review with patent attorney

---

## 1. TITLE OF INVENTION

**System and Method for Automated Decision Intelligence, Deliberation Capture, and Multi-Dimensional Semantic Retrieval for Autonomous AI Agents**

---

## 2. FIELD OF THE INVENTION

The present invention relates to artificial intelligence systems, and more particularly to a computer-implemented system and method for recording, analyzing, and retrieving structured decision records made by autonomous AI agents, including automatic capture of deliberation processes and multi-dimensional semantic retrieval using dual structure-function descriptions.

---

## 3. BACKGROUND OF THE INVENTION

### 3.1 Problem Statement

Large Language Model (LLM)-based AI agents operate in stateless sessions, losing all decision context between interactions. When an agent makes architectural choices, selects tools, or commits to approaches, this reasoning is discarded at session end. Subsequent sessions cannot query past decisions, learn from outcomes, or avoid repeating mistakes.

### 3.2 Limitations of Existing Approaches

Current approaches to AI agent memory suffer from several limitations:

- **Conversation logging** stores raw text but lacks structured decision semantics, making retrieval imprecise
- **RAG (Retrieval-Augmented Generation)** systems retrieve documents but do not model decision-specific metadata (confidence, reasoning types, outcomes, stakes)
- **Observability/tracing tools** (e.g., OpenTelemetry) capture system-level spans but do not capture cognitive deliberation - the reasoning process itself
- **Existing decision platforms** (e.g., Qomplx US20250259041A1) focus on deontic/normative reasoning constraints but do not address decision memory, outcome tracking, or deliberation auto-capture

### 3.3 Need in the Art

There exists a need for a system that:
1. Structures AI agent decisions as first-class retrievable records with multi-type reasoning support
2. Automatically captures the deliberation process (queries consulted, guardrails checked) without client instrumentation
3. Enables directional semantic retrieval using dual descriptions (structure and function) of each decision
4. Tracks decision outcomes over time for calibration and learning
5. Automatically builds lightweight relationship graphs between decisions from natural agent workflow

---

## 4. SUMMARY OF THE INVENTION

The invention provides a computer-implemented decision intelligence system comprising:

**(a)** A **Cognitive State Transfer Protocol (CSTP)** server that receives, stores, indexes, and retrieves structured decision records from one or more AI agents via JSON-RPC and/or Model Context Protocol (MCP) interfaces;

**(b)** A **deliberation auto-capture subsystem** that observes an agent's pre-decision workflow (queries to past decisions, guardrail checks) and automatically constructs a structured deliberation trace without requiring client-side instrumentation;

**(c)** A **bridge-definition subsystem** that automatically generates dual descriptions of each decision - a structural description (what the decision looks like, its form and pattern) and a functional description (what the decision does, its purpose and effect) - enabling directional semantic search;

**(d)** A **related-decision subsystem** that automatically populates graph edges between decisions by extracting semantically similar prior decisions from pre-decision query results;

**(e)** A **guardrail enforcement subsystem** that evaluates policy constraints against proposed agent actions before execution, with configurable rules based on decision stakes, confidence levels, and contextual factors;

**(f)** A **calibration and outcome tracking subsystem** that records actual outcomes of past decisions and computes statistical measures (Brier scores, category success rates, reason-type effectiveness) to assess and improve agent decision quality over time.

---

## 5. DETAILED DESCRIPTION OF THE INVENTION

### 5.1 System Architecture

The system comprises a server process with the following components:

```
+------------------+     +-------------------+     +------------------+
|   AI Agent(s)    |---->|   CSTP Server     |---->|  Vector Store    |
| (LLM sessions)  |     |  (JSON-RPC/MCP)   |     |  (ChromaDB)     |
+------------------+     +-------------------+     +------------------+
                              |         |
                    +---------+---------+---------+
                    |         |         |         |
               +--------+ +-------+ +-------+ +--------+
               |Deliber-| |Bridge | |Guard- | |Calibra-|
               |ation   | |Defn   | |rails  | |tion    |
               |Tracker | |Engine | |Engine | |Engine  |
               +--------+ +-------+ +-------+ +--------+
```

### 5.2 Claim 1: Decision Record Structure with Multi-Type Reasoning

A computer-implemented method for storing AI agent decisions, comprising:

- Receiving from an AI agent a decision record comprising: a natural language decision description, a numerical confidence value between 0.0 and 1.0, a category classification, a stakes assessment, contextual information, and one or more structured reason objects;
- Wherein each reason object comprises a reason type selected from a predetermined taxonomy (including but not limited to: analysis, pattern, authority, intuition, empirical, analogy, elimination, constraint) and a natural language text description;
- Generating a vector embedding of the decision description using a text embedding model;
- Storing the decision record with its embedding in a persistent vector store;
- Enabling subsequent semantic similarity retrieval of the stored decision based on query embeddings.

**Novelty:** Existing systems store decisions as unstructured text or simple key-value pairs. This invention structures reasoning as typed, multi-dimensional arguments that can be independently analyzed for effectiveness (e.g., "Do pattern-type reasons predict success better than intuition-type reasons?").

### 5.3 Claim 2: Server-Side Deliberation Auto-Capture (F023)

A computer-implemented method for automatically capturing an AI agent's deliberation process, comprising:

- Maintaining, on the server side, a session tracker keyed by agent identifier with a configurable time-to-live (TTL);
- When the server receives a decision query request from an agent, recording the query text, timestamp, and top-N results as a tracked input in the agent's tracker session;
- When the server receives a guardrail check request from the same agent, recording the action description, stakes, confidence, and check result as an additional tracked input;
- When the server subsequently receives a decision record request from the same agent within the TTL window, automatically constructing a deliberation trace comprising: (i) an ordered list of inputs consulted, (ii) timestamped processing steps, (iii) total deliberation timing, and (iv) a convergence flag indicating whether query results aligned with the final decision;
- Attaching the constructed deliberation trace to the decision record without requiring any client-side instrumentation or modification to the agent's workflow.

**Novelty:** Unlike distributed tracing systems (OpenTelemetry) that require client-side span instrumentation, this system infers the deliberation process entirely from server-side observation of the agent's natural query-check-record workflow. The agent does not need to know it is being traced.

### 5.4 Claim 3: Bridge-Definition Dual Description with Directional Search (F024)

A computer-implemented method for multi-dimensional semantic retrieval of decision records, comprising:

- For each stored decision record, generating or receiving a bridge-definition comprising: (i) a structural description characterizing the form, pattern, or architecture of the decision, and (ii) a functional description characterizing the purpose, effect, or problem solved by the decision;
- Generating separate vector embeddings for the structural description and the functional description;
- When a search query is received with a directional parameter ("structure" or "function"), computing similarity against only the corresponding embedding dimension;
- When a search query is received without a directional parameter, computing similarity against all embedding dimensions;
- Returning ranked results based on the directional or combined similarity scores.

**Novelty:** This enables the same decision to be found via two independent retrieval paths: "What approaches solved problems like this?" (function-side search) versus "Where else did we use this pattern?" (structure-side search). When both paths return the same result, confidence in the retrieval is independently validated (inspired by Minsky's "Society of Mind" parallel bundle reasoning). No existing patent or system provides directional semantic search with auto-generated dual descriptions for decision records.

### 5.5 Claim 4: Automatic Related-Decision Graph Construction (F025)

A computer-implemented method for building a decision relationship graph, comprising:

- When an AI agent queries the system for similar past decisions prior to recording a new decision, storing the top-N query results with their similarity distances in the agent's tracker session;
- When the agent subsequently records a new decision, extracting the stored query results from the tracker session before the session is consumed by deliberation trace construction;
- Creating related-decision edges between the new decision and each of the prior decisions returned by the query, comprising: the related decision identifier, a summary, and the similarity distance;
- Storing these edges as part of the new decision record;
- Enabling graph traversal queries across the accumulated decision corpus.

**Novelty:** This constructs a relationship graph from the agent's natural pre-decision workflow without requiring explicit linking. The graph emerges organically from the agent's research behavior.

### 5.6 Claim 5: Pre-Execution Guardrail Enforcement with Configurable Policy Rules

A computer-implemented method for enforcing decision-making policies on AI agents, comprising:

- Receiving from an AI agent a proposed action description, stakes assessment, and confidence level;
- Evaluating the proposed action against a set of configurable guardrail rules, where each rule specifies: a condition based on action metadata (stakes, confidence, category, context), and a blocking or warning response;
- Returning to the agent a pass/fail determination with specific rule violations identified;
- Recording the guardrail evaluation as part of the agent's deliberation trace.

### 5.7 Claim 6: Decision Outcome Tracking and Calibration Analytics

A computer-implemented method for tracking and analyzing AI agent decision quality, comprising:

- Associating outcome data (success, partial, failure, abandoned) with previously stored decision records;
- Computing calibration statistics including: Brier scores across confidence ranges, success rates by category, effectiveness metrics by reason type;
- Detecting calibration drift by comparing recent decision outcomes against historical baselines;
- Generating alerts when drift exceeds configurable thresholds.

### 5.8 Claim 7: Combined System

A computer-implemented system combining Claims 1-6, wherein:

- The deliberation auto-capture (Claim 2), bridge-definition generation (Claim 3), related-decision extraction (Claim 4), and guardrail evaluation (Claim 5) operate automatically and concurrently during a single decision recording workflow;
- The system requires zero client-side changes to enable any of these features;
- The combined system produces a decision record enriched with deliberation trace, dual structural-functional descriptions, related decision graph edges, guardrail evaluation results, and multi-type reasoning - all from a single record request.

---

## 6. DRAWINGS (to be prepared)

1. **FIG. 1** - System architecture diagram showing CSTP server components
2. **FIG. 2** - Decision record data structure with all enrichment fields
3. **FIG. 3** - Deliberation auto-capture sequence diagram (query -> check -> record -> trace construction)
4. **FIG. 4** - Bridge-definition generation and directional search flow
5. **FIG. 5** - Related-decision graph construction from pre-decision queries
6. **FIG. 6** - Guardrail evaluation pipeline
7. **FIG. 7** - Calibration analytics computation flow

---

## 7. PRIOR ART DIFFERENTIATION

| Prior Art | What It Covers | How This Invention Differs |
|-----------|---------------|---------------------------|
| Qomplx US20250259041A1 (Filed 2025-01-31) | AI agent decision platform with deontic reasoning, normative constraints, symbolic/neural integration | Qomplx focuses on what agents are *permitted* to do (deontic logic). This invention focuses on *learning from past decisions* - memory, retrieval, outcome tracking, deliberation capture. Complementary, not overlapping. |
| OpenTelemetry / Distributed Tracing | System-level span capture for observability | Requires client-side instrumentation. This invention captures cognitive deliberation server-side without client changes. Traces reasoning, not system calls. |
| RAG Systems (general) | Document retrieval augmented generation | RAG retrieves documents. This invention retrieves structured decision records with typed reasoning, dual descriptions, and relationship graphs. Domain-specific semantic model for decisions. |
| Decision Support Systems (general) | Help humans make decisions | This invention serves autonomous AI agents, not humans. Auto-capture and auto-enrichment assume no human in the loop during the decision process. |

---

## 8. APACHE 2.0 LICENSE COMPATIBILITY

The invention is released under the Apache License 2.0, which includes an explicit patent grant (Section 3) providing users a perpetual, worldwide, royalty-free patent license to make, use, sell, and distribute the software. This means:

- Users of the open-source implementation are automatically licensed
- The patent provides defensive protection against patent trolls who might file competing claims on similar methods
- Contributors who submit code also grant patent rights per Apache 2.0 terms
- The patent does NOT restrict open-source usage - it protects the inventor's priority and prevents others from patenting the same methods

---

## 9. TIMELINE AND PRIOR ART DATES

| Event | Date | Significance |
|-------|------|-------------|
| First public commit (GitHub) | February 3, 2026 | Starts 12-month US grace period |
| CSTP server deployed | ~February 5, 2026 | Working implementation |
| F023 Deliberation Traces shipped | February 8, 2026 | Novel auto-capture feature |
| F024 Bridge-Definitions shipped | February 8, 2026 | Novel dual-description search |
| F025 Related Decisions shipped | February 8, 2026 | Novel auto-graph construction |
| v0.10.0 release | February 8, 2026 | All features combined |
| **Grace period deadline** | **~February 3, 2027** | **Must file provisional by this date** |

---

## 10. ESTIMATED COSTS

| Item | Micro Entity | Small Entity | Notes |
|------|-------------|-------------|-------|
| USPTO Provisional Filing Fee | $65 | $160 | Micro entity = <4 patents, income < threshold |
| Patent Attorney (optional for provisional) | $2,000-5,000 | $3,000-7,000 | Recommended for claim language |
| Utility Patent (within 12 months of provisional) | $800 | $1,600 | Filing + search + examination fees |
| Attorney for Utility Patent | $8,000-15,000 | $10,000-20,000 | Full prosecution |

**Micro entity** likely applies if: fewer than 4 prior patents AND gross income below ~$234,000.

---

## 11. RECOMMENDED NEXT STEPS

1. **Review this outline** - Identify any claims to strengthen or remove
2. **Consult a patent attorney** specializing in software/AI patents (post-Alice 101 expertise critical)
3. **File provisional patent application** ($65-160 filing fee) to lock in priority date
4. **Prepare formal drawings** (FIGs 1-7) - can be done for provisional but not required
5. **Within 12 months**, decide whether to convert to full utility patent application
6. **Consider international filing** - PCT application if international protection desired (but note: no grace period in most non-US jurisdictions, so US repo publication may limit international options)

---

## 12. RISK ASSESSMENT

**Strengths:**
- Novel combination of features (deliberation auto-capture + bridge-definitions + related decisions) not found in any existing patent
- Working implementation with real-world usage data
- Apache 2.0 provides defensive moat while maintaining open source
- Within US grace period (12 months from first disclosure)

**Risks:**
- Software patent eligibility under Alice Corp. v. CLS Bank (2014) - claims must demonstrate "technical improvement" not just "abstract idea implemented on a computer"
- Minsky's "Society of Mind" (1986) as potential prior art for bridge-definition concepts (though the computational implementation is novel)
- International patents likely precluded by public disclosure without grace period
- Individual concepts (semantic search, guardrails, outcome tracking) are known - novelty lies in the specific combination and auto-capture methods
- Cost of full utility patent prosecution ($10K-20K+)

**Mitigation:**
- Frame claims around the technical methods (server-side observation, dual-embedding directional search, auto-graph construction) rather than abstract concepts
- Emphasize the "zero client instrumentation" aspect as a technical improvement
- Consider whether defensive publication (establishing prior art to prevent others from patenting) is sufficient vs. full patent

---

*This document is a preliminary outline for discussion purposes. It does not constitute legal advice. Consult a registered patent attorney before filing.*
