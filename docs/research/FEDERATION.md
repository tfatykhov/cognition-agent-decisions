# Federation Research (v0.8+)

| Field | Value |
|-------|-------|
| Status | Research Needed |
| Priority | Future |
| Decision | 7cf4f72d |
| Created | 2026-02-04 |

---

## Context

Federation (F004 announceIntent, F005 CSTP Client) deferred from v0.7.0. Need more research on use cases before implementation.

## Current Understanding

**Centralized model (v0.7.0):**
- Single cognition-engines instance
- All agents share decisions + guardrails
- Sufficient for single-user multi-agent setup
- Simpler architecture

**Federated model (future):**
- Each agent has own cognition-engines
- Agents query each other via A2A/CSTP
- Needed for multi-org, air-gapped, or specialized policy agents

## Research Questions

1. **Use cases:** When is federation actually needed vs over-engineering?
   - Multi-organization collaboration
   - Compliance/audit requirements (separate decision trails)
   - Specialized policy domains (security, compliance, ops)
   - Geographic distribution / latency

2. **Trust model:** How do agents trust each other's decisions?
   - Authentication between agents
   - Decision signing / verification
   - Reputation / confidence weighting

3. **Consistency:** How to handle conflicting guardrails?
   - Veto model (any agent can block)
   - Consensus model (majority agree)
   - Priority model (security > ops > dev)

4. **Discovery:** How do agents find each other?
   - Static registry (config file)
   - Dynamic discovery (DNS-SD, mDNS)
   - Central registry service

5. **Privacy:** What to share vs keep private?
   - Decision titles/outcomes (shareable)
   - Full context/reasoning (private?)
   - Guardrail rules (shareable)

## Related Work

- **A2A Protocol:** Google's agent-to-agent standard (task-level)
- **MCP:** Model Context Protocol (tool-level)
- **CSTP (proposed):** Cognition State Transfer (intent-level)

## Next Steps

1. Monitor v0.7.0 usage — do users ask for federation?
2. Research multi-agent coordination papers
3. Prototype simple two-agent scenario
4. Define trust model before implementation

## Review Date

2026-03-06 (30 days from decision)
