# F030: Circuit Breaker Guardrails

## Source
- AutoGPT.net: "How AI Agents Navigate Financial Transactions Autonomously" (Feb 11, 2026)
- ai16z/elizaOS: Trust-scored autonomous trading with kill switches
- Existing CSTP guardrails (block/warn/allow)

## Overview
Evolve guardrails from static rules into dynamic circuit breakers that trip based on real-time failure patterns, automatically escalate, and require explicit reset. Inspired by distributed systems circuit breaker patterns (Hystrix, Resilience4j) applied to agent decision-making.

## Current State
Guardrails today are stateless: each check is independent. A guardrail doesn't know that the last 5 decisions in this category all failed. It can't detect cascading failures or escalate.

## Circuit Breaker States

```
CLOSED (normal) → failures exceed threshold → OPEN (blocked)
    ↑                                            |
    └── manual reset or cooldown ← HALF_OPEN (probe) ←┘
```

| State | Behavior |
|-------|----------|
| `CLOSED` | Normal operation. Decisions flow through. Failures tracked. |
| `OPEN` | All decisions in scope blocked. Agent notified. Human alert sent. |
| `HALF_OPEN` | Single probe decision allowed. Success → CLOSED. Failure → OPEN. |

## API

### New RPC Method: `cstp.getCircuitState`

```json
{
  "method": "cstp.getCircuitState",
  "params": {
    "scope": "category:tooling"
  }
}
```

### Response

```json
{
  "result": {
    "scope": "category:tooling",
    "state": "closed",
    "failureCount": 2,
    "failureThreshold": 5,
    "lastFailure": "2026-02-11T12:00:00Z",
    "windowMs": 3600000,
    "cooldownMs": 1800000
  }
}
```

### Enhanced `cstp.checkGuardrails` Response

```json
{
  "result": {
    "allowed": false,
    "violations": [{
      "guardrail": "category-tooling-breaker",
      "type": "circuit_breaker",
      "state": "open",
      "message": "Circuit breaker OPEN: 5/5 recent tooling decisions failed. Cooldown: 22m remaining.",
      "failureRate": 1.0,
      "recentFailures": ["dec_abc", "dec_def", "dec_ghi"],
      "action": "block",
      "resetAt": "2026-02-11T13:30:00Z"
    }]
  }
}
```

## Configuration

```yaml
circuit_breakers:
  - scope: "category:tooling"
    failure_threshold: 5
    window_ms: 3600000        # 1 hour window
    cooldown_ms: 1800000      # 30 min cooldown before half-open
    notify: true               # Alert human when tripped
    
  - scope: "stakes:high"
    failure_threshold: 3       # Lower threshold for high-stakes
    window_ms: 86400000        # 24 hour window
    cooldown_ms: 3600000       # 1 hour cooldown
    notify: true
    
  - scope: "agent:code-reviewer"
    failure_threshold: 4
    window_ms: 7200000
    cooldown_ms: 900000
```

## Scopes
- `category:<name>` - per decision category
- `stakes:<level>` - per stakes level
- `agent:<id>` - per agent identity
- `tag:<name>` - per decision tag
- `global` - all decisions

## Integration with Existing Guardrails
- Circuit breakers are a new guardrail **type** alongside `block`/`warn`/`allow`
- `cstp.checkGuardrails` automatically checks circuit breaker state
- Failed decisions (via `cstp.reviewDecision` with `outcome: failure`) increment failure counters
- Successful outcomes decrement or reset counters

## Acceptance Criteria
- [ ] Circuit breaker state machine (closed/open/half-open)
- [ ] Configurable per scope (category, stakes, agent, tag)
- [ ] Automatic tripping on failure threshold
- [ ] Cooldown period with half-open probe
- [ ] Integration with `cstp.checkGuardrails`
- [ ] Notification on state change (open/closed)
- [ ] Dashboard view showing breaker states
- [ ] `cstp.resetCircuit` RPC for manual reset
- [ ] MCP tool exposure
