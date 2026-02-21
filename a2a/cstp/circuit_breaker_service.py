"""Circuit breaker service for CSTP guardrail integration.

Implements F030: stateful circuit breakers that trip when repeated failures
exceed a threshold within a sliding window. Integrates transparently with
existing checkGuardrails/pre_action flow.

State machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED (or back to OPEN).
Persistence: hybrid in-memory + JSONL for crash recovery.
Concurrency: asyncio.Lock for all state mutations.
"""

import asyncio
import enum
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_audit_logger = logging.getLogger("cstp.circuit_breaker.audit")

CIRCUIT_BREAKER_DATA_PATH = os.getenv(
    "CIRCUIT_BREAKER_DATA_PATH", "data/circuit_breakers.jsonl"
)

_NOTIFICATION_DEBOUNCE_SECONDS = 60.0
_STALE_EVICTION_SECONDS = 86_400.0  # 24 hours


# ---------------------------------------------------------------------------
# Enums & data models
# ---------------------------------------------------------------------------


class BreakerState(enum.Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# Legal transitions: (from_state, to_state) -> description
_LEGAL_TRANSITIONS: dict[tuple[BreakerState, BreakerState], str] = {
    (BreakerState.CLOSED, BreakerState.OPEN): "threshold_exceeded",
    (BreakerState.OPEN, BreakerState.HALF_OPEN): "cooldown_elapsed",
    (BreakerState.HALF_OPEN, BreakerState.CLOSED): "probe_success",
    (BreakerState.HALF_OPEN, BreakerState.OPEN): "probe_failure",
    (BreakerState.OPEN, BreakerState.CLOSED): "manual_reset",
}


@dataclass
class CircuitBreakerConfig:
    """Configuration for a single circuit breaker scope."""

    scope: str
    failure_threshold: int = 5
    window_ms: int = 3_600_000  # 1 hour
    cooldown_ms: int = 1_800_000  # 30 minutes
    notify: bool = True

    @property
    def window_seconds(self) -> float:
        return self.window_ms / 1000.0

    @property
    def cooldown_seconds(self) -> float:
        return self.cooldown_ms / 1000.0


@dataclass
class CircuitBreaker:
    """Runtime state of a single circuit breaker."""

    config: CircuitBreakerConfig
    state: BreakerState = BreakerState.CLOSED
    failures: deque[float] = field(default_factory=deque)
    opened_at: float | None = None
    probe_in_flight: bool = False
    last_notification: float | None = None
    last_activity: float = field(default_factory=time.monotonic)
    from_config: bool = True  # False for dynamically created breakers


@dataclass(slots=True)
class BreakerCheckResult:
    """Result of checking a single breaker against a context."""

    scope: str
    state: str
    blocked: bool
    message: str
    failure_count: int
    failure_threshold: int
    cooldown_remaining_ms: int | None = None


# ---------------------------------------------------------------------------
# Scope matching
# ---------------------------------------------------------------------------


def matches_scope(scope: str, context: dict[str, Any]) -> bool:
    """Check if a breaker scope matches a decision context.

    Scope formats:
        "global"              — matches everything
        "category:<value>"    — matches context["category"]
        "stakes:<value>"      — matches context["stakes"]
        "agent:<value>"       — matches context["agent_id"]
        "tag:<value>"         — matches if value in context["tags"]
    """
    if scope == "global":
        return True

    if ":" not in scope:
        return False

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


# ---------------------------------------------------------------------------
# YAML config loading
# ---------------------------------------------------------------------------


def load_breaker_configs(config_path: Path | None = None) -> list[CircuitBreakerConfig]:
    """Load circuit breaker configurations from YAML.

    Searches guardrails/circuit_breakers.yaml in the project root
    and any custom path provided.
    """
    configs: list[CircuitBreakerConfig] = []
    paths_to_try: list[Path] = []

    if config_path:
        paths_to_try.append(config_path)
    else:
        paths_to_try.extend([
            Path(__file__).parent.parent.parent / "guardrails" / "circuit_breakers.yaml",
            Path.cwd() / "guardrails" / "circuit_breakers.yaml",
        ])

    for path in paths_to_try:
        if not path.exists():
            continue
        try:
            import yaml

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if data is None:
                continue

            items = data.get("circuit_breakers", data)
            if not isinstance(items, list):
                items = [items]

            for item in items:
                if not isinstance(item, dict):
                    continue
                configs.append(CircuitBreakerConfig(
                    scope=item["scope"],
                    failure_threshold=int(item.get("failure_threshold", 5)),
                    window_ms=int(item.get("window_ms", 3_600_000)),
                    cooldown_ms=int(item.get("cooldown_ms", 1_800_000)),
                    notify=bool(item.get("notify", True)),
                ))
            logger.info("Loaded %d circuit breaker configs from %s", len(configs), path)
            return configs  # Use first file found
        except ImportError:
            logger.warning("PyYAML not installed, cannot load circuit breaker config from %s", path)
        except Exception as e:
            logger.warning("Failed to load circuit breaker config from %s: %s", path, e)

    return configs


# ---------------------------------------------------------------------------
# JSONL persistence
# ---------------------------------------------------------------------------


def _serialize_breaker(scope: str, breaker: CircuitBreaker) -> dict[str, Any]:
    """Serialize breaker state for JSONL persistence."""
    return {
        "scope": scope,
        "state": breaker.state.value,
        "failures": list(breaker.failures),
        "opened_at": breaker.opened_at,
        "probe_in_flight": breaker.probe_in_flight,
        "last_notification": breaker.last_notification,
        "last_activity": breaker.last_activity,
        "timestamp": datetime.now(UTC).isoformat(),
    }


def _save_all_breakers(
    breakers: dict[str, CircuitBreaker], path: Path
) -> None:
    """Full rewrite of all breaker states to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for scope, breaker in breakers.items():
            line = json.dumps(_serialize_breaker(scope, breaker), ensure_ascii=False)
            f.write(line + "\n")


def _append_breaker(scope: str, breaker: CircuitBreaker, path: Path) -> None:
    """Append a single breaker state to JSONL."""
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(_serialize_breaker(scope, breaker), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _load_breakers_from_jsonl(
    path: Path, configs: dict[str, CircuitBreakerConfig]
) -> dict[str, CircuitBreaker]:
    """Load breaker states from JSONL, keeping only the last entry per scope."""
    if not path.exists():
        return {}

    latest: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                scope = data["scope"]
                latest[scope] = data  # Last entry wins
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(
                    "Skipping invalid circuit breaker entry at line %d: %s",
                    line_num, e,
                )

    breakers: dict[str, CircuitBreaker] = {}
    for scope, data in latest.items():
        config = configs.get(scope) or CircuitBreakerConfig(scope=scope)
        from_config = scope in configs

        try:
            state = BreakerState(data.get("state", "closed"))
        except ValueError:
            state = BreakerState.CLOSED

        failures_raw = data.get("failures", [])
        failures: deque[float] = deque(
            float(ts) for ts in failures_raw
        )

        breakers[scope] = CircuitBreaker(
            config=config,
            state=state,
            failures=failures,
            opened_at=data.get("opened_at"),
            probe_in_flight=bool(data.get("probe_in_flight", False)),
            last_notification=data.get("last_notification"),
            last_activity=data.get("last_activity", time.monotonic()),
            from_config=from_config,
        )

    return breakers


# ---------------------------------------------------------------------------
# CircuitBreakerManager
# ---------------------------------------------------------------------------


class CircuitBreakerManager:
    """Manages all circuit breakers with atomic state transitions.

    Thread-safety: all state mutations protected by asyncio.Lock.
    Persistence: JSONL append on every state change, full rewrite on reset/eviction.
    """

    def __init__(
        self,
        config_path: Path | None = None,
        persistence_path: str | None = None,
    ) -> None:
        self._config_path = config_path
        self._persistence_path = Path(persistence_path or CIRCUIT_BREAKER_DATA_PATH)
        self._configs: dict[str, CircuitBreakerConfig] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Load configs from YAML and restore state from JSONL."""
        configs = load_breaker_configs(self._config_path)
        self._configs = {c.scope: c for c in configs}

        # Restore persisted state
        self._breakers = _load_breakers_from_jsonl(
            self._persistence_path, self._configs
        )

        # Ensure all configured scopes have a breaker
        for scope, config in self._configs.items():
            if scope not in self._breakers:
                self._breakers[scope] = CircuitBreaker(
                    config=config, from_config=True
                )

        self._initialized = True
        logger.info(
            "CircuitBreakerManager initialized: %d configs, %d active breakers",
            len(self._configs),
            len(self._breakers),
        )

    def _get_or_create_breaker(self, scope: str) -> CircuitBreaker:
        """Get existing breaker or create a dynamic one."""
        if scope not in self._breakers:
            config = self._configs.get(scope) or CircuitBreakerConfig(scope=scope)
            self._breakers[scope] = CircuitBreaker(
                config=config,
                from_config=scope in self._configs,
            )
        return self._breakers[scope]

    def _evict_stale_window(self, breaker: CircuitBreaker) -> None:
        """Remove failure timestamps outside the sliding window."""
        cutoff = time.monotonic() - breaker.config.window_seconds
        while breaker.failures and breaker.failures[0] < cutoff:
            breaker.failures.popleft()

    def _check_lazy_cooldown(self, breaker: CircuitBreaker) -> None:
        """Transition OPEN -> HALF_OPEN if cooldown has elapsed."""
        if (
            breaker.state is BreakerState.OPEN
            and breaker.opened_at is not None
        ):
            elapsed = time.monotonic() - breaker.opened_at
            if elapsed >= breaker.config.cooldown_seconds:
                breaker.state = BreakerState.HALF_OPEN
                breaker.probe_in_flight = False
                breaker.last_activity = time.monotonic()
                logger.info(
                    "Circuit breaker %s: OPEN -> HALF_OPEN (cooldown elapsed)",
                    breaker.config.scope,
                )

    def _check_invariants(self, breaker: CircuitBreaker) -> None:
        """Verify post-mutation invariants (debug aid)."""
        if breaker.state is BreakerState.CLOSED:
            assert breaker.opened_at is None, "CLOSED breaker must have opened_at=None"
        if breaker.state in (BreakerState.OPEN, BreakerState.HALF_OPEN):
            assert breaker.opened_at is not None, f"{breaker.state.name} must have opened_at set"
        if breaker.probe_in_flight:
            assert breaker.state is BreakerState.HALF_OPEN, (
                "probe_in_flight only valid in HALF_OPEN"
            )

    def _should_notify(self, breaker: CircuitBreaker) -> bool:
        """Check if enough time has passed since last notification."""
        if not breaker.config.notify:
            return False
        if breaker.last_notification is None:
            return True
        return (time.monotonic() - breaker.last_notification) >= _NOTIFICATION_DEBOUNCE_SECONDS

    def _emit_notification(
        self, scope: str, breaker: CircuitBreaker, event: str
    ) -> None:
        """Emit a structured audit log notification."""
        if not self._should_notify(breaker):
            return
        breaker.last_notification = time.monotonic()
        audit_entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": f"circuit_breaker_{event}",
            "scope": scope,
            "state": breaker.state.value,
            "failure_count": len(breaker.failures),
            "threshold": breaker.config.failure_threshold,
        }
        _audit_logger.info(json.dumps(audit_entry))

    async def _persist_breaker(self, scope: str) -> None:
        """Append current breaker state to JSONL."""
        breaker = self._breakers.get(scope)
        if breaker:
            _append_breaker(scope, breaker, self._persistence_path)

    async def _persist_all(self) -> None:
        """Full rewrite of all breaker states."""
        _save_all_breakers(self._breakers, self._persistence_path)

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------

    async def check(
        self, context: dict[str, Any]
    ) -> list[BreakerCheckResult]:
        """Check all matching breakers against a decision context.

        Returns a list of BreakerCheckResult for each matching scope.
        Most-restrictive-wins: if ANY matching breaker is OPEN, the action
        is blocked.

        Called from evaluate_guardrails() / pre_action flow.
        """
        results: list[BreakerCheckResult] = []

        async with self._lock:
            for scope, breaker in list(self._breakers.items()):
                if not matches_scope(scope, context):
                    continue

                self._evict_stale_window(breaker)
                self._check_lazy_cooldown(breaker)

                if breaker.state is BreakerState.CLOSED:
                    results.append(BreakerCheckResult(
                        scope=scope,
                        state=breaker.state.value,
                        blocked=False,
                        message="",
                        failure_count=len(breaker.failures),
                        failure_threshold=breaker.config.failure_threshold,
                    ))

                elif breaker.state is BreakerState.OPEN:
                    remaining_ms = None
                    if breaker.opened_at is not None:
                        elapsed = time.monotonic() - breaker.opened_at
                        remaining = breaker.config.cooldown_seconds - elapsed
                        remaining_ms = max(0, int(remaining * 1000))

                    results.append(BreakerCheckResult(
                        scope=scope,
                        state=breaker.state.value,
                        blocked=True,
                        message=(
                            f"Circuit breaker OPEN for {scope}: "
                            f"{len(breaker.failures)}/{breaker.config.failure_threshold} "
                            f"failures in window"
                        ),
                        failure_count=len(breaker.failures),
                        failure_threshold=breaker.config.failure_threshold,
                        cooldown_remaining_ms=remaining_ms,
                    ))

                elif breaker.state is BreakerState.HALF_OPEN:
                    if not breaker.probe_in_flight:
                        # Allow one probe through
                        breaker.probe_in_flight = True
                        breaker.last_activity = time.monotonic()
                        await self._persist_breaker(scope)
                        results.append(BreakerCheckResult(
                            scope=scope,
                            state=breaker.state.value,
                            blocked=False,
                            message=f"Circuit breaker HALF_OPEN for {scope}: probe allowed",
                            failure_count=len(breaker.failures),
                            failure_threshold=breaker.config.failure_threshold,
                        ))
                    else:
                        # Probe already in flight, block additional requests
                        results.append(BreakerCheckResult(
                            scope=scope,
                            state=breaker.state.value,
                            blocked=True,
                            message=(
                                f"Circuit breaker HALF_OPEN for {scope}: "
                                f"probe in flight, additional requests blocked"
                            ),
                            failure_count=len(breaker.failures),
                            failure_threshold=breaker.config.failure_threshold,
                        ))

        return results

    async def record_outcome(
        self,
        context: dict[str, Any],
        outcome: str,
    ) -> None:
        """Record a decision outcome and update matching breakers.

        Called from _handle_review_decision as a post-review side effect.

        Args:
            context: Decision context (category, stakes, agent_id, tags).
            outcome: Decision outcome — "failure" and "abandoned" increment
                     failure counters. "success" and "partial" do not.
        """
        is_failure = outcome in ("failure", "abandoned")

        async with self._lock:
            for scope, breaker in list(self._breakers.items()):
                if not matches_scope(scope, context):
                    continue

                breaker.last_activity = time.monotonic()

                if is_failure:
                    self._record_failure(scope, breaker)
                else:
                    self._record_success(scope, breaker)

                self._check_invariants(breaker)
                await self._persist_breaker(scope)

    def _record_failure(self, scope: str, breaker: CircuitBreaker) -> None:
        """Record a failure for a breaker (called under lock)."""
        if breaker.state is BreakerState.CLOSED:
            breaker.failures.append(time.monotonic())
            self._evict_stale_window(breaker)

            if len(breaker.failures) >= breaker.config.failure_threshold:
                # Trip the breaker
                breaker.state = BreakerState.OPEN
                breaker.opened_at = time.monotonic()
                breaker.probe_in_flight = False
                logger.warning(
                    "Circuit breaker TRIPPED for %s: %d/%d failures",
                    scope,
                    len(breaker.failures),
                    breaker.config.failure_threshold,
                )
                self._emit_notification(scope, breaker, "tripped")

        elif breaker.state is BreakerState.HALF_OPEN:
            # Probe failed — back to OPEN
            breaker.state = BreakerState.OPEN
            breaker.opened_at = time.monotonic()
            breaker.probe_in_flight = False
            logger.info(
                "Circuit breaker %s: HALF_OPEN -> OPEN (probe failed)", scope
            )
            self._emit_notification(scope, breaker, "probe_failed")

        elif breaker.state is BreakerState.OPEN:
            # Already open — just record for stats, don't extend window
            breaker.failures.append(time.monotonic())
            self._evict_stale_window(breaker)

    def _record_success(self, scope: str, breaker: CircuitBreaker) -> None:
        """Record a success for a breaker (called under lock)."""
        if breaker.state is BreakerState.HALF_OPEN:
            # Probe succeeded — close the breaker
            breaker.state = BreakerState.CLOSED
            breaker.failures.clear()
            breaker.opened_at = None
            breaker.probe_in_flight = False
            logger.info(
                "Circuit breaker %s: HALF_OPEN -> CLOSED (probe succeeded)", scope
            )
            self._emit_notification(scope, breaker, "recovered")

        elif breaker.state is BreakerState.CLOSED:
            # Success in CLOSED state — clear failure history
            breaker.failures.clear()

    async def get_state(self, scope: str) -> dict[str, Any] | None:
        """Get the current state of a specific breaker.

        Returns None if scope has no breaker.
        """
        async with self._lock:
            breaker = self._breakers.get(scope)
            if breaker is None:
                return None

            self._evict_stale_window(breaker)
            self._check_lazy_cooldown(breaker)

            cooldown_remaining_ms = None
            if breaker.state is BreakerState.OPEN and breaker.opened_at is not None:
                elapsed = time.monotonic() - breaker.opened_at
                remaining = breaker.config.cooldown_seconds - elapsed
                cooldown_remaining_ms = max(0, int(remaining * 1000))

            return {
                "scope": scope,
                "state": breaker.state.value,
                "failure_count": len(breaker.failures),
                "failure_threshold": breaker.config.failure_threshold,
                "window_ms": breaker.config.window_ms,
                "cooldown_ms": breaker.config.cooldown_ms,
                "cooldown_remaining_ms": cooldown_remaining_ms,
                "opened_at": breaker.opened_at,
                "probe_in_flight": breaker.probe_in_flight,
                "from_config": breaker.from_config,
            }

    async def reset(
        self, scope: str, *, probe_first: bool = False
    ) -> dict[str, Any]:
        """Manually reset a circuit breaker.

        Args:
            scope: Breaker scope to reset.
            probe_first: If True, transition OPEN -> HALF_OPEN instead
                         of OPEN -> CLOSED.

        Returns:
            Dict with previous and new state, or error.
        """
        async with self._lock:
            breaker = self._breakers.get(scope)
            if breaker is None:
                return {"error": f"No breaker found for scope: {scope}"}

            prev_state = breaker.state

            if prev_state is not BreakerState.OPEN:
                return {
                    "error": f"Can only reset OPEN breakers, current state: {prev_state.value}",
                    "scope": scope,
                    "state": prev_state.value,
                }

            if probe_first:
                breaker.state = BreakerState.HALF_OPEN
                breaker.probe_in_flight = False
                breaker.last_activity = time.monotonic()
            else:
                breaker.state = BreakerState.CLOSED
                breaker.failures.clear()
                breaker.opened_at = None
                breaker.probe_in_flight = False
                breaker.last_activity = time.monotonic()

            self._check_invariants(breaker)
            await self._persist_breaker(scope)

            logger.info(
                "Circuit breaker %s manually reset: %s -> %s",
                scope,
                prev_state.value,
                breaker.state.value,
            )
            self._emit_notification(scope, breaker, "manual_reset")

            return {
                "scope": scope,
                "previous_state": prev_state.value,
                "new_state": breaker.state.value,
            }

    async def list_breakers(self) -> list[dict[str, Any]]:
        """List all breakers with their current state."""
        results: list[dict[str, Any]] = []

        async with self._lock:
            for scope in sorted(self._breakers.keys()):
                breaker = self._breakers[scope]
                self._evict_stale_window(breaker)
                self._check_lazy_cooldown(breaker)

                cooldown_remaining_ms = None
                if breaker.state is BreakerState.OPEN and breaker.opened_at is not None:
                    elapsed = time.monotonic() - breaker.opened_at
                    remaining = breaker.config.cooldown_seconds - elapsed
                    cooldown_remaining_ms = max(0, int(remaining * 1000))

                results.append({
                    "scope": scope,
                    "state": breaker.state.value,
                    "failure_count": len(breaker.failures),
                    "failure_threshold": breaker.config.failure_threshold,
                    "window_ms": breaker.config.window_ms,
                    "cooldown_ms": breaker.config.cooldown_ms,
                    "cooldown_remaining_ms": cooldown_remaining_ms,
                    "from_config": breaker.from_config,
                })

        return results

    async def evict_stale(self) -> int:
        """Evict dynamic breakers that are CLOSED with no activity for 24h.

        Config-defined breakers are never evicted.

        Returns:
            Number of breakers evicted.
        """
        evicted = 0
        now = time.monotonic()

        async with self._lock:
            to_remove: list[str] = []
            for scope, breaker in self._breakers.items():
                if breaker.from_config:
                    continue
                if breaker.state is not BreakerState.CLOSED:
                    continue
                if not breaker.failures and (now - breaker.last_activity) > _STALE_EVICTION_SECONDS:
                    to_remove.append(scope)

            for scope in to_remove:
                del self._breakers[scope]
                evicted += 1

            if evicted > 0:
                await self._persist_all()
                logger.info("Evicted %d stale circuit breakers", evicted)

        return evicted

    async def get_non_closed_summary(self) -> list[dict[str, Any]]:
        """Get summary of non-CLOSED breakers for session context.

        Returns breakers in OPEN or HALF_OPEN state with key details
        for inclusion in get_session_context markdown.
        """
        results: list[dict[str, Any]] = []

        async with self._lock:
            for scope, breaker in self._breakers.items():
                self._evict_stale_window(breaker)
                self._check_lazy_cooldown(breaker)

                if breaker.state is BreakerState.CLOSED:
                    continue

                cooldown_remaining_ms = None
                if breaker.state is BreakerState.OPEN and breaker.opened_at is not None:
                    elapsed = time.monotonic() - breaker.opened_at
                    remaining = breaker.config.cooldown_seconds - elapsed
                    cooldown_remaining_ms = max(0, int(remaining * 1000))

                results.append({
                    "scope": scope,
                    "state": breaker.state.value,
                    "failure_count": len(breaker.failures),
                    "failure_threshold": breaker.config.failure_threshold,
                    "cooldown_remaining_ms": cooldown_remaining_ms,
                })

        return results


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_manager: CircuitBreakerManager | None = None
_manager_lock = asyncio.Lock()


async def get_circuit_breaker_manager(
    config_path: Path | None = None,
    persistence_path: str | None = None,
) -> CircuitBreakerManager:
    """Get or create the singleton CircuitBreakerManager.

    First call initializes from config + JSONL. Subsequent calls
    return the same instance.
    """
    global _manager
    async with _manager_lock:
        if _manager is None:
            _manager = CircuitBreakerManager(
                config_path=config_path,
                persistence_path=persistence_path,
            )
            await _manager.initialize()
        return _manager


def set_circuit_breaker_manager(manager: CircuitBreakerManager | None) -> None:
    """Replace the singleton manager (for testing)."""
    global _manager
    _manager = manager
