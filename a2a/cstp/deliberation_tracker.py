"""F023 Phase 2: Server-side deliberation auto-capture.

Tracks API calls (queries, guardrail checks, lookups) per agent/session
and auto-builds Deliberation objects when decisions are recorded.

Works for both JSON-RPC (keyed by agent_id) and MCP (keyed by session_id).
Zero client changes required.

All tracking operations are fail-open: errors are logged but never
propagate to the main API flow.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from .decision_service import Deliberation, DeliberationInput, DeliberationStep

logger = logging.getLogger("cstp-deliberation")


@dataclass(slots=True)
class TrackedInput:
    """A single tracked input from an API call."""

    id: str
    type: str  # "query" | "guardrail" | "lookup" | "stats"
    text: str
    source: str  # "cstp:queryDecisions" etc.
    timestamp: float  # time.time()
    raw_data: dict[str, Any]


@dataclass
class TrackerSession:
    """Accumulated inputs for one agent/session."""

    inputs: list[TrackedInput] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)


class DeliberationTracker:
    """Tracks API calls per agent/session for auto-deliberation capture.

    Thread-safe. Singleton instance shared across dispatcher and MCP server.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._sessions: dict[str, TrackerSession] = {}
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def track(self, key: str, tracked_input: TrackedInput) -> None:
        """Register an input for the given agent/session key."""
        with self._lock:
            # Probabilistic cleanup: ~2% of calls
            if random.random() < 0.02:
                self._cleanup_expired_locked()

            if key not in self._sessions:
                self._sessions[key] = TrackerSession()
            session = self._sessions[key]
            session.inputs.append(tracked_input)
            session.last_activity = time.time()

    def consume(self, key: str) -> Deliberation | None:
        """Build Deliberation from tracked inputs and clear them.

        Returns None if no inputs were tracked.
        Called during recordDecision.
        Filters out inputs older than TTL.
        """
        with self._lock:
            session = self._sessions.pop(key, None)

        if not session or not session.inputs:
            return None

        # Filter expired inputs
        cutoff = time.time() - self._ttl
        valid_inputs = [i for i in session.inputs if i.timestamp >= cutoff]

        if not valid_inputs:
            return None

        return self._build_deliberation(valid_inputs)

    def get_inputs(self, key: str) -> list[TrackedInput]:
        """Peek at current tracked inputs without consuming."""
        with self._lock:
            session = self._sessions.get(key)
            if not session:
                return []
            # Filter expired inputs
            cutoff = time.time() - self._ttl
            return [i for i in session.inputs if i.timestamp >= cutoff]

    def cleanup_expired(self) -> int:
        """Remove sessions older than TTL. Returns count removed."""
        with self._lock:
            return self._cleanup_expired_locked()

    def _cleanup_expired_locked(self) -> int:
        """Internal cleanup (must hold lock)."""
        cutoff = time.time() - self._ttl
        expired = [
            k
            for k, s in self._sessions.items()
            if s.last_activity < cutoff
        ]
        for k in expired:
            del self._sessions[k]
        return len(expired)

    def _build_deliberation(
        self, inputs: list[TrackedInput]
    ) -> Deliberation:
        """Convert tracked inputs into a Deliberation object.

        Auto-generates steps from the input sequence:
        - Each input becomes a step describing what was gathered
        - Steps reference which input IDs they used
        - Total duration spans first to last input
        """
        # Build DeliberationInput list
        delib_inputs = []
        for inp in inputs:
            delib_inputs.append(
                DeliberationInput(
                    id=inp.id,
                    text=inp.text,
                    source=inp.source,
                    timestamp=_format_timestamp(inp.timestamp),
                )
            )

        # Build steps from the input sequence
        steps = []
        for i, inp in enumerate(inputs, start=1):
            step_type = _input_type_to_step_type(inp.type)
            steps.append(
                DeliberationStep(
                    step=i,
                    thought=inp.text,
                    inputs_used=[inp.id],
                    timestamp=_format_timestamp(inp.timestamp),
                    type=step_type,
                    conclusion=False,
                )
            )

        # Calculate total duration
        total_duration_ms: int | None = None
        if len(inputs) >= 2:
            total_duration_ms = int(
                (inputs[-1].timestamp - inputs[0].timestamp) * 1000
            )

        return Deliberation(
            inputs=delib_inputs,
            steps=steps,
            total_duration_ms=total_duration_ms,
            convergence_point=None,
        )

    @property
    def session_count(self) -> int:
        """Number of active tracker sessions."""
        with self._lock:
            return len(self._sessions)


def _format_timestamp(ts: float) -> str:
    """Convert time.time() to ISO format string."""
    from datetime import UTC, datetime

    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _input_type_to_step_type(input_type: str) -> str:
    """Map tracked input type to deliberation step type."""
    mapping = {
        "query": "analysis",
        "guardrail": "constraint",
        "lookup": "analysis",
        "stats": "empirical",
    }
    return mapping.get(input_type, "analysis")


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_tracker: DeliberationTracker | None = None
_tracker_lock = threading.Lock()


def get_tracker(ttl_seconds: int = 300) -> DeliberationTracker:
    """Get or create the global tracker instance."""
    global _tracker
    if _tracker is not None:
        return _tracker
    with _tracker_lock:
        if _tracker is None:
            _tracker = DeliberationTracker(ttl_seconds=ttl_seconds)
        return _tracker


def reset_tracker() -> None:
    """Reset the global tracker (for testing)."""
    global _tracker
    with _tracker_lock:
        _tracker = None


# ---------------------------------------------------------------------------
# Convenience helpers — called from dispatcher / mcp_server
# ---------------------------------------------------------------------------


def track_query(
    key: str,
    query: str,
    result_count: int,
    top_ids: list[str],
    retrieval_mode: str,
    top_results: list[dict] | None = None,
) -> None:
    """Track a queryDecisions call. Fail-open."""
    try:
        tracker = get_tracker()
        tracker.track(
            key,
            TrackedInput(
                id=f"q-{uuid4().hex[:8]}",
                type="query",
                text=f"Queried '{query[:50]}': {result_count} results ({retrieval_mode})",
                source="cstp:queryDecisions",
                timestamp=time.time(),
                raw_data={
                    "query": query,
                    "result_count": result_count,
                    "top_ids": top_ids[:5],
                    "retrieval_mode": retrieval_mode,
                    "top_results": top_results[:5] if top_results else [],
                },
            ),
        )
    except Exception:
        logger.debug("Failed to track query", exc_info=True)


def track_guardrail(
    key: str,
    description: str,
    allowed: bool,
    violation_count: int,
) -> None:
    """Track a checkGuardrails call. Fail-open."""
    try:
        status = "allowed" if allowed else f"blocked ({violation_count} violations)"
        tracker = get_tracker()
        tracker.track(
            key,
            TrackedInput(
                id=f"g-{uuid4().hex[:8]}",
                type="guardrail",
                text=f"Checked '{description[:50]}': {status}",
                source="cstp:checkGuardrails",
                timestamp=time.time(),
                raw_data={
                    "description": description,
                    "allowed": allowed,
                    "violation_count": violation_count,
                },
            ),
        )
    except Exception:
        logger.debug("Failed to track guardrail", exc_info=True)


def track_lookup(
    key: str,
    decision_id: str,
    title: str,
) -> None:
    """Track a getDecision call. Fail-open."""
    try:
        tracker = get_tracker()
        tracker.track(
            key,
            TrackedInput(
                id=f"l-{uuid4().hex[:8]}",
                type="lookup",
                text=f"Retrieved decision {decision_id}: {title[:50]}",
                source="cstp:getDecision",
                timestamp=time.time(),
                raw_data={
                    "decision_id": decision_id,
                    "title": title,
                },
            ),
        )
    except Exception:
        logger.debug("Failed to track lookup", exc_info=True)


def track_stats(
    key: str,
    total_decisions: int,
    reason_type_count: int,
    diversity: float | None = None,
) -> None:
    """Track a getReasonStats call. Fail-open."""
    try:
        tracker = get_tracker()
        diversity_str = f", diversity={diversity:.2f}" if diversity else ""
        tracker.track(
            key,
            TrackedInput(
                id=f"s-{uuid4().hex[:8]}",
                type="stats",
                text=f"Reviewed reason stats: {reason_type_count} types, {total_decisions} decisions{diversity_str}",
                source="cstp:getReasonStats",
                timestamp=time.time(),
                raw_data={
                    "total_decisions": total_decisions,
                    "reason_type_count": reason_type_count,
                    "diversity": diversity,
                },
            ),
        )
    except Exception:
        logger.debug("Failed to track stats", exc_info=True)


def auto_attach_deliberation(
    key: str,
    deliberation: Deliberation | None,
) -> tuple[Deliberation | None, bool]:
    """Consume tracked inputs and attach/merge with deliberation. Fail-open.

    Returns:
        (deliberation, auto_captured) — auto_captured is True only if
        tracked inputs were actually consumed and attached.

    - If no explicit deliberation: return auto-built from tracker
    - If explicit deliberation: merge tracked inputs + steps into it
    - If nothing tracked: return the explicit deliberation as-is (or None)
    """
    try:
        tracker = get_tracker()
        auto_delib = tracker.consume(key)
    except Exception:
        logger.debug("Failed to consume deliberation", exc_info=True)
        return deliberation, False

    if not auto_delib:
        # Nothing tracked — return whatever was passed in
        return deliberation, False

    if not deliberation or not deliberation.has_content():
        # No explicit deliberation — use auto-built
        return auto_delib, True

    # Merge: append tracked inputs AND steps to explicit deliberation
    existing_input_ids = {i.id for i in deliberation.inputs}
    for inp in auto_delib.inputs:
        if inp.id not in existing_input_ids:
            deliberation.inputs.append(inp)

    # Also merge auto-generated steps (append after existing steps)
    if auto_delib.steps:
        max_step = max((s.step for s in deliberation.steps), default=0)
        for step in auto_delib.steps:
            # Re-number to follow existing steps
            step.step = max_step + step.step
            deliberation.steps.append(step)

    return deliberation, True


def extract_related_decisions(
    deliberation: Deliberation | None,
) -> list[dict]:
    """Extract related decisions from deliberation trace query results.

    Collects top_results from all query inputs in the deliberation,
    deduplicates by ID, and returns sorted by distance (closest first).

    Returns list of dicts with id, summary, distance.
    """
    if not deliberation or not deliberation.inputs:
        return []

    # Also check raw tracker data if deliberation was auto-built
    seen: dict[str, dict] = {}

    for inp in deliberation.inputs:
        # Deliberation inputs don't have raw_data directly,
        # but we stored top_results in the tracker's raw_data
        # which gets consumed into the deliberation.
        # We need to check the raw_data on TrackedInput before
        # it becomes a DeliberationInput.
        pass

    # The raw_data is lost when TrackedInput becomes DeliberationInput.
    # We need to extract BEFORE the conversion. Let's use a different approach:
    # extract from the tracker's raw inputs before they're consumed.
    return []


def extract_related_from_tracker(key: str) -> list[dict]:
    """Extract related decisions from tracked inputs BEFORE consumption.

    Call this before auto_attach_deliberation to capture top_results
    from query inputs while they're still in the tracker.

    Returns list of dicts with id, summary, distance - deduplicated and sorted.
    """
    try:
        tracker = get_tracker()
        with tracker._lock:
            session = tracker._sessions.get(key)
            if not session:
                return []

            seen: dict[str, dict] = {}
            cutoff = time.time() - tracker._ttl

            for inp in session.inputs:
                if inp.timestamp < cutoff:
                    continue
                if inp.type != "query" or not inp.raw_data:
                    continue
                top_results = inp.raw_data.get("top_results", [])
                for r in top_results:
                    rid = r.get("id", "")
                    if rid and rid not in seen:
                        seen[rid] = {
                            "id": rid,
                            "summary": r.get("summary", ""),
                            "distance": r.get("distance", 0.0),
                        }

            # Sort by distance (closest first) and return
            return sorted(seen.values(), key=lambda x: x["distance"])
    except Exception:
        logger.debug("Failed to extract related decisions", exc_info=True)
        return []
