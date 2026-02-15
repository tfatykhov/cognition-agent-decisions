# Feature Specs

Design documents for Cognition Engines features — past, present, and future.

## Shipped (v0.8.0)

| Spec | Feature |
|------|---------|
| [F001](/specs/f001-cstp-server) | CSTP Server Infrastructure |
| [F002](/specs/f002-query-decisions) | Query Decisions |
| [F003](/specs/f003-check-guardrails) | Check Guardrails |
| [F004](/specs/f004-announce-intent) | Announce Intent |
| [F005](/specs/f005-cstp-client) | CSTP Client |
| [F006](/specs/f006-docker-deployment) | Docker Deployment |
| [F007](/specs/f007-record-decision) | Record Decision |
| [F008](/specs/f008-review-decision) | Review Decision |
| [F009](/specs/f009-get-calibration) | Get Calibration |
| [F010](/specs/f010-project-context) | Project Context |
| [F011](/specs/f011-web-dashboard) | Web Dashboard |

## Shipped (v0.9.0)

| Spec | Feature |
|------|---------|
| [F019](/specs/f019-list-guardrails) | List Guardrails |

::: info
F014–F017 (Hybrid Retrieval, Temporal Decay, Reason Diversity, Bridge Search) were shipped in v0.9.0 but their specs were implementation plans only. See the [changelog](/changelog) for details.
:::

## Shipped (v0.10.0)

| Spec | Feature |
|------|---------|
| [F022](/specs/f022-mcp-server) | MCP Server |
| [F023](/specs/f023-deliberation-traces) | Deliberation Traces |
| [F024](/specs/f024-bridge-definitions) | Bridge-Definitions |
| [F027](/specs/f027-decision-quality) | Decision Recording Quality |

## Shipped (v0.11.0)

| Spec | Feature |
|------|---------|
| [F046](/specs/f046-pre-action-hook) | Pre-Action Hook API |
| [F047](/specs/f047-session-context) | Session Context Endpoint |

## Roadmap

### Research & Observability

| Spec | Feature |
|------|---------|
| [F020](/specs/f020-reasoning-traces) | Structured Reasoning Traces |
| [F029](/specs/f029-task-router) | Task Router |
| [F030](/specs/f030-circuit-breaker-guardrails) | Circuit Breaker Guardrails |
| [F031](/specs/f031-source-trust-scoring) | Source Trust Scoring |
| [F032](/specs/f032-error-amplification-tracking) | Error Amplification Tracking |

### Minsky-Inspired

| Spec | Feature |
|------|---------|
| [F033](/specs/f033-censor-layer) | Censor Layer |
| [F034](/specs/f034-decomposed-confidence) | Decomposed Confidence |

### Federation

| Spec | Feature |
|------|---------|
| [F035](/specs/f035-semantic-state-transfer) | Semantic State Transfer |
| [F036](/specs/f036-reasoning-continuity) | Reasoning Continuity |
| [F037](/specs/f037-collective-innovation) | Collective Innovation |
| [F038](/specs/f038-cross-agent-federation) | Cross-Agent Federation |
| [F039](/specs/f039-protocol-stack) | Cognition Protocol Stack |

### Beads-Inspired (Decision Graphs)

| Spec | Feature |
|------|---------|
| [F040](/specs/f040-task-decision-graph) | Task-Decision Graph |
| [F041](/specs/f041-memory-compaction) | Memory Compaction |
| [F042](/specs/f042-decision-dependencies) | Decision Dependencies |
| [F043](/specs/f043-distributed-merge) | Distributed Merge |
| [F044](/specs/f044-agent-work-discovery) | Agent Work Discovery |
| [F045](/specs/f045-graph-storage-layer) | Graph Storage Layer |

### Infrastructure

| Spec | Feature |
|------|---------|
| [F048](/specs/f048-multi-vectordb) | Multi-Vector-DB Support |

## Theoretical Sources

| Chapter | Concept | Applied In |
|---------|---------|-----------|
| Minsky Ch 12 | Bridge-Definitions | F024 |
| Minsky Ch 18 | Parallel Bundles | Reason types, confidence |
| Minsky Ch 27 | Censors vs Suppressors | F033 |
| Minsky Ch 28 | Mental Currencies | F034 |
| Beads (Wirth) | Linked Structures | F040–F045 |
