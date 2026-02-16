"""Tests for F049: Deliberation Tracker Viewer.

Tests cover:
- parse_tracker_key() — composite key parsing for all formats
- _format_age() — human-readable age formatting
- _age_freshness_class() — CSS class thresholds
- _transform_tracker_sessions() — API response → template data
- GET /deliberation — full page route
- GET /deliberation/partial — HTMX partial route
- Auth enforcement on /deliberation
"""

import sys
from base64 import b64encode
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Add dashboard/ to sys.path so its modules can be imported
_dashboard_dir = str(Path(__file__).resolve().parent.parent / "dashboard")
if _dashboard_dir not in sys.path:
    sys.path.insert(0, _dashboard_dir)

# Must patch config/cstp_client BEFORE importing app, because app.py
# reads config at module level and creates a CSTPClient instance.
_mock_config = MagicMock()
_mock_config.secret_key = "test-secret"
_mock_config.cstp_url = "http://localhost:9991"
_mock_config.cstp_token = "test-token"
_mock_config.dashboard_user = "admin"
_mock_config.dashboard_pass = "testpass"
_mock_config.dashboard_port = 8080
_mock_config.validate.return_value = []

with patch.dict(sys.modules, {}):
    pass  # ensure clean state

# Patch the config module before importing app
import config as _config_mod  # noqa: E402

_orig_config = _config_mod.config
_config_mod.config = _mock_config

from app import (  # noqa: E402
    _age_freshness_class,
    _format_age,
    _transform_tracker_sessions,
    app,
    parse_tracker_key,
)

# Restore original config after import (app already captured the mock)
_config_mod.config = _orig_config


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    """Flask test client with WTF_CSRF disabled."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def _auth_headers() -> dict[str, str]:
    """Return Basic Auth headers matching mock config."""
    creds = b64encode(b"admin:testpass").decode()
    return {"Authorization": f"Basic {creds}"}


def _sample_tracker_data() -> dict[str, Any]:
    """Return sample debugTracker response for testing."""
    return {
        "sessions": [
            "agent:planner:decision:abc12345",
            "agent:tester",
            "mcp:default",
        ],
        "sessionCount": 3,
        "detail": {
            "agent:planner:decision:abc12345": {
                "inputCount": 2,
                "inputs": [
                    {
                        "type": "thought",
                        "text": "Analyzing requirements",
                        "ageSeconds": 10,
                    },
                    {
                        "type": "input",
                        "text": "Read spec doc",
                        "ageSeconds": 45,
                    },
                ],
            },
            "agent:tester": {
                "inputCount": 1,
                "inputs": [
                    {
                        "type": "thought",
                        "text": "Writing tests",
                        "ageSeconds": 200,
                    },
                ],
            },
            "mcp:default": {
                "inputCount": 0,
                "inputs": [],
            },
        },
    }


# ---------------------------------------------------------------------------
# parse_tracker_key tests
# ---------------------------------------------------------------------------

class TestParseTrackerKey:
    """Tests for parse_tracker_key() — all composite key formats."""

    def test_agent_and_decision(self) -> None:
        result = parse_tracker_key("agent:planner:decision:abc123")
        assert result["agent_id"] == "planner"
        assert result["decision_id"] == "abc123"
        assert result["transport"] is None
        assert result["transport_id"] is None
        assert result["raw"] == "agent:planner:decision:abc123"

    def test_agent_only(self) -> None:
        result = parse_tracker_key("agent:planner")
        assert result["agent_id"] == "planner"
        assert result["decision_id"] is None
        assert result["transport"] is None

    def test_decision_only(self) -> None:
        result = parse_tracker_key("decision:abc123")
        assert result["agent_id"] is None
        assert result["decision_id"] == "abc123"
        assert result["transport"] is None

    def test_rpc_transport(self) -> None:
        result = parse_tracker_key("rpc:myagent")
        assert result["transport"] == "rpc"
        assert result["transport_id"] == "myagent"
        assert result["agent_id"] is None
        assert result["decision_id"] is None

    def test_bare_key_no_colon(self) -> None:
        result = parse_tracker_key("mcp-session")
        assert result["agent_id"] is None
        assert result["decision_id"] is None
        assert result["transport"] is None
        assert result["transport_id"] is None
        assert result["raw"] == "mcp-session"

    def test_mcp_transport(self) -> None:
        result = parse_tracker_key("mcp:default")
        assert result["transport"] == "mcp"
        assert result["transport_id"] == "default"
        assert result["agent_id"] is None
        assert result["decision_id"] is None


# ---------------------------------------------------------------------------
# _format_age tests
# ---------------------------------------------------------------------------

class TestFormatAge:
    """Tests for _format_age() — seconds to human-readable string."""

    def test_zero_seconds(self) -> None:
        assert _format_age(0) == "0s ago"

    def test_seconds_range(self) -> None:
        assert _format_age(45) == "45s ago"

    def test_boundary_59_seconds(self) -> None:
        assert _format_age(59) == "59s ago"

    def test_one_minute(self) -> None:
        assert _format_age(60) == "1m ago"

    def test_minutes_range(self) -> None:
        assert _format_age(150) == "2m ago"

    def test_boundary_59_minutes(self) -> None:
        assert _format_age(3599) == "59m ago"

    def test_one_hour(self) -> None:
        assert _format_age(3600) == "1h ago"

    def test_hours_range(self) -> None:
        assert _format_age(7200) == "2h ago"


# ---------------------------------------------------------------------------
# _age_freshness_class tests
# ---------------------------------------------------------------------------

class TestAgeFreshnessClass:
    """Tests for _age_freshness_class() — CSS class thresholds."""

    def test_zero_is_fresh(self) -> None:
        assert _age_freshness_class(0) == "age--fresh"

    def test_29_is_fresh(self) -> None:
        assert _age_freshness_class(29) == "age--fresh"

    def test_30_is_recent(self) -> None:
        assert _age_freshness_class(30) == "age--recent"

    def test_119_is_recent(self) -> None:
        assert _age_freshness_class(119) == "age--recent"

    def test_120_is_stale(self) -> None:
        assert _age_freshness_class(120) == "age--stale"

    def test_large_value_is_stale(self) -> None:
        assert _age_freshness_class(9999) == "age--stale"


# ---------------------------------------------------------------------------
# _transform_tracker_sessions tests
# ---------------------------------------------------------------------------

class TestTransformTrackerSessions:
    """Tests for _transform_tracker_sessions() — API → template data."""

    def test_transforms_full_response(self) -> None:
        data = _sample_tracker_data()
        sessions = _transform_tracker_sessions(data)

        assert len(sessions) == 3

        # First session: agent:planner:decision:abc12345
        s0 = sessions[0]
        assert s0["key"] == "agent:planner:decision:abc12345"
        assert s0["parsed"]["agent_id"] == "planner"
        assert s0["parsed"]["decision_id"] == "abc12345"
        assert s0["input_count"] == 2
        assert len(s0["inputs"]) == 2
        assert s0["inputs"][0]["age_display"] == "10s ago"
        assert s0["inputs"][0]["age_class"] == "age--fresh"
        assert s0["inputs"][1]["age_display"] == "45s ago"
        assert s0["inputs"][1]["age_class"] == "age--recent"

        # Second session: agent:tester
        s1 = sessions[1]
        assert s1["parsed"]["agent_id"] == "tester"
        assert s1["parsed"]["decision_id"] is None
        assert s1["inputs"][0]["age_class"] == "age--stale"

        # Third session: mcp:default (empty inputs)
        s2 = sessions[2]
        assert s2["parsed"]["transport"] == "mcp"
        assert s2["input_count"] == 0
        assert s2["inputs"] == []

    def test_empty_response(self) -> None:
        data: dict[str, Any] = {"sessions": [], "sessionCount": 0, "detail": {}}
        sessions = _transform_tracker_sessions(data)
        assert sessions == []

    def test_session_without_detail(self) -> None:
        """Session key exists in sessions list but not in detail."""
        data: dict[str, Any] = {
            "sessions": ["agent:ghost"],
            "sessionCount": 1,
            "detail": {},
        }
        sessions = _transform_tracker_sessions(data)
        assert len(sessions) == 1
        assert sessions[0]["input_count"] == 0
        assert sessions[0]["inputs"] == []


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------

class TestDeliberationRoute:
    """Tests for GET /deliberation (full page)."""

    def test_returns_200_with_data(self, client) -> None:
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = _sample_tracker_data()
            resp = client.get("/deliberation", headers=_auth_headers())

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "Deliberation Tracker" in html
        assert "3 active" in html

    def test_returns_200_empty_state(self, client) -> None:
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = {
                "sessions": [],
                "sessionCount": 0,
                "detail": {},
            }
            resp = client.get("/deliberation", headers=_auth_headers())

        assert resp.status_code == 200
        html = resp.data.decode()
        assert "0 active" in html
        assert "No active deliberation sessions" in html

    def test_passes_filter_key(self, client) -> None:
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = {
                "sessions": ["agent:test"],
                "sessionCount": 1,
                "detail": {
                    "agent:test": {"inputCount": 0, "inputs": []},
                },
            }
            resp = client.get(
                "/deliberation?key=agent:test", headers=_auth_headers()
            )

        assert resp.status_code == 200
        # Verify the filter key was passed to the CSTP client
        mock_cstp.debug_tracker.assert_called_once_with(key="agent:test")

    def test_handles_cstp_error(self, client) -> None:
        from cstp_client import CSTPError

        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.side_effect = CSTPError("connection refused")
            resp = client.get("/deliberation", headers=_auth_headers())

        # Should still return 200 with empty state (error flashed)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "0 active" in html


class TestDeliberationPartialRoute:
    """Tests for GET /deliberation/partial (HTMX partial)."""

    def test_returns_200(self, client) -> None:
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = _sample_tracker_data()
            resp = client.get("/deliberation/partial", headers=_auth_headers())

        assert resp.status_code == 200
        html = resp.data.decode()
        # Partial should contain session data but NOT the full page wrapper
        assert "3 active" in html

    def test_partial_with_filter(self, client) -> None:
        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.return_value = {
                "sessions": [],
                "sessionCount": 0,
                "detail": {},
            }
            resp = client.get(
                "/deliberation/partial?key=agent:x", headers=_auth_headers()
            )

        assert resp.status_code == 200
        mock_cstp.debug_tracker.assert_called_once_with(key="agent:x")

    def test_partial_handles_cstp_error(self, client) -> None:
        from cstp_client import CSTPError

        with patch("app.cstp") as mock_cstp:
            mock_cstp.debug_tracker.side_effect = CSTPError("timeout")
            resp = client.get("/deliberation/partial", headers=_auth_headers())

        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Auth test
# ---------------------------------------------------------------------------

class TestDeliberationAuth:
    """Tests for authentication on deliberation routes."""

    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/deliberation")
        assert resp.status_code == 401

    def test_wrong_credentials_returns_401(self, client) -> None:
        bad_creds = b64encode(b"admin:wrongpass").decode()
        headers = {"Authorization": f"Basic {bad_creds}"}
        resp = client.get("/deliberation", headers=headers)
        assert resp.status_code == 401

    def test_partial_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/deliberation/partial")
        assert resp.status_code == 401
