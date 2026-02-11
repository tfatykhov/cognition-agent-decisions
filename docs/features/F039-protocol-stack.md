# F039: Cognition Protocol Stack (SSTP/CSTP/LSTP)

> **Status:** Proposed
> **Target:** v1.0.0+ (Multi-Agent Cognition Network)
> **Source:** Cisco Outshift Internet of Cognition, README roadmap

## Overview
Implement the three-layer protocol stack from Cisco Outshift's Internet of Cognition architecture. Each layer optimizes for different trade-offs between human auditability, bandwidth efficiency, and inference fidelity.

## Protocol Layers

### SSTP - Semantic State Transfer Protocol
**Layer:** Semantic (human-auditable)
**Current status:** Partially implemented as CSTP JSON-RPC

The highest-level protocol. Decisions, guardrails, and reasoning are expressed in natural language with structured metadata. Fully auditable by humans.

**Use cases:**
- Cross-vendor strategic coordination
- Policy governance and compliance
- Human-in-the-loop decision review
- Audit trails

**Format:** JSON-RPC with natural language fields (what we have today)

```json
{
  "decision": "Adopt HSM architecture for long-context processing",
  "confidence": 0.85,
  "reasons": [{"type": "analysis", "text": "MIT research shows 81% improvement"}],
  "bridge": {
    "structure": "Architecture pattern selection",
    "function": "Optimize long-context inference performance"
  }
}
```

### CSTP - Compressed State Transfer Protocol
**Layer:** Compressed (bandwidth-efficient)

Decisions and context compressed into abstract feature representations. Reduces payload by 10-50x while preserving semantic meaning. Useful for edge deployments, high-frequency decision streams, and WAN communication.

**Use cases:**
- Edge agents with limited bandwidth
- High-frequency trading/monitoring decisions
- WAN federation between distant agents
- Mobile/IoT agent decision sync

**Format:** Compressed feature vectors + minimal metadata

```json
{
  "id": "dec_abc",
  "embedding": [0.12, -0.45, ...],
  "confidence": 0.85,
  "category_idx": 3,
  "outcome_idx": 1,
  "timestamp": 1707681600
}
```

### LSTP - Latent State Transfer Protocol
**Layer:** Latent (highest fidelity)

Raw latent representations for maximum inference continuity. One agent's internal state can be directly loaded by another agent with compatible architecture. Closest to "transferring a mind state."

**Use cases:**
- Local cluster agents with shared model architecture
- High-fidelity reasoning continuity (no information loss)
- Agent cloning / forking
- Research and experimentation

**Format:** Serialized tensor state + model metadata

```json
{
  "id": "state_abc",
  "model": "gemini-3-pro",
  "format": "safetensors",
  "layers": ["reasoning_head", "decision_context"],
  "compatible_models": ["gemini-3-pro", "gemini-3-flash"],
  "data": "<base64 tensor data>"
}
```

## Protocol Selection

| Factor | SSTP | CSTP | LSTP |
|--------|------|------|------|
| Human auditability | Full | Partial | None |
| Bandwidth | High | Low | Very High |
| Fidelity | Good | Moderate | Perfect |
| Cross-vendor | Yes | Yes | No (model-dependent) |
| Latency | Medium | Low | High (transfer) / Low (resume) |

### Auto-Selection Logic
```json
{
  "method": "cstp.negotiateProtocol",
  "params": {
    "peer": "cstp://peer.example.com",
    "constraints": {
      "auditRequired": true,
      "maxBandwidthKbps": 100,
      "modelCompatible": false
    }
  }
}
```

## Implementation Priority
1. **SSTP** - Already partially implemented as current CSTP JSON-RPC. Formalize the spec.
2. **CSTP (compressed)** - Add embedding-only query mode and compressed bundle format.
3. **LSTP** - Research phase. Requires compatible model architectures.

## API

### `cstp.negotiateProtocol`
Auto-negotiate the best protocol layer for a given peer connection.

### `cstp.exportCompressed`
Export decisions in CSTP compressed format.

### `cstp.importCompressed`
Import compressed decision bundles.

## Integration
- F035 State Transfer: Bundles can be serialized at any protocol layer
- F038 Federation: Protocol negotiation between federated peers
- F036 Reasoning Continuity: LSTP enables highest-fidelity thread resumption

## Acceptance Criteria
- [ ] SSTP formalized (current JSON-RPC spec documented as SSTP)
- [ ] CSTP compressed format defined
- [ ] `cstp.negotiateProtocol` RPC method
- [ ] `cstp.exportCompressed` / `cstp.importCompressed`
- [ ] Embedding-only query mode for CSTP layer
- [ ] LSTP research document with feasibility analysis
- [ ] Protocol selection matrix in documentation
- [ ] MCP tools for protocol operations
