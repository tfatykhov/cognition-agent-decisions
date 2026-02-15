"""Tests for F126: cstp.debugTracker endpoint."""

import time
from unittest.mock import patch

import pytest

from a2a.cstp.deliberation_tracker import (
    DeliberationTracker,
    TrackedInput,
    debug_tracker,
    reset_tracker,
    track_reasoning,
)
from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.models import DebugTrackerRequest, DebugTrackerResponse
from a2a.models.jsonrpc import JsonRpcRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_tracker() -> None:
    """Reset global tracker before each test."""
    reset_tracker()


def _make_input(
    id: str = "t-001",
    type: str = "reasoning",
    text: str = "test thought",
    source: str = "cstp:recordThought",
    timestamp: float | None = None,
) -> TrackedInput:
    """Build a TrackedInput with sensible defaults."""
    return TrackedInput(
        id=id,
        type=type,
        text=text,
        source=source,
        timestamp=timestamp or time.time(),
        raw_data={"text": text},
    )


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestDebugTrackerModels:
    def test_request_from_params_no_key(self) -> None:
        req = DebugTrackerRequest.from_params({})
        assert req.key is None

    def test_request_from_params_with_key(self) -> None:
        req = DebugTrackerRequest.from_params({"key": "agent-1"})
        assert req.key == "agent-1"

    def test_response_to_dict(self) -> None:
        resp = DebugTrackerResponse(
            sessions=["s1", "s2"],
            session_count=2,
            detail={"s1": {"inputCount": 1, "inputs": []}},
        )
        data = resp.to_dict()
        assert data["sessions"] == ["s1", "s2"]
        assert data["sessionCount"] == 2
        assert "s1" in data["detail"]


# ---------------------------------------------------------------------------
# Core tracker tests
# ---------------------------------------------------------------------------


class TestDebugTrackerEmpty:
    def test_debug_tracker_empty(self) -> None:
        """debugTracker with no sessions returns empty result."""
        tracker = DeliberationTracker()
        result = tracker.debug_sessions()
        assert result["sessions"] == []
        assert result["sessionCount"] == 0
        assert result["detail"] == {}


class TestDebugTrackerAfterRecordThought:
    def test_debug_tracker_after_record_thought(self) -> None:
        """After recordThought, debugTracker shows the thought with correct fields."""
        tracker = DeliberationTracker()
        now = time.time()
        inp = _make_input(id="r-abc123", type="reasoning", text="Consider X", timestamp=now)
        tracker.track("agent-1", inp)

        result = tracker.debug_sessions(key="agent-1")

        assert result["sessions"] == ["agent-1"]
        assert result["sessionCount"] == 1
        detail = result["detail"]["agent-1"]
        assert detail["inputCount"] == 1

        entry = detail["inputs"][0]
        assert entry["id"] == "r-abc123"
        assert entry["type"] == "reasoning"
        assert entry["text"] == "Consider X"
        assert entry["source"] == "cstp:recordThought"
        assert isinstance(entry["ageSeconds"], int)
        assert entry["ageSeconds"] >= 0


class TestDebugTrackerSpecificKey:
    def test_debug_tracker_specific_key(self) -> None:
        """debugTracker with specific key returns only that session."""
        tracker = DeliberationTracker()
        tracker.track("agent-1", _make_input(id="t-001", text="thought A"))
        tracker.track("agent-2", _make_input(id="t-002", text="thought B"))

        result = tracker.debug_sessions(key="agent-1")

        assert result["sessions"] == ["agent-1"]
        assert result["sessionCount"] == 1
        assert "agent-1" in result["detail"]
        assert "agent-2" not in result["detail"]
        assert result["detail"]["agent-1"]["inputs"][0]["id"] == "t-001"


class TestDebugTrackerAllSessions:
    def test_debug_tracker_all_sessions(self) -> None:
        """debugTracker without key returns all sessions."""
        tracker = DeliberationTracker()
        tracker.track("agent-1", _make_input(id="t-001"))
        tracker.track("agent-2", _make_input(id="t-002"))
        tracker.track("agent-3", _make_input(id="t-003"))

        result = tracker.debug_sessions()

        assert result["sessionCount"] == 3
        assert set(result["sessions"]) == {"agent-1", "agent-2", "agent-3"}
        assert len(result["detail"]) == 3


class TestDebugTrackerReadOnly:
    def test_debug_tracker_read_only(self) -> None:
        """debugTracker is read-only — calling it twice returns same data."""
        tracker = DeliberationTracker()
        tracker.track("agent-1", _make_input(id="t-001"))

        result1 = tracker.debug_sessions(key="agent-1")
        result2 = tracker.debug_sessions(key="agent-1")

        assert result1["sessionCount"] == result2["sessionCount"]
        assert result1["detail"]["agent-1"]["inputCount"] == 1
        assert result2["detail"]["agent-1"]["inputCount"] == 1


class TestDebugTrackerAgeSeconds:
    def test_debug_tracker_age_seconds(self) -> None:
        """age_seconds is computed correctly from timestamp."""
        tracker = DeliberationTracker()
        past = time.time() - 60  # 60 seconds ago
        tracker.track("agent-1", _make_input(id="t-001", timestamp=past))

        with patch("a2a.cstp.deliberation_tracker.time") as mock_time:
            mock_time.time.return_value = past + 60
            result = tracker.debug_sessions(key="agent-1")

        entry = result["detail"]["agent-1"]["inputs"][0]
        assert entry["ageSeconds"] == 60


class TestDebugTrackerAfterPreactionConsumes:
    def test_debug_tracker_after_preaction_consumes(self) -> None:
        """After consume(), debugTracker shows the session was emptied."""
        tracker = DeliberationTracker()
        tracker.track("agent-1", _make_input(id="t-001"))

        # Verify input is visible before consume
        before = tracker.debug_sessions(key="agent-1")
        assert before["detail"]["agent-1"]["inputCount"] == 1

        # Consume (simulates what preAction/recordDecision does)
        tracker.consume("agent-1")

        # After consume, session is removed
        after = tracker.debug_sessions(key="agent-1")
        assert after["sessions"] == []
        assert after["sessionCount"] == 0
        assert after["detail"] == {}


class TestDebugTrackerKeyNotFound:
    def test_debug_tracker_key_not_found(self) -> None:
        """debugTracker with nonexistent key returns empty result (no error)."""
        tracker = DeliberationTracker()
        # Add a session for a different key
        tracker.track("agent-1", _make_input(id="t-001"))

        result = tracker.debug_sessions(key="nonexistent-agent")

        assert result["sessions"] == []
        assert result["sessionCount"] == 0
        assert result["detail"] == {}


class TestDebugTrackerExpiredInputs:
    def test_debug_tracker_expired_inputs(self) -> None:
        """Inputs past TTL are filtered out of debug output."""
        tracker = DeliberationTracker(ttl_seconds=60)

        # Input created 120 seconds ago (past 60s TTL)
        old_time = time.time() - 120
        tracker.track("agent-1", _make_input(id="t-old", timestamp=old_time))
        # Recent input
        tracker.track("agent-1", _make_input(id="t-new", timestamp=time.time()))

        result = tracker.debug_sessions(key="agent-1")

        # Only the recent input should appear
        detail = result["detail"]["agent-1"]
        assert detail["inputCount"] == 1
        assert detail["inputs"][0]["id"] == "t-new"


# ---------------------------------------------------------------------------
# Convenience function tests
# ---------------------------------------------------------------------------


class TestDebugTrackerConvenience:
    def test_debug_tracker_convenience_empty(self) -> None:
        """debug_tracker() convenience wrapper works with empty state."""
        result = debug_tracker()
        assert result["sessions"] == []
        assert result["sessionCount"] == 0

    def test_debug_tracker_convenience_with_data(self) -> None:
        """debug_tracker() convenience wrapper uses global tracker."""
        track_reasoning("rpc:test-agent", "some reasoning")
        result = debug_tracker(key="rpc:test-agent")
        assert result["sessionCount"] == 1
        assert result["detail"]["rpc:test-agent"]["inputCount"] == 1

    def test_debug_tracker_convenience_with_key(self) -> None:
        """debug_tracker(key=...) filters to specific session."""
        track_reasoning("rpc:agent-1", "thought A")
        track_reasoning("rpc:agent-2", "thought B")
        result = debug_tracker(key="rpc:agent-1")
        assert result["sessionCount"] == 1
        assert "rpc:agent-1" in result["detail"]
        assert "rpc:agent-2" not in result["detail"]


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


class TestDebugTrackerDispatcher:
    @pytest.fixture
    def dispatcher(self) -> CstpDispatcher:
        d = CstpDispatcher()
        register_methods(d)
        return d

    def test_method_registered(self, dispatcher: CstpDispatcher) -> None:
        assert "cstp.debugTracker" in dispatcher._methods

    @pytest.mark.asyncio
    async def test_dispatch_empty(self, dispatcher: CstpDispatcher) -> None:
        """Dispatching debugTracker with no sessions returns empty result."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.debugTracker",
            params={},
            id="test-1",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")
        assert response.error is None
        assert response.result is not None
        assert response.result["sessions"] == []
        assert response.result["sessionCount"] == 0
        assert response.result["detail"] == {}

    @pytest.mark.asyncio
    async def test_dispatch_with_key(self, dispatcher: CstpDispatcher) -> None:
        """Dispatching debugTracker with key filters correctly."""
        # Track something via the global tracker
        track_reasoning("rpc:test-agent", "my thought")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.debugTracker",
            params={"key": "rpc:test-agent"},
            id="test-2",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")
        assert response.error is None
        assert response.result["sessionCount"] == 1
        assert response.result["detail"]["rpc:test-agent"]["inputCount"] == 1

    @pytest.mark.asyncio
    async def test_dispatch_nonexistent_key(self, dispatcher: CstpDispatcher) -> None:
        """Dispatching debugTracker with nonexistent key returns empty (no error)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.debugTracker",
            params={"key": "no-such-session"},
            id="test-3",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")
        assert response.error is None
        assert response.result["sessions"] == []
        assert response.result["sessionCount"] == 0
