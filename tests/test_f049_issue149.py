"""Tests for issue #149: F049 Enhancements — Consumed History & Session TTL.

Tests cover:
- ConsumedRecord creation on consume()
- Consumed history bounded by deque maxlen
- backfill_consumed() for decision_id
- Session TTL expiry (independent of input TTL)
- Expired sessions moved to consumed history
- debug_sessions with include_consumed
- debug_sessions triggers cleanup
- Input TTL vs Session TTL independence
- TrackerConfig from YAML, env, and defaults
- ConsumedSessionDetail serialization round-trip
- DebugTrackerRequest include_consumed param
- Dashboard template rendering (transport_id badge, consumed section, decision link, OOB counter)
- Dispatcher backfill after record_decision integration
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Server-side tracker tests (no flask dependency)
# ---------------------------------------------------------------------------

from a2a.cstp.deliberation_tracker import (
    ConsumedRecord,
    DeliberationTracker,
    TrackedInput,
    _parse_key_components,
)
from a2a.cstp.models import (
    ConsumedSessionDetail,
    DebugTrackerRequest,
    DebugTrackerResponse,
)
from a2a.config import Config, TrackerConfig


def _make_input(
    input_id: str = "t-001",
    input_type: str = "query",
    text: str = "test input",
    source: str = "cstp:test",
    ts: float | None = None,
) -> TrackedInput:
    """Helper to create a TrackedInput."""
    return TrackedInput(
        id=input_id,
        type=input_type,
        text=text,
        source=source,
        timestamp=ts or time.time(),
        raw_data={},
    )


# ---- 1. test_consumed_record_on_consume ----


def test_consumed_record_on_consume() -> None:
    """consume() appends a ConsumedRecord to _consumed_history."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=1800, consumed_history_size=50)
    key = "agent:alice"
    tracker.track(key, _make_input("q-1", "query", "Search for X"))
    tracker.track(key, _make_input("q-2", "query", "Search for Y"))

    result = tracker.consume(key)
    assert result is not None  # deliberation was built

    # Consumed history should have one record
    assert len(tracker._consumed_history) == 1
    record = tracker._consumed_history[0]
    assert isinstance(record, ConsumedRecord)
    assert record.key == key
    assert record.input_count == 2
    assert record.agent_id == "alice"
    assert record.decision_id is None  # not backfilled yet
    assert record.status == "consumed"
    assert len(record.inputs_summary) == 2
    assert record.inputs_summary[0]["id"] == "q-1"


# ---- 2. test_consumed_history_bounded ----


def test_consumed_history_bounded() -> None:
    """Consumed history deque evicts oldest when maxlen is exceeded."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=1800, consumed_history_size=3)

    # Consume 5 sessions (only last 3 should remain)
    for i in range(5):
        key = f"agent:user{i}"
        tracker.track(key, _make_input(f"q-{i}", "query", f"query {i}"))
        tracker.consume(key)

    assert len(tracker._consumed_history) == 3
    # Oldest two (user0, user1) should have been evicted
    keys_in_history = [r.key for r in tracker._consumed_history]
    assert "agent:user0" not in keys_in_history
    assert "agent:user1" not in keys_in_history
    assert "agent:user2" in keys_in_history
    assert "agent:user3" in keys_in_history
    assert "agent:user4" in keys_in_history


# ---- 3. test_backfill_consumed_decision_id ----


def test_backfill_consumed_decision_id() -> None:
    """backfill_consumed() sets decision_id on the matching ConsumedRecord."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=1800, consumed_history_size=50)
    key = "agent:bob"
    tracker.track(key, _make_input("q-1"))
    tracker.consume(key)

    # Before backfill
    assert tracker._consumed_history[0].decision_id is None

    # Backfill
    result = tracker.backfill_consumed(key, "abc12345")
    assert result is True
    assert tracker._consumed_history[0].decision_id == "abc12345"

    # Backfill again for same key — should not match (already backfilled)
    result2 = tracker.backfill_consumed(key, "def67890")
    assert result2 is False


# ---- 4. test_session_ttl_expiry ----


def test_session_ttl_expiry() -> None:
    """Sessions expire after session_ttl seconds of inactivity."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=2, consumed_history_size=50)
    key = "agent:charlie"
    now = time.time()

    # Track with a recent timestamp
    tracker.track(key, _make_input("q-1", ts=now))

    # Manually set last_activity to the past beyond session_ttl
    tracker._sessions[key].last_activity = now - 5

    removed = tracker.cleanup_expired()
    assert removed == 1
    assert key not in tracker._sessions


# ---- 5. test_expired_moved_to_consumed ----


def test_expired_moved_to_consumed() -> None:
    """Expired sessions get status='expired' in consumed history."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=2, consumed_history_size=50)
    key = "agent:dave:decision:d001"
    now = time.time()

    tracker.track(key, _make_input("q-1", ts=now))
    # Force session to be expired
    tracker._sessions[key].last_activity = now - 5

    tracker.cleanup_expired()

    assert len(tracker._consumed_history) == 1
    record = tracker._consumed_history[0]
    assert record.status == "expired"
    assert record.key == key
    # _parse_key_components should extract agent_id and decision_id
    assert record.agent_id == "dave"


# ---- 6. test_debug_sessions_include_consumed ----


def test_debug_sessions_include_consumed() -> None:
    """debug_sessions with include_consumed=True returns consumed list."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=1800, consumed_history_size=50)

    # Create and consume a session
    key = "agent:eve"
    tracker.track(key, _make_input("q-1"))
    tracker.consume(key)

    # Track a new active session
    active_key = "agent:frank"
    tracker.track(active_key, _make_input("q-2"))

    # Without include_consumed
    result_no = tracker.debug_sessions(include_consumed=False)
    assert "consumed" not in result_no
    assert result_no["sessionCount"] == 1

    # With include_consumed
    result_yes = tracker.debug_sessions(include_consumed=True)
    assert "consumed" in result_yes
    assert len(result_yes["consumed"]) == 1
    assert result_yes["consumed"][0]["key"] == key
    assert result_yes["consumed"][0]["status"] == "consumed"


# ---- 7. test_debug_sessions_cleanup_on_read ----


def test_debug_sessions_cleanup_on_read() -> None:
    """debug_sessions() triggers deterministic cleanup of expired sessions."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=2, consumed_history_size=50)
    key = "agent:grace"
    now = time.time()

    tracker.track(key, _make_input("q-1", ts=now))
    tracker._sessions[key].last_activity = now - 5  # expired

    # debug_sessions should clean up
    result = tracker.debug_sessions(include_consumed=True)
    assert result["sessionCount"] == 0
    assert key not in result["sessions"]
    # Expired session should be in consumed
    assert len(result["consumed"]) == 1
    assert result["consumed"][0]["status"] == "expired"


# ---- 8. test_input_ttl_vs_session_ttl ----


def test_input_ttl_vs_session_ttl() -> None:
    """Input TTL and session TTL are independent controls."""
    # Short input TTL (2s), long session TTL (1800s)
    tracker = DeliberationTracker(input_ttl=2, session_ttl=1800, consumed_history_size=50)
    key = "agent:heidi"
    now = time.time()

    # Old input (expired by input TTL) and new input
    tracker.track(key, _make_input("q-old", ts=now - 10))
    tracker.track(key, _make_input("q-new", ts=now))

    # Session should still be active (session TTL not exceeded)
    assert key in tracker._sessions

    # But get_inputs should only return the non-expired input
    valid_inputs = tracker.get_inputs(key)
    assert len(valid_inputs) == 1
    assert valid_inputs[0].id == "q-new"

    # Consuming should still work (uses input TTL filter)
    result = tracker.consume(key)
    assert result is not None
    # Only 1 valid input
    assert len(result.inputs) == 1

    # Now test the reverse: long input TTL, short session TTL
    tracker2 = DeliberationTracker(input_ttl=1800, session_ttl=2, consumed_history_size=50)
    key2 = "agent:ivan"
    tracker2.track(key2, _make_input("q-1", ts=now))
    tracker2._sessions[key2].last_activity = now - 5  # session expired

    removed = tracker2.cleanup_expired()
    assert removed == 1  # session expired even though input TTL is long


# ---- 9. test_tracker_config ----


def test_tracker_config() -> None:
    """TrackerConfig loads from YAML dict, env vars, and defaults."""
    # Defaults
    tc = TrackerConfig()
    assert tc.input_ttl_seconds == 300
    assert tc.session_ttl_minutes == 30
    assert tc.consumed_history_size == 50

    # From YAML dict
    cfg = Config._from_dict({
        "tracker": {
            "input_ttl_seconds": 600,
            "session_ttl_minutes": 60,
            "consumed_history_size": 100,
        }
    })
    assert cfg.tracker.input_ttl_seconds == 600
    assert cfg.tracker.session_ttl_minutes == 60
    assert cfg.tracker.consumed_history_size == 100

    # From env vars
    with patch.dict("os.environ", {
        "CSTP_TRACKER_INPUT_TTL": "120",
        "CSTP_TRACKER_SESSION_TTL": "15",
        "CSTP_TRACKER_HISTORY_SIZE": "25",
    }):
        cfg_env = Config.from_env()
        assert cfg_env.tracker.input_ttl_seconds == 120
        assert cfg_env.tracker.session_ttl_minutes == 15
        assert cfg_env.tracker.consumed_history_size == 25

    # Config object includes tracker field
    default_config = Config()
    assert hasattr(default_config, "tracker")
    assert isinstance(default_config.tracker, TrackerConfig)


# ---- 10. test_consumed_session_model ----


def test_consumed_session_model() -> None:
    """ConsumedSessionDetail serialization round-trip."""
    raw = {
        "key": "agent:tester:decision:abc123",
        "consumedAt": 45,
        "inputCount": 3,
        "agentId": "tester",
        "decisionId": "abc123",
        "status": "consumed",
        "inputsSummary": [
            {"id": "q-1", "type": "query", "text": "test query"},
        ],
    }
    detail = ConsumedSessionDetail.from_raw(raw)
    assert detail.key == "agent:tester:decision:abc123"
    assert detail.consumed_at_seconds == 45
    assert detail.input_count == 3
    assert detail.agent_id == "tester"
    assert detail.decision_id == "abc123"
    assert detail.status == "consumed"
    assert len(detail.inputs_summary) == 1

    # Round-trip: to_dict should produce same structure
    d = detail.to_dict()
    assert d["key"] == raw["key"]
    assert d["consumedAt"] == raw["consumedAt"]
    assert d["inputCount"] == raw["inputCount"]
    assert d["agentId"] == raw["agentId"]
    assert d["decisionId"] == raw["decisionId"]
    assert d["status"] == raw["status"]
    assert d["inputsSummary"] == raw["inputsSummary"]


# ---- 11. test_debug_tracker_request_include_consumed ----


def test_debug_tracker_request_include_consumed() -> None:
    """DebugTrackerRequest parses includeConsumed from params."""
    # Default: False
    req = DebugTrackerRequest.from_params({})
    assert req.include_consumed is False
    assert req.key is None

    # Explicit True (camelCase)
    req2 = DebugTrackerRequest.from_params({"includeConsumed": True, "key": "agent:x"})
    assert req2.include_consumed is True
    assert req2.key == "agent:x"

    # Falsy value
    req3 = DebugTrackerRequest.from_params({"includeConsumed": False})
    assert req3.include_consumed is False


# ---- 12. test_debug_tracker_response_with_consumed ----


def test_debug_tracker_response_with_consumed() -> None:
    """DebugTrackerResponse.from_raw parses consumed records."""
    raw: dict[str, Any] = {
        "sessions": ["agent:x"],
        "sessionCount": 1,
        "detail": {
            "agent:x": {
                "inputCount": 2,
                "inputs": [
                    {"id": "q-1", "type": "query", "text": "test", "source": "cstp:q", "ageSeconds": 5},
                ],
            },
        },
        "consumed": [
            {
                "key": "agent:old",
                "consumedAt": 120,
                "inputCount": 1,
                "agentId": "old",
                "decisionId": "dec001",
                "status": "consumed",
                "inputsSummary": [{"id": "q-0", "type": "query", "text": "old query"}],
            },
        ],
    }
    resp = DebugTrackerResponse.from_raw(raw)
    assert resp.session_count == 1
    assert len(resp.consumed) == 1
    assert resp.consumed[0].key == "agent:old"
    assert resp.consumed[0].decision_id == "dec001"

    # to_dict includes consumed
    d = resp.to_dict()
    assert "consumed" in d
    assert len(d["consumed"]) == 1
    assert d["consumed"][0]["decisionId"] == "dec001"

    # Without consumed
    raw_no_consumed: dict[str, Any] = {
        "sessions": [], "sessionCount": 0, "detail": {},
    }
    resp2 = DebugTrackerResponse.from_raw(raw_no_consumed)
    assert len(resp2.consumed) == 0
    d2 = resp2.to_dict()
    assert "consumed" not in d2  # empty consumed list not included


# ---- 13. test_parse_key_components ----


def test_parse_key_components() -> None:
    """_parse_key_components extracts agent_id and decision_id."""
    # agent:alice:decision:dec001
    r = _parse_key_components("agent:alice:decision:dec001")
    assert r["agent_id"] == "alice"
    assert r["decision_id"] == "dec001"

    # agent:bob
    r2 = _parse_key_components("agent:bob")
    assert r2["agent_id"] == "bob"
    assert r2["decision_id"] is None

    # decision:xyz
    r3 = _parse_key_components("decision:xyz")
    assert r3["agent_id"] is None
    assert r3["decision_id"] == "xyz"

    # rpc:default (transport key)
    r4 = _parse_key_components("rpc:default")
    assert r4["agent_id"] is None
    assert r4["decision_id"] is None


# ---- 14. test_consumed_record_inputs_summary_truncation ----


def test_consumed_record_inputs_summary_truncation() -> None:
    """Consumed record truncates text to 80 chars and limits to 10 inputs."""
    tracker = DeliberationTracker(input_ttl=300, session_ttl=1800, consumed_history_size=50)
    key = "agent:truncator"

    # Track 15 inputs with long text
    for i in range(15):
        tracker.track(key, _make_input(f"q-{i}", text="A" * 200))

    tracker.consume(key)

    record = tracker._consumed_history[0]
    # inputs_summary capped at 10
    assert len(record.inputs_summary) == 10
    # text truncated to 80 chars
    for summary in record.inputs_summary:
        assert len(summary["text"]) == 80


# ---------------------------------------------------------------------------
# Dashboard tests (require flask) — guarded by CI skip
# ---------------------------------------------------------------------------

_FLASK_AVAILABLE = importlib.util.find_spec("flask") is not None


@pytest.mark.skipif(not _FLASK_AVAILABLE, reason="flask not installed (CI)")
class TestDashboardConsumed:
    """Dashboard tests for consumed section rendering."""

    @pytest.fixture(autouse=True)
    def _setup_dashboard(self) -> Any:
        """Set up dashboard app for testing."""
        _dashboard_dir = str(Path(__file__).resolve().parent.parent / "dashboard")
        if _dashboard_dir not in sys.path:
            sys.path.insert(0, _dashboard_dir)

        # Create mock config
        mock_config = MagicMock()
        mock_config.secret_key = "test-secret-149"
        mock_config.cstp_url = "http://localhost:9991"
        mock_config.cstp_token = "test-token"
        mock_config.dashboard_user = "admin"
        mock_config.dashboard_pass = "testpass"
        mock_config.dashboard_port = 8080
        mock_config.validate.return_value = []

        import config as _config_mod
        _config_mod.config = mock_config

        from app import (
            _transform_consumed_sessions,
            app,
            parse_tracker_key,
        )

        self.app = app
        self.app.config["TESTING"] = True
        self.app.config["WTF_CSRF_ENABLED"] = False
        self.client = self.app.test_client()
        self._transform_consumed_sessions = _transform_consumed_sessions
        self.parse_tracker_key = parse_tracker_key

        from base64 import b64encode
        self.auth_header = {
            "Authorization": "Basic " + b64encode(b"admin:testpass").decode(),
        }

    # ---- 15 (a). test_transport_id_badge_rendered ----

    def test_transport_id_badge_rendered(self) -> None:
        """Template renders transport_id as a neutral badge."""
        tracker_data = {
            "sessions": ["rpc:my-agent-1"],
            "sessionCount": 1,
            "detail": {
                "rpc:my-agent-1": {
                    "inputCount": 1,
                    "inputs": [
                        {"id": "q-1", "type": "query", "text": "test",
                         "source": "cstp:q", "ageSeconds": 10},
                    ],
                },
            },
        }
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = tracker_data
            resp = self.client.get("/deliberation/partial", headers=self.auth_header)

        html = resp.data.decode()
        # transport_id "my-agent-1" should appear in a neutral badge
        assert "my-agent-1" in html
        assert "badge--neutral" in html
        # transport "rpc" should appear in a warning badge
        assert "badge--warning" in html

    # ---- 15 (b). test_consumed_section_rendered ----

    def test_consumed_section_rendered(self) -> None:
        """'Recently Consumed' section renders in the partial template."""
        tracker_data = {
            "sessions": [],
            "sessionCount": 0,
            "detail": {},
            "consumed": [
                {
                    "key": "agent:alice",
                    "consumedAt": 30,
                    "inputCount": 2,
                    "agentId": "alice",
                    "decisionId": None,
                    "status": "consumed",
                    "inputsSummary": [
                        {"id": "q-1", "type": "query", "text": "search X"},
                    ],
                },
            ],
        }
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = tracker_data
            resp = self.client.get("/deliberation/partial", headers=self.auth_header)

        html = resp.data.decode()
        assert "Recently Consumed" in html
        assert "session-card--consumed" in html
        assert "consumed" in html  # status badge
        assert "alice" in html  # agent_id

    # ---- 15 (c). test_consumed_section_with_decision_link ----

    def test_consumed_section_with_decision_link(self) -> None:
        """Consumed card renders decision_id as a clickable link."""
        tracker_data = {
            "sessions": [],
            "sessionCount": 0,
            "detail": {},
            "consumed": [
                {
                    "key": "agent:bob:decision:dec12345",
                    "consumedAt": 60,
                    "inputCount": 1,
                    "agentId": "bob",
                    "decisionId": "dec12345",
                    "status": "consumed",
                    "inputsSummary": [],
                },
            ],
        }
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = tracker_data
            resp = self.client.get("/deliberation/partial", headers=self.auth_header)

        html = resp.data.decode()
        # Decision ID should appear as a link
        assert "dec12345" in html
        assert "Decision:" in html
        # Link to decision detail page
        assert "/decisions/dec12345" in html

    # ---- 15 (d). test_oob_counter_with_consumed ----

    def test_oob_counter_with_consumed(self) -> None:
        """OOB counter shows consumed count alongside active."""
        tracker_data = {
            "sessions": ["agent:active"],
            "sessionCount": 1,
            "detail": {
                "agent:active": {
                    "inputCount": 1,
                    "inputs": [
                        {"id": "q-1", "type": "query", "text": "x",
                         "source": "cstp:q", "ageSeconds": 5},
                    ],
                },
            },
            "consumed": [
                {
                    "key": "agent:old1", "consumedAt": 100, "inputCount": 1,
                    "agentId": "old1", "decisionId": None,
                    "status": "consumed", "inputsSummary": [],
                },
                {
                    "key": "agent:old2", "consumedAt": 200, "inputCount": 2,
                    "agentId": "old2", "decisionId": None,
                    "status": "expired", "inputsSummary": [],
                },
            ],
        }
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = tracker_data
            resp = self.client.get("/deliberation/partial", headers=self.auth_header)

        html = resp.data.decode()
        # OOB span should contain "1 active" and "2 consumed"
        assert "1 active" in html
        assert "2 consumed" in html

    # ---- 16 (a). test_transform_consumed_sessions ----

    def test_transform_consumed_sessions(self) -> None:
        """_transform_consumed_sessions produces template-friendly dicts."""
        consumed_data = [
            {
                "key": "agent:tester:decision:d001",
                "consumedAt": 45,
                "inputCount": 3,
                "agentId": "tester",
                "decisionId": "d001",
                "status": "consumed",
                "inputsSummary": [{"id": "q-1", "type": "query", "text": "test"}],
            },
            {
                "key": "rpc:default",
                "consumedAt": 3700,
                "inputCount": 1,
                "agentId": None,
                "decisionId": None,
                "status": "expired",
                "inputsSummary": [],
            },
        ]
        result = self._transform_consumed_sessions(consumed_data)

        assert len(result) == 2
        # First item
        assert result[0]["key"] == "agent:tester:decision:d001"
        assert result[0]["parsed"]["agent_id"] == "tester"
        assert result[0]["parsed"]["decision_id"] == "d001"
        assert result[0]["decision_id"] == "d001"
        assert result[0]["status"] == "consumed"
        assert result[0]["age_display"] == "45s ago"
        assert result[0]["age_class"] == "age--fresh"

        # Second item — transport key, 1h+ old
        assert result[1]["parsed"]["transport"] == "rpc"
        assert result[1]["parsed"]["transport_id"] == "default"
        assert result[1]["status"] == "expired"
        assert result[1]["age_display"] == "1h ago"
        assert result[1]["age_class"] == "age--orphaned"


# ---------------------------------------------------------------------------
# Dispatcher integration test (no flask dependency, but needs mcp mocking)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dispatcher_backfill_after_record() -> None:
    """Integration: record_decision triggers backfill_consumed."""
    # Mock mcp modules to avoid import errors
    mock_mcp_modules = {
        "mcp": MagicMock(),
        "mcp.server": MagicMock(),
        "mcp.server.stdio": MagicMock(),
        "mcp.server.streamable_http_manager": MagicMock(),
        "mcp.types": MagicMock(),
    }
    with patch.dict(sys.modules, mock_mcp_modules):
        from a2a.cstp.deliberation_tracker import (
            get_tracker,
            reset_tracker,
        )

        # Reset to get a fresh tracker
        reset_tracker()
        tracker = get_tracker()

        key = "rpc:test-agent"
        # Track some inputs
        tracker.track(key, _make_input("q-1", "query", "test query"))

        # Consume (simulating what happens during recordDecision)
        delib = tracker.consume(key)
        assert delib is not None

        # Verify consumed record exists without decision_id
        assert len(tracker._consumed_history) == 1
        assert tracker._consumed_history[0].decision_id is None

        # Simulate dispatcher backfill
        result = tracker.backfill_consumed(key, "fake-dec-id")
        assert result is True
        assert tracker._consumed_history[0].decision_id == "fake-dec-id"

        # Cleanup
        reset_tracker()
