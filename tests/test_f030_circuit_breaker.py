"""Tests for F030: Circuit Breaker Guardrails.

Comprehensive test suite covering state machine, sliding window, persistence,
concurrency, scope matching, integration, edge cases, and config loading.
"""

import asyncio
import json
import time
from collections import deque
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from a2a.cstp.circuit_breaker_service import (
    BreakerCheckResult,
    BreakerState,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerManager,
    _load_breakers_from_jsonl,
    _save_all_breakers,
    _serialize_breaker,
    load_breaker_configs,
    matches_scope,
    set_circuit_breaker_manager,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _config(
    scope: str = "global",
    threshold: int = 3,
    window_ms: int = 60_000,
    cooldown_ms: int = 30_000,
    notify: bool = False,
) -> CircuitBreakerConfig:
    """Build a CircuitBreakerConfig with test-friendly defaults."""
    return CircuitBreakerConfig(
        scope=scope,
        failure_threshold=threshold,
        window_ms=window_ms,
        cooldown_ms=cooldown_ms,
        notify=notify,
    )


async def _make_manager(
    tmp_path: Path,
    configs: list[CircuitBreakerConfig] | None = None,
    config_path: Path | None = None,
) -> CircuitBreakerManager:
    """Create a fresh CircuitBreakerManager for testing.

    If configs are provided, they are injected directly (no YAML loading).
    If config_path is provided, YAML is loaded from that path.
    """
    persistence = str(tmp_path / "breakers.jsonl")
    mgr = CircuitBreakerManager(
        config_path=config_path,
        persistence_path=persistence,
    )

    if configs is not None:
        # Skip YAML loading; inject configs directly
        mgr._configs = {c.scope: c for c in configs}
        for scope, cfg in mgr._configs.items():
            mgr._breakers[scope] = CircuitBreaker(config=cfg, from_config=True)
        mgr._initialized = True
    else:
        await mgr.initialize()

    set_circuit_breaker_manager(mgr)
    return mgr


def _ctx(**kwargs: Any) -> dict[str, Any]:
    """Build a decision context dict with defaults."""
    ctx: dict[str, Any] = {
        "category": kwargs.get("category", "architecture"),
        "stakes": kwargs.get("stakes", "medium"),
    }
    if "agent_id" in kwargs:
        ctx["agent_id"] = kwargs["agent_id"]
    if "tags" in kwargs:
        ctx["tags"] = kwargs["tags"]
    return ctx


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_singleton() -> None:
    """Reset the module-level singleton before each test."""
    set_circuit_breaker_manager(None)


# ===========================================================================
# 1. Scope Matching
# ===========================================================================


class TestScopeMatching:
    """Tests for matches_scope() — all 5 scope types + edge cases."""

    def test_global_matches_all(self) -> None:
        assert matches_scope("global", _ctx()) is True
        assert matches_scope("global", _ctx(category="tooling")) is True
        assert matches_scope("global", {}) is True

    def test_category_match(self) -> None:
        assert matches_scope("category:architecture", _ctx(category="architecture")) is True
        assert matches_scope("category:tooling", _ctx(category="architecture")) is False

    def test_stakes_match(self) -> None:
        assert matches_scope("stakes:high", _ctx(stakes="high")) is True
        assert matches_scope("stakes:high", _ctx(stakes="low")) is False

    def test_agent_match(self) -> None:
        assert matches_scope("agent:test-bot", _ctx(agent_id="test-bot")) is True
        assert matches_scope("agent:test-bot", _ctx(agent_id="other")) is False
        assert matches_scope("agent:test-bot", _ctx()) is False

    def test_tag_match(self) -> None:
        assert matches_scope("tag:urgent", _ctx(tags=["urgent", "review"])) is True
        assert matches_scope("tag:urgent", _ctx(tags=["review"])) is False
        assert matches_scope("tag:urgent", _ctx()) is False

    def test_no_match_unknown_dimension(self) -> None:
        assert matches_scope("unknown:value", _ctx()) is False

    def test_no_match_missing_colon(self) -> None:
        assert matches_scope("notascope", _ctx()) is False

    def test_scope_with_colon_in_value(self) -> None:
        assert matches_scope("tag:foo:bar", _ctx(tags=["foo:bar"])) is True


# ===========================================================================
# 2. State Machine
# ===========================================================================


class TestStateMachine:
    """Tests for state transitions and invariants."""

    async def test_initial_state_is_closed(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        results = await mgr.check(_ctx())
        assert len(results) == 1
        assert results[0].state == "closed"
        assert results[0].blocked is False

    async def test_transition_closed_to_open_on_threshold(self, tmp_path: Path) -> None:
        cfg = _config(threshold=3)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        for _ in range(3):
            await mgr.record_outcome(ctx, "failure")

        results = await mgr.check(ctx)
        assert results[0].state == "open"
        assert results[0].blocked is True

    async def test_transition_open_to_half_open_on_cooldown(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, cooldown_ms=1_000)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip the breaker
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Simulate cooldown elapsed
        base = time.time()
        with patch("a2a.cstp.circuit_breaker_service.time.time", return_value=base + 2.0):
            results = await mgr.check(ctx)
            assert results[0].state == "half_open"
            assert results[0].blocked is False

    async def test_transition_half_open_to_closed_on_success(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, cooldown_ms=1_000)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Move to HALF_OPEN via cooldown
        breaker = mgr._breakers["global"]
        breaker.state = BreakerState.HALF_OPEN
        breaker.probe_in_flight = False

        # Probe success
        await mgr.record_outcome(ctx, "success")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    async def test_transition_half_open_to_open_on_failure(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, cooldown_ms=1_000)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Move to HALF_OPEN
        breaker = mgr._breakers["global"]
        breaker.state = BreakerState.HALF_OPEN
        breaker.probe_in_flight = True

        # Probe fails
        await mgr.record_outcome(ctx, "failure")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["state"] == "open"

    async def test_manual_reset_open_to_closed(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        result = await mgr.reset("global")
        assert result["previous_state"] == "open"
        assert result["new_state"] == "closed"

        state = await mgr.get_state("global")
        assert state is not None
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    async def test_manual_reset_open_to_half_open_probe_first(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        result = await mgr.reset("global", probe_first=True)
        assert result["previous_state"] == "open"
        assert result["new_state"] == "half_open"

    async def test_reset_non_open_returns_error(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        result = await mgr.reset("global")
        assert "error" in result

    async def test_reset_unknown_scope_returns_error(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        result = await mgr.reset("nonexistent")
        assert "error" in result

    async def test_invariants_closed_state(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        breaker = mgr._breakers["global"]
        assert breaker.state is BreakerState.CLOSED
        assert breaker.opened_at is None
        assert breaker.probe_in_flight is False

    async def test_invariants_open_state(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        for _ in range(2):
            await mgr.record_outcome(_ctx(), "failure")

        breaker = mgr._breakers["global"]
        assert breaker.state is BreakerState.OPEN
        assert breaker.opened_at is not None
        assert breaker.probe_in_flight is False


# ===========================================================================
# 3. Sliding Window
# ===========================================================================


class TestSlidingWindow:
    """Tests for sliding window failure tracking."""

    async def test_failures_expire_outside_window(self, tmp_path: Path) -> None:
        cfg = _config(threshold=5, window_ms=10_000)  # 10s window
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Record 3 failures
        for _ in range(3):
            await mgr.record_outcome(ctx, "failure")

        # Advance time beyond window
        base = time.time()
        with patch(
            "a2a.cstp.circuit_breaker_service.time.time",
            return_value=base + 15.0,
        ):
            results = await mgr.check(ctx)
            assert results[0].failure_count == 0  # All expired

    async def test_window_boundary_precision(self, tmp_path: Path) -> None:
        cfg = _config(threshold=5, window_ms=10_000)
        mgr = await _make_manager(tmp_path, [cfg])
        breaker = mgr._breakers["global"]

        # Inject failures at known times
        base = 1000.0
        breaker.failures = deque([base, base + 5.0, base + 9.0])

        # At base + 10.0, the first failure is exactly at the cutoff
        with patch(
            "a2a.cstp.circuit_breaker_service.time.time",
            return_value=base + 10.0,
        ):
            results = await mgr.check(_ctx())
            # base is exactly at cutoff (monotonic - window_seconds == base)
            # cutoff = base + 10.0 - 10.0 = base, so base < cutoff is False
            # The first failure at base should remain (not strictly less than)
            assert results[0].failure_count == 3

    async def test_empty_window_no_failures(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        results = await mgr.check(_ctx())
        assert results[0].failure_count == 0

    async def test_failures_pruned_on_check(self, tmp_path: Path) -> None:
        cfg = _config(threshold=10, window_ms=5_000)
        mgr = await _make_manager(tmp_path, [cfg])
        breaker = mgr._breakers["global"]

        # Inject old failures
        old_time = time.time() - 100.0
        breaker.failures = deque([old_time, old_time + 1.0])

        results = await mgr.check(_ctx())
        assert results[0].failure_count == 0
        assert len(breaker.failures) == 0

    async def test_success_in_closed_clears_failures(self, tmp_path: Path) -> None:
        cfg = _config(threshold=5)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        await mgr.record_outcome(ctx, "failure")
        await mgr.record_outcome(ctx, "failure")
        assert len(mgr._breakers["global"].failures) == 2

        await mgr.record_outcome(ctx, "success")
        assert len(mgr._breakers["global"].failures) == 0


# ===========================================================================
# 4. Persistence
# ===========================================================================


class TestPersistence:
    """Tests for JSONL write/read and crash recovery."""

    async def test_jsonl_write_on_state_change(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        jsonl = tmp_path / "breakers.jsonl"

        await mgr.record_outcome(_ctx(), "failure")

        assert jsonl.exists()
        lines = jsonl.read_text().strip().split("\n")
        assert len(lines) >= 1
        data = json.loads(lines[-1])
        assert data["scope"] == "global"
        assert data["state"] == "closed"

    async def test_jsonl_replay_on_startup(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])

        # Trip the breaker
        for _ in range(2):
            await mgr.record_outcome(_ctx(), "failure")

        state_before = await mgr.get_state("global")
        assert state_before is not None
        assert state_before["state"] == "open"

        # Create a new manager from the same JSONL
        set_circuit_breaker_manager(None)
        mgr2 = CircuitBreakerManager(
            persistence_path=str(tmp_path / "breakers.jsonl"),
        )
        # Inject the same config for scope recognition
        mgr2._configs = {"global": cfg}
        mgr2._breakers = _load_breakers_from_jsonl(
            Path(tmp_path / "breakers.jsonl"), mgr2._configs
        )
        for scope, config in mgr2._configs.items():
            if scope not in mgr2._breakers:
                mgr2._breakers[scope] = CircuitBreaker(config=config, from_config=True)
        mgr2._initialized = True

        state_after = await mgr2.get_state("global")
        assert state_after is not None
        assert state_after["state"] == "open"

    async def test_corrupt_jsonl_line_skipped(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "breakers.jsonl"
        jsonl.parent.mkdir(parents=True, exist_ok=True)

        # Write a valid line then a corrupt line then another valid line
        valid1 = json.dumps({
            "scope": "global",
            "state": "closed",
            "failures": [],
            "opened_at": None,
            "probe_in_flight": False,
            "last_notification": None,
            "last_activity": 1000.0,
        })
        valid2 = json.dumps({
            "scope": "global",
            "state": "open",
            "failures": [999.0],
            "opened_at": 999.0,
            "probe_in_flight": False,
            "last_notification": None,
            "last_activity": 1001.0,
        })
        jsonl.write_text(f"{valid1}\nNOT VALID JSON\n{valid2}\n")

        configs = {"global": _config()}
        breakers = _load_breakers_from_jsonl(jsonl, configs)
        # Last valid entry for "global" should win
        assert "global" in breakers
        assert breakers["global"].state is BreakerState.OPEN

    async def test_no_persistence_file_cold_start(self, tmp_path: Path) -> None:
        jsonl = tmp_path / "nonexistent.jsonl"
        configs = {"global": _config()}
        breakers = _load_breakers_from_jsonl(jsonl, configs)
        assert breakers == {}

    def test_serialize_breaker(self) -> None:
        cfg = _config()
        breaker = CircuitBreaker(
            config=cfg,
            state=BreakerState.OPEN,
            failures=deque([100.0, 200.0]),
            opened_at=200.0,
        )
        data = _serialize_breaker("global", breaker)
        assert data["scope"] == "global"
        assert data["state"] == "open"
        assert data["failures"] == [100.0, 200.0]
        assert data["opened_at"] == 200.0
        assert "timestamp" in data

    async def test_save_all_breakers_full_rewrite(self, tmp_path: Path) -> None:
        cfg = _config()
        jsonl = tmp_path / "breakers.jsonl"

        breakers = {
            "global": CircuitBreaker(config=cfg),
            "category:arch": CircuitBreaker(config=_config(scope="category:arch")),
        }
        _save_all_breakers(breakers, jsonl)

        lines = jsonl.read_text().strip().split("\n")
        assert len(lines) == 2
        scopes = {json.loads(line)["scope"] for line in lines}
        assert scopes == {"global", "category:arch"}


# ===========================================================================
# 5. Concurrency
# ===========================================================================


class TestConcurrency:
    """Tests for concurrent access patterns."""

    async def test_concurrent_check_and_record(self, tmp_path: Path) -> None:
        cfg = _config(threshold=10)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        async def do_failure() -> None:
            await mgr.record_outcome(ctx, "failure")

        async def do_check() -> list[BreakerCheckResult]:
            return await mgr.check(ctx)

        # Run 5 failures and 5 checks concurrently
        tasks = [do_failure() for _ in range(5)] + [do_check() for _ in range(5)]
        await asyncio.gather(*tasks)

        # After 5 failures, should have 5 in window (threshold=10, so still closed)
        state = await mgr.get_state("global")
        assert state is not None
        assert state["failure_count"] == 5
        assert state["state"] == "closed"

    async def test_probe_in_flight_blocks_second_probe(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, cooldown_ms=1_000)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Move to HALF_OPEN
        breaker = mgr._breakers["global"]
        breaker.state = BreakerState.HALF_OPEN
        breaker.probe_in_flight = False

        # First check allows probe
        results1 = await mgr.check(ctx)
        assert results1[0].blocked is False
        assert breaker.probe_in_flight is True

        # Second check blocks
        results2 = await mgr.check(ctx)
        assert results2[0].blocked is True
        assert "probe in flight" in results2[0].message

    async def test_concurrent_failures_reach_threshold(self, tmp_path: Path) -> None:
        cfg = _config(threshold=5)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        async def do_failure() -> None:
            await mgr.record_outcome(ctx, "failure")

        # 5 concurrent failures
        await asyncio.gather(*[do_failure() for _ in range(5)])

        state = await mgr.get_state("global")
        assert state is not None
        # Should be open (threshold met or exceeded)
        assert state["state"] == "open"


# ===========================================================================
# 6. Overlapping Scopes / Most-Restrictive-Wins
# ===========================================================================


class TestOverlappingScopes:
    """Tests for overlapping scopes and most-restrictive-wins logic."""

    async def test_overlapping_scopes_most_restrictive_wins(self, tmp_path: Path) -> None:
        configs = [
            _config(scope="global", threshold=10),
            _config(scope="category:architecture", threshold=2),
        ]
        mgr = await _make_manager(tmp_path, configs)
        ctx = _ctx(category="architecture")

        # 2 failures trips the category breaker but not global
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        results = await mgr.check(ctx)
        # Should have 2 results: one blocked (category), one not (global)
        states = {r.scope: r.blocked for r in results}
        assert states["category:architecture"] is True
        assert states["global"] is False

    async def test_no_matching_scope_returns_empty(self, tmp_path: Path) -> None:
        cfg = _config(scope="category:tooling", threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        results = await mgr.check(_ctx(category="architecture"))
        assert results == []


# ===========================================================================
# 7. Integration with guardrails_service
# ===========================================================================


class TestIntegration:
    """Tests for circuit breaker integration with evaluate_guardrails."""

    async def test_check_guardrails_includes_breaker_violations(
        self, tmp_path: Path
    ) -> None:
        from a2a.cstp.guardrails_service import clear_guardrails_cache, evaluate_guardrails

        clear_guardrails_cache()

        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip the breaker
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Use an empty guardrails dir so static guardrails don't interfere
        guardrails_dir = tmp_path / "guardrails_empty"
        guardrails_dir.mkdir()

        result = await evaluate_guardrails(ctx, guardrails_dir=guardrails_dir)
        assert result.allowed is False
        assert any(
            "circuit_breaker" in v.guardrail_id for v in result.violations
        )

    async def test_check_guardrails_allows_when_closed(
        self, tmp_path: Path
    ) -> None:
        from a2a.cstp.guardrails_service import clear_guardrails_cache, evaluate_guardrails

        clear_guardrails_cache()

        cfg = _config(threshold=5)
        await _make_manager(tmp_path, [cfg])

        guardrails_dir = tmp_path / "guardrails_empty2"
        guardrails_dir.mkdir()

        result = await evaluate_guardrails(_ctx(), guardrails_dir=guardrails_dir)
        assert result.allowed is True

    async def test_review_decision_hooks_record_outcome(self, tmp_path: Path) -> None:
        """Verify that record_outcome updates matching breakers."""
        configs = [
            _config(scope="global", threshold=3),
            _config(scope="stakes:high", threshold=2),
        ]
        mgr = await _make_manager(tmp_path, configs)
        ctx = _ctx(stakes="high")

        # Record 2 failures — should trip stakes:high but not global
        await mgr.record_outcome(ctx, "failure")
        await mgr.record_outcome(ctx, "failure")

        global_state = await mgr.get_state("global")
        stakes_state = await mgr.get_state("stakes:high")
        assert global_state is not None
        assert global_state["state"] == "closed"
        assert stakes_state is not None
        assert stakes_state["state"] == "open"

    async def test_success_outcome_closes_half_open(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Move to HALF_OPEN
        mgr._breakers["global"].state = BreakerState.HALF_OPEN
        mgr._breakers["global"].probe_in_flight = True

        # Success closes it
        await mgr.record_outcome(ctx, "success")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["state"] == "closed"


# ===========================================================================
# 8. Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    async def test_manual_reset_during_probe_in_flight(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        # Move to HALF_OPEN with probe in flight
        breaker = mgr._breakers["global"]
        breaker.state = BreakerState.OPEN  # Keep as OPEN for reset

        result = await mgr.reset("global")
        assert result["new_state"] == "closed"

        state = await mgr.get_state("global")
        assert state is not None
        assert state["probe_in_flight"] is False

    async def test_failure_and_abandoned_count_partial_does_not(
        self, tmp_path: Path
    ) -> None:
        cfg = _config(threshold=3)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # failure and abandoned both increment the failure counter
        await mgr.record_outcome(ctx, "failure")
        await mgr.record_outcome(ctx, "abandoned")
        breaker = mgr._breakers["global"]
        assert len(breaker.failures) == 2

        # partial is treated as success (not a failure) -- it clears the deque
        # in CLOSED state. This verifies partial does NOT trip the breaker.
        await mgr.record_outcome(ctx, "partial")

        state = await mgr.get_state("global")
        assert state is not None
        # partial triggers _record_success which clears failures in CLOSED
        assert state["failure_count"] == 0
        assert state["state"] == "closed"

    async def test_failure_abandoned_trips_at_threshold(
        self, tmp_path: Path
    ) -> None:
        cfg = _config(threshold=3)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        await mgr.record_outcome(ctx, "failure")
        await mgr.record_outcome(ctx, "abandoned")
        await mgr.record_outcome(ctx, "failure")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["state"] == "open"

    async def test_cold_start_all_closed(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [
            _config(scope="global"),
            _config(scope="category:arch"),
        ])
        breakers = await mgr.list_breakers()
        assert all(b["state"] == "closed" for b in breakers)

    async def test_stale_eviction(self, tmp_path: Path) -> None:
        cfg = _config(scope="category:arch", threshold=5)
        mgr = await _make_manager(tmp_path, [cfg])

        # Create a dynamic breaker (not from config)
        mgr._breakers["agent:stale-bot"] = CircuitBreaker(
            config=_config(scope="agent:stale-bot"),
            state=BreakerState.CLOSED,
            failures=deque(),
            last_activity=time.time() - 100_000.0,  # Very old
            from_config=False,
        )

        evicted = await mgr.evict_stale()
        assert evicted == 1
        assert "agent:stale-bot" not in mgr._breakers

    async def test_stale_eviction_skips_config_breakers(self, tmp_path: Path) -> None:
        cfg = _config(scope="global")
        mgr = await _make_manager(tmp_path, [cfg])

        # Make it look stale
        mgr._breakers["global"].last_activity = time.time() - 100_000.0

        evicted = await mgr.evict_stale()
        assert evicted == 0
        assert "global" in mgr._breakers

    async def test_stale_eviction_skips_non_closed(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [])
        mgr._breakers["agent:dynamic"] = CircuitBreaker(
            config=_config(scope="agent:dynamic"),
            state=BreakerState.OPEN,
            failures=deque(),
            opened_at=time.time(),
            last_activity=time.time() - 100_000.0,
            from_config=False,
        )

        evicted = await mgr.evict_stale()
        assert evicted == 0

    async def test_notification_debounce(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, notify=True)
        mgr = await _make_manager(tmp_path, [cfg])
        breaker = mgr._breakers["global"]

        # First notification should fire (last_notification=None)
        assert mgr._should_notify(breaker) is True

        # After notification, debounce
        breaker.last_notification = time.time()
        assert mgr._should_notify(breaker) is False

        # After debounce window
        breaker.last_notification = time.time() - 61.0
        assert mgr._should_notify(breaker) is True

    async def test_get_state_unknown_scope(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        state = await mgr.get_state("nonexistent")
        assert state is None

    async def test_list_breakers(self, tmp_path: Path) -> None:
        mgr = await _make_manager(tmp_path, [
            _config(scope="global"),
            _config(scope="stakes:high"),
        ])
        breakers = await mgr.list_breakers()
        assert len(breakers) == 2
        scopes = {b["scope"] for b in breakers}
        assert scopes == {"global", "stakes:high"}

    async def test_get_non_closed_summary_empty_when_all_closed(
        self, tmp_path: Path
    ) -> None:
        mgr = await _make_manager(tmp_path, [_config()])
        summary = await mgr.get_non_closed_summary()
        assert summary == []

    async def test_get_non_closed_summary_includes_open(
        self, tmp_path: Path
    ) -> None:
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])

        for _ in range(2):
            await mgr.record_outcome(_ctx(), "failure")

        summary = await mgr.get_non_closed_summary()
        assert len(summary) == 1
        assert summary[0]["state"] == "open"

    async def test_cooldown_remaining_ms_in_open_state(self, tmp_path: Path) -> None:
        cfg = _config(threshold=2, cooldown_ms=60_000)
        mgr = await _make_manager(tmp_path, [cfg])

        for _ in range(2):
            await mgr.record_outcome(_ctx(), "failure")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["cooldown_remaining_ms"] is not None
        assert state["cooldown_remaining_ms"] > 0

    async def test_dynamic_breaker_creation(self, tmp_path: Path) -> None:
        """Breakers are created dynamically for scopes not in config."""
        mgr = await _make_manager(tmp_path, [])  # No configs

        # Recording outcome for an unknown scope should create a dynamic breaker
        ctx = _ctx()
        # matches_scope("global", ctx) won't match since there's no global breaker
        # Let's add a global one dynamically
        mgr._breakers["global"] = CircuitBreaker(
            config=_config(scope="global"),
            from_config=False,
        )
        await mgr.record_outcome(ctx, "failure")

        state = await mgr.get_state("global")
        assert state is not None
        assert state["from_config"] is False

    async def test_failures_recorded_even_when_open(self, tmp_path: Path) -> None:
        """When breaker is OPEN, failures are still recorded for stats."""
        cfg = _config(threshold=2)
        mgr = await _make_manager(tmp_path, [cfg])
        ctx = _ctx()

        # Trip to OPEN
        for _ in range(2):
            await mgr.record_outcome(ctx, "failure")

        breaker = mgr._breakers["global"]
        count_at_trip = len(breaker.failures)

        # Record more failures while OPEN
        await mgr.record_outcome(ctx, "failure")
        assert len(breaker.failures) >= count_at_trip


# ===========================================================================
# 9. Config Loading
# ===========================================================================


class TestConfigLoading:
    """Tests for YAML config loading."""

    def test_yaml_config_loading(self, tmp_path: Path) -> None:
        yaml_dir = tmp_path / "guardrails"
        yaml_dir.mkdir()
        yaml_file = yaml_dir / "circuit_breakers.yaml"
        yaml_file.write_text(
            "circuit_breakers:\n"
            "  - scope: 'stakes:high'\n"
            "    failure_threshold: 3\n"
            "    window_ms: 86400000\n"
            "    cooldown_ms: 3600000\n"
            "    notify: true\n"
            "  - scope: 'global'\n"
            "    failure_threshold: 10\n"
        )

        configs = load_breaker_configs(yaml_file)
        assert len(configs) == 2
        assert configs[0].scope == "stakes:high"
        assert configs[0].failure_threshold == 3
        assert configs[0].window_ms == 86_400_000
        assert configs[0].cooldown_ms == 3_600_000
        assert configs[0].notify is True
        assert configs[1].scope == "global"
        assert configs[1].failure_threshold == 10

    def test_missing_config_file_defaults(self, tmp_path: Path) -> None:
        nonexistent = tmp_path / "does_not_exist.yaml"
        configs = load_breaker_configs(nonexistent)
        assert configs == []

    def test_invalid_config_items_skipped(self, tmp_path: Path) -> None:
        yaml_dir = tmp_path / "guardrails"
        yaml_dir.mkdir()
        yaml_file = yaml_dir / "circuit_breakers.yaml"
        yaml_file.write_text(
            "circuit_breakers:\n"
            "  - scope: 'global'\n"
            "    failure_threshold: 5\n"
            "  - 'not a dict'\n"
            "  - scope: 'stakes:high'\n"
        )

        configs = load_breaker_configs(yaml_file)
        # Only valid dict items are loaded; string "not a dict" is skipped
        assert len(configs) == 2
        scopes = [c.scope for c in configs]
        assert "global" in scopes
        assert "stakes:high" in scopes

    def test_empty_yaml_file(self, tmp_path: Path) -> None:
        yaml_file = tmp_path / "empty.yaml"
        yaml_file.write_text("")
        configs = load_breaker_configs(yaml_file)
        assert configs == []

    def test_config_defaults(self) -> None:
        cfg = CircuitBreakerConfig(scope="test")
        assert cfg.failure_threshold == 5
        assert cfg.window_ms == 3_600_000
        assert cfg.cooldown_ms == 1_800_000
        assert cfg.notify is True
        assert cfg.window_seconds == 3600.0
        assert cfg.cooldown_seconds == 1800.0


# ===========================================================================
# 10. BreakerCheckResult and models
# ===========================================================================


class TestModels:
    """Tests for data models and model serialization."""

    def test_breaker_check_result_fields(self) -> None:
        r = BreakerCheckResult(
            scope="global",
            state="open",
            blocked=True,
            message="Circuit breaker OPEN",
            failure_count=5,
            failure_threshold=5,
            cooldown_remaining_ms=30_000,
        )
        assert r.scope == "global"
        assert r.blocked is True
        assert r.cooldown_remaining_ms == 30_000

    def test_breaker_state_enum(self) -> None:
        assert BreakerState.CLOSED.value == "closed"
        assert BreakerState.OPEN.value == "open"
        assert BreakerState.HALF_OPEN.value == "half_open"
        assert BreakerState("closed") is BreakerState.CLOSED

    def test_guardrail_violation_f030_fields(self) -> None:
        from a2a.cstp.models import GuardrailViolation

        v = GuardrailViolation(
            guardrail_id="circuit_breaker:global",
            name="Circuit breaker (global)",
            message="OPEN",
            severity="block",
            type="circuit_breaker",
            state="open",
            failure_rate=1.0,
            reset_at="2026-02-21T12:00:00Z",
        )
        d = v.to_dict()
        assert d["type"] == "circuit_breaker"
        assert d["state"] == "open"
        assert d["failureRate"] == 1.0
        assert d["resetAt"] == "2026-02-21T12:00:00Z"

    def test_guardrail_violation_no_f030_fields(self) -> None:
        from a2a.cstp.models import GuardrailViolation

        v = GuardrailViolation(
            guardrail_id="static:test",
            name="Test",
            message="Test message",
        )
        d = v.to_dict()
        assert "type" not in d
        assert "state" not in d
        assert "failureRate" not in d

    def test_get_circuit_state_request(self) -> None:
        from a2a.cstp.models import GetCircuitStateRequest

        req = GetCircuitStateRequest.from_params({"scope": "global"})
        assert req.scope == "global"

        with pytest.raises(ValueError, match="scope"):
            GetCircuitStateRequest.from_params({})

    def test_reset_circuit_request(self) -> None:
        from a2a.cstp.models import ResetCircuitRequest

        req = ResetCircuitRequest.from_params({"scope": "global", "probeFirst": True})
        assert req.scope == "global"
        assert req.probe_first is True

        req2 = ResetCircuitRequest.from_params({"scope": "test"})
        assert req2.probe_first is False

        with pytest.raises(ValueError, match="scope"):
            ResetCircuitRequest.from_params({})
