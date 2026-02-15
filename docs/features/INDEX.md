# Feature Index

All feature specs live in `docs/features/`. One file per feature, consistent naming: `FXXX-short-name.md`.

## Shipped

| ID | Feature | Version | File |
|----|---------|---------|------|
| F001 | CSTP Server | v0.8.0 | `F001-cstp-server.md` |
| F002 | Query Decisions | v0.8.0 | `F002-query-decisions.md` |
| F003 | Check Guardrails | v0.8.0 | `F003-check-guardrails.md` |
| F004 | Announce Intent | v0.8.0 | `F004-announce-intent.md` |
| F005 | CSTP Client | v0.8.0 | `F005-cstp-client.md` |
| F006 | Docker Deployment | v0.8.0 | `F006-docker-deployment.md` |
| F007 | Record Decision | v0.8.0 | `F007-record-decision.md` |
| F008 | Review Decision | v0.8.0 | `F008-review-decision.md` |
| F009 | Get Calibration | v0.8.0 | `F009-get-calibration.md` |
| F010 | Project Context | v0.8.0 | `F010-project-context.md` |
| F011 | Web Dashboard | v0.8.0 | `F011-web-dashboard.md` |
| F014 | Rolling Calibration Windows | v0.9.0 | `V0.9.0-FEATURES.md` |
| F015 | Calibration Drift Alerts | v0.9.0 | `V0.9.0-FEATURES.md` |
| F016 | Confidence Variance Tracking | v0.9.0 | `V0.9.0-FEATURES.md` |
| F017 | Hybrid Retrieval Scoring | v0.9.0 | `V0.9.0-FEATURES.md` |
| F019 | List Guardrails | v0.9.1 | `F019-list-guardrails.md` |
| F022 | MCP Server | v0.10.0 | `F022-mcp-server.md` |
| F023 | Deliberation Traces | v0.10.0 | `F023-deliberation-traces.md` |
| F024 | Bridge Definitions | v0.10.0 | `F024-bridge-definitions.md` |
| F025 | Related Decisions | v0.10.0 | *(in changelog, no standalone spec)* |
| F027 | Decision Quality | v0.10.0 | `F027-decision-quality.md` |
| F028 | Reasoning Capture | v0.10.0 | *(shipped as part of F023/F027)* |
| F046 | Pre-Action Hook API | v0.11.0 | `F046-pre-action-hook.md` |
| F047 | Session Context Endpoint | v0.11.0 | `F047-session-context.md` |

## Roadmap

| ID | Feature | Source | File |
|----|---------|--------|------|
| F020 | Structured Reasoning Traces | Internal | `F020-reasoning-traces.md` |
| F029 | Task Router | MIT/Google Scaling Research | `F029-task-router.md` |
| F030 | Circuit Breaker Guardrails | AutoGPT + ai16z | `F030-circuit-breaker-guardrails.md` |
| F031 | Source Trust Scoring | ai16z Trust Scores | `F031-source-trust-scoring.md` |
| F032 | Error Amplification Tracking | MIT 17.2x Error Finding | `F032-error-amplification-tracking.md` |
| F033 | Censor Layer | Minsky Ch 27 | `F033-censor-layer.md` |
| F034 | Decomposed Confidence | Minsky Ch 28 | `F034-decomposed-confidence.md` |
| F035 | Semantic State Transfer | Cisco IoC, README | `F035-semantic-state-transfer.md` |
| F036 | Reasoning Continuity | Minsky teaching-selves | `F036-reasoning-continuity.md` |
| F037 | Collective Innovation | Cisco IoC, README | `F037-collective-innovation.md` |
| F038 | Cross-Agent Federation | Cisco IoC, README | `F038-cross-agent-federation.md` |
| F039 | Cognition Protocol Stack | Cisco IoC (SSTP/CSTP/LSTP) | `F039-protocol-stack.md` |
| F040 | Task-Decision Graph | Beads (steveyegge/beads) | `F040-task-decision-graph.md` |
| F041 | Memory Compaction | Beads (steveyegge/beads) | `F041-memory-compaction.md` |
| F042 | ~~Decision Dependency Graph~~ | ~~Beads~~ (merged into F045) | `F042-decision-dependencies.md` |
| F043 | Distributed Decision Merge | Beads (steveyegge/beads) | `F043-distributed-merge.md` |
| F044 | Agent Work Discovery | Beads (steveyegge/beads) | `F044-agent-work-discovery.md` |
| F045 | Decision Graph Storage Layer | GNN/KG Research (ICML 2025, MemoBrain, Context Graphs) | `F045-graph-storage-layer.md` |
| ~~F046~~ | ~~Pre-Action Hook API~~ | ~~Agentic Loop Integration~~ | *Shipped in v0.11.0* |
| ~~F047~~ | ~~Session Context Endpoint~~ | ~~Agentic Loop Integration~~ | *Shipped in v0.11.0* |
| F048 | Multi-Vector-DB Support | Infrastructure | `F048-multi-vectordb.md` |

## Retired IDs

| ID | Note |
|----|------|
| F012, F013, F018, F021, F026 | Unused / skipped |

## Implementation Plans

Detailed implementation plans for shipped features:
- `F011-implementation-plan.md`, `F011-phases.md`
- `F014-implementation-plan.md`
- `F015-implementation-plan.md`
- `F016-implementation-plan.md`
- `F017-implementation-plan.md`
- `F023-phase2-implementation.md`
