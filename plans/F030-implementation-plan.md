# F030: Circuit Breaker Guardrails — Implementation Plan

> Synthesized from 4-agent debate: state-machine-purist, guardrail-integrator, edge-case-hunter, api-pragmatist
> Decision IDs: f1bfd80f, 75f39586, 7fb9f395, c46ef182 → synthesis: 92debe89

## Architecture Overview

```
Agent → pre_action/checkGuardrails → CircuitBreakerManager.check(context)
                                          ↓
                                   BreakerState enum (CLOSED/OPEN/HALF_OPEN)
                                          ↓
                              Sliding window failure tracking
                                          ↓
                              JSONL persistence (crash recovery)

Agent → reviewDecision(outcome:failure) → CircuitBreakerManager.record_outcome()
                                          ↓
                              Increment counters for ALL matching scopes
                                          ↓
                              Trip breaker if threshold exceeded
```

## Consensus Decisions (all 4 agents agreed)

| Topic | Decision | Rationale |
|-------|----------|-----------|
| State representation | `BreakerState` enum: CLOSED, OPEN, HALF_OPEN | Type safety, no string typos |
| Concurrency | `asyncio.Lock` per manager (not per breaker) | Single-process asyncio, matches graph store |
| Failure window | Sliding window (deque of monotonic timestamps) | No boundary effects like fixed windows |
| Cooldown | Lazy evaluation on next check | No background polling, no timer management |
| Persistence | Hybrid: in-memory authoritative + JSONL for recovery | Prevents restart-bypass attack |
| Integration | Transparent via existing checkGuardrails/pre_action | Zero new agent workflows needed |
| Core boundary | All breaker logic in `a2a/cstp/` — core untouched | Respects src/cognition_engines/ import constraint |

## Resolved Tensions

| Tension | Agent A | Agent B | Resolution |
|---------|---------|---------|------------|
| Config location | guardrail-integrator: `guardrails/circuit_breakers.yaml` | api-pragmatist: `server.yaml` | **`guardrails/circuit_breakers.yaml`** — co-located, separate schema |
| Manual reset path | state-machine-purist: OPEN→CLOSED direct | spec: through HALF_OPEN | **OPEN→CLOSED direct** (operator override) + optional `probe_first=true` for OPEN→HALF_OPEN |
| MCP exposure | api-pragmatist: no MCP tools | spec: full MCP exposure | **Read-only `get_circuit_state`** MCP tool only. No reset via MCP — human/admin-only |
| Failure semantics | edge-case-hunter: ambiguous | spec: only `outcome:failure` | **failure + abandoned** increment. **partial** does NOT (it's a qualified success) |
| Success handling | state-machine-purist: full reset | spec: ambiguous "decrement or reset" | **Full reset** — clear failure deque entirely on success in CLOSED state |

## Edge Cases Addressed (from edge-case-hunter's 14 findings)

1. **Restart bypass** → JSONL persistence, replay on startup
2. **Overlapping scopes** → Most-restrictive-wins (any OPEN → block)
3. **Scope failure counting** → Failures increment ALL matching scope counters
4. **Half-open thundering herd** → `probe_in_flight` atomic flag under asyncio.Lock
5. **Notification storm** → Debounce: min 60s between alerts per scope
6. **Memory growth** → Evict stale dynamic scopes (CLOSED + 0 failures > 24hr, not in config)
7. **Clock skew** → `time.monotonic()` for runtime, ISO for JSONL recovery
8. **TOCTOU gap** → Accepted: check and review are inherently separate operations
9. **Manual reset during probe** → Reset clears `probe_in_flight` flag, transitions CLOSED
10. **Cold start** → All breakers start CLOSED, counter starts at 0 — correct behavior

## State Machine

```
                    failure_count >= threshold
    CLOSED ──────────────────────────────────────→ OPEN
      ↑                                             |
      │ probe succeeds                              │ cooldown expires (lazy)
      │                                             ↓
      └─────────────── HALF_OPEN ←──────────────────┘
                          │
                          │ probe fails
                          ↓
                        OPEN

    Manual reset: OPEN → CLOSED (direct, operator override)
    Manual reset (cautious): OPEN → HALF_OPEN (probe_first=true)
```

### Transition Table

| From | To | Trigger |
|------|----|---------|
| CLOSED | OPEN | failure_count >= threshold within window |
| OPEN | HALF_OPEN | cooldown elapsed (checked lazily on next request) |
| HALF_OPEN | CLOSED | probe decision succeeds |
| HALF_OPEN | OPEN | probe decision fails |
| OPEN | CLOSED | manual reset (force=true, default) |
| OPEN | HALF_OPEN | manual reset (probe_first=true) |

### Invariants (checked post-mutation)

1. CLOSED → `opened_at` is None
2. OPEN → `opened_at` is not None
3. HALF_OPEN → `opened_at` is not None
4. `probe_in_flight` can only be True when state is HALF_OPEN
5. Failure deque only contains timestamps within window
6. `len(failures)` <= threshold

## File Changes

### New Files

| File | Purpose |
|------|---------|
| `a2a/cstp/circuit_breaker_service.py` | BreakerState enum, CircuitBreaker dataclass, CircuitBreakerManager singleton |
| `guardrails/circuit_breakers.yaml` | Default config (ships with one stakes:high breaker) |
| `tests/test_f030_circuit_breaker.py` | Comprehensive test suite |

### Modified Files

| File | Changes |
|------|---------|
| `a2a/cstp/models.py` | Extend `GuardrailViolation` with optional `type`, `state`, `failure_rate`, `recent_failures`, `reset_at` fields. Add `GetCircuitStateRequest/Response`, `ResetCircuitRequest/Response` |
| `a2a/cstp/dispatcher.py` | Add `_handle_get_circuit_state`, `_handle_reset_circuit`. Hook `circuit_breaker_service.record_outcome()` into `_handle_review_decision`. Merge breaker results into `_handle_check_guardrails` |
| `a2a/cstp/guardrails_service.py` | Import and call `CircuitBreakerManager.check()` in `evaluate_guardrails()` |
| `a2a/cstp/session_context_service.py` | Add `circuitBreakers` section showing non-CLOSED breakers |
| `a2a/mcp_server.py` | Add read-only `get_circuit_state` tool (Phase 3) |
| `dashboard/app.py` | Add `/breakers` route with state table, reset button (Phase 4) |

### Untouched (by design)

- `src/cognition_engines/` — entire core layer untouched (respects import constraint)

## Data Model

```python
class BreakerState(enum.Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

@dataclass
class CircuitBreakerConfig:
    scope: str                    # "category:tooling", "stakes:high", "global"
    failure_threshold: int = 5
    window_ms: int = 3_600_000    # 1 hour
    cooldown_ms: int = 1_800_000  # 30 minutes
    notify: bool = True

@dataclass
class CircuitBreaker:
    config: CircuitBreakerConfig
    state: BreakerState = BreakerState.CLOSED
    failures: deque[float] = field(default_factory=deque)  # monotonic timestamps
    opened_at: float | None = None
    probe_in_flight: bool = False
    last_notification: float | None = None  # debounce tracking
```

## Scope Matching Algorithm

```python
def matches_scope(scope: str, context: dict) -> bool:
    if scope == "global":
        return True
    dimension, value = scope.split(":", 1)
    if dimension == "category":
        return context.get("category") == value
    elif dimension == "stakes":
        return context.get("stakes") == value
    elif dimension == "agent":
        return context.get("agent_id") == value
    elif dimension == "tag":
        return value in context.get("tags", [])
    return False
```

## Configuration (default ships with project)

```yaml
# guardrails/circuit_breakers.yaml
circuit_breakers:
  - scope: "stakes:high"
    failure_threshold: 3
    window_ms: 86400000      # 24 hours
    cooldown_ms: 3600000     # 1 hour
    notify: true
```

## Phased Delivery

### Phase 1: Core State Machine + Guardrail Integration
- `CircuitBreakerManager` with state machine, sliding window, JSONL persistence
- Hook into `evaluate_guardrails()` → breaker violations appear in `checkGuardrails` response
- Hook into `_handle_review_decision` → failures/successes update counters
- Default config file
- Full test suite

### Phase 2: RPC Methods
- `cstp.getCircuitState` — query breaker state by scope
- `cstp.resetCircuit` — manual reset (admin-only)
- `cstp.listBreakers` — list all breakers with current state (or extend `listGuardrails`)

### Phase 3: MCP + Session Context
- Read-only `get_circuit_state` MCP tool
- `get_session_context` includes non-CLOSED breaker summary
- Markdown format: `### Circuit Breakers\n- [OPEN] stakes:high — 3/3 failures, resets in 45m`

### Phase 4: Dashboard
- `/breakers` page with HTMX polling
- Color-coded state table (green/red/yellow)
- Failure count vs threshold progress bar
- Reset button with confirmation (admin-only)
- Recent failures linked to decision detail pages

## Test Plan

| Category | Tests |
|----------|-------|
| State machine | All legal transitions, illegal transition rejection, invariant checking |
| Sliding window | Window expiry, boundary timestamps, empty window |
| Persistence | JSONL write/read, crash recovery, corrupt file handling |
| Concurrency | Concurrent check + record_outcome, probe race condition |
| Scope matching | All 5 scope types, overlapping scopes, most-restrictive-wins |
| Integration | checkGuardrails returns breaker violations, pre_action blocks on OPEN |
| Edge cases | Restart recovery, manual reset during probe, cold start, stale eviction |
| Config | YAML loading, missing file defaults, invalid config |
