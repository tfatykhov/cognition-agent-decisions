"""Tests for issue #159: pre_action deliberation tracking.

Verifies that pre_action injects track_query/track_guardrail calls
and uses the correct tracker_key for both RPC and MCP transports.
"""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.deliberation_tracker import get_tracker, reset_tracker
from a2a.cstp.models import PreActionRequest


# ---------------------------------------------------------------------------
# Mock helpers (reused from test_f046_pre_action.py)
# ---------------------------------------------------------------------------


@dataclass
class MockQueryResult:
    id: str = "abc12345"
    title: str = "Test decision"
    category: str = "architecture"
    confidence: float = 0.8
    stakes: str = "medium"
    status: str = "reviewed"
    outcome: str = "success"
    date: str = "2026-01-15"
    distance: float = 0.12
    reason_types: list[str] | None = None
    tags: list[str] | None = None
    pattern: str | None = None
    lessons: str | None = None
    actual_result: str | None = None
    reasons: list[dict[str, str]] | None = None
    bridge: dict[str, str] | None = None


@dataclass
class MockQueryResponse:
    results: list[MockQueryResult] = field(default_factory=list)
    query: str = "test"
    query_time_ms: int = 10
    error: str | None = None


@dataclass
class MockGuardrailResult:
    guardrail_id: str
    name: str
    message: str
    severity: str
    suggestion: str | None = None


@dataclass
class MockEvalResult:
    allowed: bool = True
    violations: list[MockGuardrailResult] = field(default_factory=list)
    warnings: list[MockGuardrailResult] = field(default_factory=list)
    evaluated: int = 3


@dataclass
class MockCalibrationOverall:
    brier_score: float = 0.05
    accuracy: float = 0.90
    calibration_gap: float = -0.02
    interpretation: str = "well_calibrated"
    reviewed_decisions: int = 15
    total_decisions: int = 20


@dataclass
class MockCalibrationResponse:
    overall: MockCalibrationOverall | None = field(
        default_factory=MockCalibrationOverall,
    )
    by_confidence_bucket: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    confidence_stats: None = None
    query_time: str = "2026-01-15T00:00:00"


@dataclass
class MockRecordResponse:
    success: bool = True
    id: str = "new12345"
    path: str = "decisions/2026/02/test.yaml"
    indexed: bool = True
    timestamp: str = "2026-02-14T00:00:00"
    error: str | None = None
    quality: dict | None = None
    guardrail_warnings: list | None = None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPreActionDeliberationTracking:
    """Issue #159: pre_action must track query and guardrail calls."""

    @pytest.fixture(autouse=True)
    def _reset_tracker(self) -> None:
        reset_tracker()

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_tracks_query_under_rpc_key(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """pre_action with default tracker_key should track under rpc:{agent_id}."""
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult()],
        )
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Test tracking", "category": "architecture"},
            "options": {"autoRecord": False},
        })
        await pre_action(req, agent_id="test-agent")

        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:test-agent")
        assert len(inputs) >= 2, f"Expected >=2 tracked inputs, got {len(inputs)}"

        types = [i.type for i in inputs]
        assert "query" in types, "Expected a 'query' tracked input"
        assert "guardrail" in types, "Expected a 'guardrail' tracked input"

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_tracks_under_mcp_key(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """pre_action with mcp: tracker_key should track under mcp:{agent_id}."""
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult()],
        )
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "MCP tracking test", "category": "architecture"},
            "options": {"autoRecord": False},
        })
        await pre_action(req, agent_id="mcp-client", tracker_key="mcp:mcp-client")

        tracker = get_tracker()

        # Should be tracked under mcp: key
        mcp_inputs = tracker.get_inputs("mcp:mcp-client")
        assert len(mcp_inputs) >= 2, f"Expected >=2 inputs under mcp: key, got {len(mcp_inputs)}"

        # Should NOT be tracked under rpc: key
        rpc_inputs = tracker.get_inputs("rpc:mcp-client")
        assert len(rpc_inputs) == 0, "Should not have inputs under rpc: key"

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_auto_record_consumes_tracked_inputs(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """auto_record should consume tracked inputs from the correct key."""
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult()],
        )
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse(success=True, id="new12345")

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {
                "description": "Auto-record with mcp key",
                "category": "architecture",
                "confidence": 0.85,
            },
        })
        resp = await pre_action(
            req, agent_id="mcp-client", tracker_key="mcp:mcp-client",
        )

        assert resp.decision_id == "new12345"

        # After auto_record, tracked inputs should be consumed
        tracker = get_tracker()
        remaining = tracker.get_inputs("mcp:mcp-client")
        assert len(remaining) == 0, "Inputs should be consumed after auto_record"

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_no_tracking_on_query_failure(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
    ) -> None:
        """If query fails, should not track a query input."""
        mock_query.side_effect = RuntimeError("ChromaDB down")
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Test failure handling"},
            "options": {"autoRecord": False},
        })
        await pre_action(req, agent_id="test-agent")

        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:test-agent")
        types = [i.type for i in inputs]
        assert "query" not in types, "Should not track query on failure"
        # Guardrail should still be tracked
        assert "guardrail" in types

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_no_guardrail_tracking_on_guardrail_failure(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
    ) -> None:
        """If guardrail eval fails, should not track a guardrail input."""
        mock_query.return_value = MockQueryResponse(results=[MockQueryResult()])
        mock_guard.side_effect = RuntimeError("Guardrails error")
        mock_cal.return_value = MockCalibrationResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Test guardrail failure"},
            "options": {"autoRecord": False},
        })
        await pre_action(req, agent_id="test-agent")

        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:test-agent")
        types = [i.type for i in inputs]
        assert "guardrail" not in types, "Should not track guardrail on failure"
        # Query should still be tracked
        assert "query" in types

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_query_error_response_not_tracked(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
    ) -> None:
        """If query returns an error (not exception), should not track."""
        mock_query.return_value = MockQueryResponse(error="Index not ready")
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Test query error"},
            "options": {"autoRecord": False},
        })
        await pre_action(req, agent_id="test-agent")

        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:test-agent")
        types = [i.type for i in inputs]
        assert "query" not in types, "Should not track query when error is returned"

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.record_decision")
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    @patch("a2a.cstp.preaction_service.log_guardrail_check")
    async def test_tracker_key_defaults_to_rpc(
        self,
        mock_log: AsyncMock,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
        mock_record: AsyncMock,
    ) -> None:
        """When tracker_key is not passed, it should default to rpc:{agent_id}."""
        mock_query.return_value = MockQueryResponse(results=[MockQueryResult()])
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()
        mock_record.return_value = MockRecordResponse()

        from a2a.cstp.preaction_service import pre_action

        req = PreActionRequest.from_params({
            "action": {"description": "Default key test"},
            "options": {"autoRecord": False},
        })
        # Call without explicit tracker_key
        await pre_action(req, agent_id="my-agent")

        tracker = get_tracker()
        inputs = tracker.get_inputs("rpc:my-agent")
        assert len(inputs) >= 2, "Should track under rpc: key by default"
