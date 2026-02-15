# F038: Cross-Agent Federation

> **Status:** Proposed
> **Target:** v1.0.0 (Multi-Agent Cognition Network)
> **Source:** README roadmap, docs/research/FEDERATION.md, Cisco Outshift IoC
> **Depends on:** F035 (Semantic State Transfer), F031 (Source Trust Scoring)

## Overview
Enable multiple independent CSTP server instances to discover each other, share decisions and guardrails, and query across organizational boundaries. Each agent maintains its own decision store but can selectively federate with peers - sharing what's appropriate while keeping sensitive decisions private.

## Problem
Current architecture is hub-and-spoke: all agents connect to one CSTP server. This works for a single user's agents but breaks down for:
- Multi-organization collaboration (each org runs their own CSTP)
- Air-gapped environments (no shared network)
- Specialized policy domains (security team has different guardrails than dev team)
- Geographic distribution (latency to central server)

## Architecture

### Federation Topology
```
┌──────────────────┐     ┌──────────────────┐
│  Org A CSTP      │     │  Org B CSTP      │
│  ┌────┐ ┌────┐   │     │  ┌────┐ ┌────┐   │
│  │AgA1│ │AgA2│   │◄───►│  │AgB1│ │AgB2│   │
│  └────┘ └────┘   │     │  └────┘ └────┘   │
│  Guardrails: orgA│     │  Guardrails: orgB│
└──────────────────┘     └──────────────────┘
         ▲                        ▲
         │    ┌──────────────┐    │
         └───►│ Federation   │◄───┘
              │ Registry     │
              └──────────────┘
```

### Trust Model
```json
{
  "peer": {
    "id": "cstp://orgb.example.com",
    "name": "Org B CSTP",
    "trustLevel": "verified",
    "permissions": {
      "queryDecisions": true,
      "shareGuardrails": true,
      "importDecisions": false,
      "viewDeliberation": false
    },
    "publicKey": "...",
    "verifiedAt": "2026-02-11T20:00:00Z"
  }
}
```

### Trust Levels
| Level | Meaning | Permissions |
|-------|---------|-------------|
| `anonymous` | Unknown peer | Query only (public decisions) |
| `verified` | Identity confirmed | Query + shared guardrails |
| `trusted` | Established relationship | Full query + import + deliberation |
| `internal` | Same organization | Everything |

## API

### `cstp.registerPeer`
```json
{
  "method": "cstp.registerPeer",
  "params": {
    "url": "cstp://orgb.example.com",
    "trustLevel": "verified",
    "sharedToken": "..."
  }
}
```

### `cstp.federatedQuery`
```json
{
  "method": "cstp.federatedQuery",
  "params": {
    "query": "database migration patterns",
    "scope": "federation",
    "peers": ["cstp://orgb.example.com"],
    "minTrustLevel": "verified"
  }
}
```

### Response
```json
{
  "result": {
    "local": [{"id": "dec_abc", "source": "local", ...}],
    "federated": [
      {
        "id": "dec_xyz",
        "source": "cstp://orgb.example.com",
        "trustLevel": "verified",
        "trustScore": 0.78,
        "decision": "Used event sourcing for migration",
        "redacted": ["context", "deliberation"]
      }
    ]
  }
}
```

### `cstp.listPeers`
List registered federation peers with health status.

### `cstp.syncGuardrails`
Import/export shared guardrail policies between peers.

## Discovery

### Static Registry
```yaml
federation:
  peers:
    - url: cstp://peer1.example.com
      token: "..."
      trust: verified
```

### Dynamic (Future)
- DNS-SD for local network discovery
- Central registry for internet-scale federation
- Agent card exchange (A2A protocol)

## Privacy Controls
- **Decision visibility:** public / org / private per decision
- **Redaction:** Strip context/deliberation from federated results
- **Guardrail scoping:** org-level vs federated-level policies
- **Audit trail:** All federated queries logged

## Integration
- F031 Source Trust: Federated results weighted by peer trust
- F035 State Transfer: Bundle format for federation sync
- F037 Collective Innovation: Cross-org deliberation sessions
- F030 Circuit Breakers: Federation-wide circuit breakers for coordinated safety

## Acceptance Criteria
- [ ] `cstp.registerPeer` RPC method
- [ ] `cstp.federatedQuery` RPC method
- [ ] `cstp.listPeers` RPC method
- [ ] `cstp.syncGuardrails` RPC method
- [ ] Trust level enforcement on federated queries
- [ ] Privacy controls (visibility, redaction)
- [ ] Peer health monitoring
- [ ] MCP tools exposed
- [ ] Dashboard: Federation network view
- [ ] Static registry configuration
