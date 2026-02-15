"""Tests for F044: Agent Work Discovery (cstp.ready)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.models import ReadyAction, ReadyRequest, ReadyResponse
from a2a.cstp.ready_service import (
    _detect_review_outcome_actions,
    _detect_stale_pending_actions,
    get_ready_actions,
)
from a2a.models.jsonrpc import JsonRpcRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _days_ago(n: int) -> str:
    """Return ISO date string for n days ago."""
    return (datetime.now(UTC) - timedelta(days=n)).strftime("%Y-%m-%d")


def _make_decision(**overrides: Any) -> dict[str, Any]:
    """Build a minimal decision dict with overrides."""
    base: dict[str, Any] = {
        "id": "abc12345",
        "decision": "Test decision",
        "status": "pending",
        "category": "architecture",
        "stakes": "medium",
        "date": _days_ago(7),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestReadyRequest:
    def test_from_params_defaults(self) -> None:
        req = ReadyRequest.from_params({})
        assert req.min_priority == "low"
        assert req.action_types == []
        assert req.limit == 20
        assert req.category is None

    def test_from_params_custom(self) -> None:
        req = ReadyRequest.from_params({
            "minPriority": "high",
            "actionTypes": ["review_outcome", "calibration_drift"],
            "limit": 10,
            "category": "tooling",
        })
        assert req.min_priority == "high"
        assert req.action_types == ["review_outcome", "calibration_drift"]
        assert req.limit == 10
        assert req.category == "tooling"

    def test_from_params_snake_case(self) -> None:
        req = ReadyRequest.from_params({
            "min_priority": "medium",
            "action_types": ["stale_pending"],
        })
        assert req.min_priority == "medium"
        assert req.action_types == ["stale_pending"]

    def test_from_params_clamps_limit(self) -> None:
        assert ReadyRequest.from_params({"limit": 999}).limit == 50
        assert ReadyRequest.from_params({"limit": -5}).limit == 1

    def test_from_params_invalid_priority(self) -> None:
        req = ReadyRequest.from_params({"minPriority": "critical"})
        assert req.min_priority == "low"


class TestReadyAction:
    def test_to_dict_full(self) -> None:
        action = ReadyAction(
            type="review_outcome",
            priority="high",
            reason="Overdue review",
            suggestion="Record outcome",
            decision_id="abc123",
            category="tooling",
            date="2025-01-01",
            title="Fix bug",
            detail="7d overdue",
        )
        data = action.to_dict()
        assert data["type"] == "review_outcome"
        assert data["priority"] == "high"
        assert data["reason"] == "Overdue review"
        assert data["suggestion"] == "Record outcome"
        assert data["decisionId"] == "abc123"
        assert data["category"] == "tooling"
        assert data["date"] == "2025-01-01"
        assert data["title"] == "Fix bug"
        assert data["detail"] == "7d overdue"

    def test_to_dict_minimal(self) -> None:
        action = ReadyAction(
            type="calibration_drift",
            priority="medium",
            reason="Drift detected",
            suggestion="Review decisions",
        )
        data = action.to_dict()
        assert data["type"] == "calibration_drift"
        assert "decisionId" not in data
        assert "category" not in data
        assert "date" not in data


class TestReadyResponse:
    def test_to_dict(self) -> None:
        resp = ReadyResponse(
            actions=[
                ReadyAction(
                    type="review_outcome", priority="high",
                    reason="Overdue", suggestion="Review",
                    decision_id="abc",
                ),
            ],
            total=3,
            filtered=2,
        )
        data = resp.to_dict()
        assert data["total"] == 3
        assert data["filtered"] == 2
        assert len(data["actions"]) == 1
        assert data["actions"][0]["type"] == "review_outcome"

    def test_to_dict_empty(self) -> None:
        resp = ReadyResponse(actions=[], total=0)
        data = resp.to_dict()
        assert data["actions"] == []
        assert data["total"] == 0
        assert data["filtered"] == 0


# ---------------------------------------------------------------------------
# Detector tests: review_outcome
# ---------------------------------------------------------------------------


class TestDetectReviewOutcome:
    def test_overdue_high_stakes(self) -> None:
        decisions = [_make_decision(
            review_by=_days_ago(3), stakes="high",
        )]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 1
        assert actions[0].type == "review_outcome"
        assert actions[0].priority == "high"
        assert actions[0].decision_id == "abc12345"

    def test_overdue_critical_stakes(self) -> None:
        decisions = [_make_decision(
            review_by=_days_ago(1), stakes="critical",
        )]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 1
        assert actions[0].priority == "high"

    def test_overdue_medium_stakes(self) -> None:
        decisions = [_make_decision(
            review_by=_days_ago(2), stakes="medium",
        )]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 1
        assert actions[0].priority == "medium"

    def test_overdue_low_stakes(self) -> None:
        decisions = [_make_decision(
            review_by=_days_ago(5), stakes="low",
        )]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 1
        assert actions[0].priority == "low"

    def test_future_review_by_skipped(self) -> None:
        tomorrow = (datetime.now(UTC) + timedelta(days=1)).strftime("%Y-%m-%d")
        decisions = [_make_decision(review_by=tomorrow)]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 0

    def test_no_review_by_skipped(self) -> None:
        decisions = [_make_decision()]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 0

    def test_reviewed_status_skipped(self) -> None:
        decisions = [_make_decision(
            status="reviewed", review_by=_days_ago(1),
        )]
        actions = _detect_review_outcome_actions(decisions)
        assert len(actions) == 0

    def test_empty_decisions(self) -> None:
        assert _detect_review_outcome_actions([]) == []


# ---------------------------------------------------------------------------
# Detector tests: stale_pending
# ---------------------------------------------------------------------------


class TestDetectStalePending:
    def test_medium_priority_35_days(self) -> None:
        decisions = [_make_decision(date=_days_ago(35))]
        actions = _detect_stale_pending_actions(decisions)
        assert len(actions) == 1
        assert actions[0].type == "stale_pending"
        assert actions[0].priority == "medium"

    def test_high_priority_70_days(self) -> None:
        decisions = [_make_decision(date=_days_ago(70))]
        actions = _detect_stale_pending_actions(decisions)
        assert len(actions) == 1
        assert actions[0].priority == "high"

    def test_recent_decision_skipped(self) -> None:
        """Decisions younger than 30d are not stale."""
        decisions = [_make_decision(date=_days_ago(10))]
        actions = _detect_stale_pending_actions(decisions)
        assert len(actions) == 0

    def test_has_review_by_skipped(self) -> None:
        """Decisions with review_by are handled by review_outcome detector."""
        decisions = [_make_decision(
            date=_days_ago(40), review_by=_days_ago(5),
        )]
        actions = _detect_stale_pending_actions(decisions)
        assert len(actions) == 0

    def test_reviewed_status_skipped(self) -> None:
        decisions = [_make_decision(date=_days_ago(40), status="reviewed")]
        actions = _detect_stale_pending_actions(decisions)
        assert len(actions) == 0

    def test_empty_decisions(self) -> None:
        assert _detect_stale_pending_actions([]) == []

    def test_days_old_in_detail(self) -> None:
        decisions = [_make_decision(date=_days_ago(45))]
        actions = _detect_stale_pending_actions(decisions)
        assert "45 days" in actions[0].detail


# ---------------------------------------------------------------------------
# Service tests: get_ready_actions
# ---------------------------------------------------------------------------


class TestGetReadyActions:
    @pytest.mark.asyncio
    async def test_empty_decisions(self) -> None:
        request = ReadyRequest()
        response = await get_ready_actions(request, preloaded_decisions=[])
        assert response.total == 0
        assert response.actions == []

    @pytest.mark.asyncio
    async def test_preloaded_decisions_skips_load(self) -> None:
        """When preloaded_decisions is passed, load_all_decisions is not called."""
        decisions = [_make_decision(review_by=_days_ago(1))]
        with patch("a2a.cstp.ready_service.load_all_decisions") as mock_load:
            response = await get_ready_actions(
                ReadyRequest(action_types=["review_outcome"]),
                preloaded_decisions=decisions,
            )
            mock_load.assert_not_called()
            assert len(response.actions) == 1

    @pytest.mark.asyncio
    async def test_loads_decisions_when_not_preloaded(self) -> None:
        with patch(
            "a2a.cstp.ready_service.load_all_decisions",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_load:
            await get_ready_actions(ReadyRequest())
            mock_load.assert_called_once()

    @pytest.mark.asyncio
    async def test_filter_by_min_priority(self) -> None:
        decisions = [
            _make_decision(id="high1", review_by=_days_ago(1), stakes="high"),
            _make_decision(id="med1", review_by=_days_ago(1), stakes="medium"),
            _make_decision(id="low1", review_by=_days_ago(1), stakes="low"),
        ]
        request = ReadyRequest(
            min_priority="medium",
            action_types=["review_outcome"],
        )
        response = await get_ready_actions(request, preloaded_decisions=decisions)
        assert response.total == 3
        assert len(response.actions) == 2
        assert response.filtered == 1
        priorities = {a.priority for a in response.actions}
        assert "low" not in priorities

    @pytest.mark.asyncio
    async def test_filter_by_action_types(self) -> None:
        decisions = [
            _make_decision(id="review1", review_by=_days_ago(1)),
            _make_decision(id="stale1", date=_days_ago(40)),
        ]
        request = ReadyRequest(action_types=["review_outcome"])
        response = await get_ready_actions(request, preloaded_decisions=decisions)
        assert len(response.actions) == 1
        assert response.actions[0].type == "review_outcome"

    @pytest.mark.asyncio
    async def test_filter_by_category(self) -> None:
        decisions = [
            _make_decision(id="arch1", review_by=_days_ago(1), category="architecture"),
            _make_decision(id="tool1", review_by=_days_ago(1), category="tooling"),
        ]
        request = ReadyRequest(
            category="tooling",
            action_types=["review_outcome"],
        )
        response = await get_ready_actions(request, preloaded_decisions=decisions)
        assert len(response.actions) == 1
        assert response.actions[0].decision_id == "tool1"

    @pytest.mark.asyncio
    async def test_sorted_by_priority_then_date(self) -> None:
        decisions = [
            _make_decision(
                id="low_old", review_by=_days_ago(1), stakes="low", date=_days_ago(50),
            ),
            _make_decision(
                id="high_new", review_by=_days_ago(1), stakes="high", date=_days_ago(5),
            ),
            _make_decision(
                id="high_old", review_by=_days_ago(1), stakes="high", date=_days_ago(30),
            ),
        ]
        request = ReadyRequest(action_types=["review_outcome"])
        response = await get_ready_actions(request, preloaded_decisions=decisions)
        ids = [a.decision_id for a in response.actions]
        # High priority first (oldest date first within same priority)
        assert ids[0] == "high_old"
        assert ids[1] == "high_new"
        assert ids[2] == "low_old"

    @pytest.mark.asyncio
    async def test_limit_applied(self) -> None:
        decisions = [
            _make_decision(id=f"d{i}", review_by=_days_ago(1))
            for i in range(10)
        ]
        request = ReadyRequest(
            limit=3, action_types=["review_outcome"],
        )
        response = await get_ready_actions(request, preloaded_decisions=decisions)
        assert response.total == 10
        assert len(response.actions) == 3


# ---------------------------------------------------------------------------
# Drift detection tests
# ---------------------------------------------------------------------------


class TestDetectDriftActions:
    @pytest.mark.asyncio
    async def test_drift_detected(self) -> None:
        from a2a.cstp.drift_service import CheckDriftResponse, DriftAlert, WindowStats

        mock_response = CheckDriftResponse(
            drift_detected=True,
            recent=WindowStats("30d", 0.25, 0.6, 10),
            historical=WindowStats("90d+", 0.15, 0.8, 30),
            alerts=[DriftAlert(
                type="brier_degradation",
                category="tooling",
                recent_value=0.25,
                historical_value=0.15,
                change_pct=66.7,
                severity="error",
                message="Tooling decisions: Brier score degraded 67%",
            )],
        )

        decisions = [
            _make_decision(status="reviewed", category="tooling"),
        ]

        with patch(
            "a2a.cstp.ready_service.check_drift",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            from a2a.cstp.ready_service import _detect_drift_actions
            actions = await _detect_drift_actions(decisions)

        assert len(actions) == 1
        assert actions[0].type == "calibration_drift"
        assert actions[0].priority == "high"  # 66.7% > 40%
        assert actions[0].category == "tooling"

    @pytest.mark.asyncio
    async def test_no_drift(self) -> None:
        from a2a.cstp.drift_service import CheckDriftResponse

        mock_response = CheckDriftResponse(
            drift_detected=False, recent=None, historical=None,
        )

        decisions = [
            _make_decision(status="reviewed", category="tooling"),
        ]

        with patch(
            "a2a.cstp.ready_service.check_drift",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            from a2a.cstp.ready_service import _detect_drift_actions
            actions = await _detect_drift_actions(decisions)

        assert len(actions) == 0

    @pytest.mark.asyncio
    async def test_drift_medium_priority(self) -> None:
        from a2a.cstp.drift_service import CheckDriftResponse, DriftAlert, WindowStats

        mock_response = CheckDriftResponse(
            drift_detected=True,
            recent=WindowStats("30d", 0.20, 0.7, 10),
            historical=WindowStats("90d+", 0.15, 0.8, 30),
            alerts=[DriftAlert(
                type="brier_degradation",
                category="process",
                recent_value=0.20,
                historical_value=0.15,
                change_pct=33.3,  # >20% but <40% → medium
                severity="warning",
                message="Process: Brier score degraded 33%",
            )],
        )

        decisions = [_make_decision(status="reviewed", category="process")]

        with patch(
            "a2a.cstp.ready_service.check_drift",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            from a2a.cstp.ready_service import _detect_drift_actions
            actions = await _detect_drift_actions(decisions)

        assert len(actions) == 1
        assert actions[0].priority == "medium"

    @pytest.mark.asyncio
    async def test_no_reviewed_decisions(self) -> None:
        """No reviewed decisions → no categories → no drift actions."""
        decisions = [_make_decision(status="pending")]

        with patch(
            "a2a.cstp.ready_service.check_drift",
            new_callable=AsyncMock,
        ) as mock_drift:
            from a2a.cstp.ready_service import _detect_drift_actions
            actions = await _detect_drift_actions(decisions)

        mock_drift.assert_not_called()
        assert len(actions) == 0


# ---------------------------------------------------------------------------
# Dispatcher integration
# ---------------------------------------------------------------------------


class TestReadyDispatcher:
    @pytest.fixture
    def dispatcher(self) -> CstpDispatcher:
        d = CstpDispatcher()
        register_methods(d)
        return d

    def test_method_registered(self, dispatcher: CstpDispatcher) -> None:
        assert "cstp.ready" in dispatcher._methods

    @pytest.mark.asyncio
    @patch(
        "a2a.cstp.ready_service.load_all_decisions",
        new_callable=AsyncMock,
    )
    async def test_dispatch_round_trip(
        self, mock_load: AsyncMock, dispatcher: CstpDispatcher,
    ) -> None:
        mock_load.return_value = [
            _make_decision(review_by=_days_ago(3), stakes="high"),
        ]

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.ready",
            params={"minPriority": "low", "limit": 10},
            id="test-1",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")

        assert response.error is None
        assert response.result is not None
        assert "actions" in response.result
        assert len(response.result["actions"]) == 1
        assert response.result["actions"][0]["type"] == "review_outcome"
        assert response.result["total"] == 1

    @pytest.mark.asyncio
    @patch(
        "a2a.cstp.ready_service.load_all_decisions",
        new_callable=AsyncMock,
    )
    async def test_dispatch_empty(
        self, mock_load: AsyncMock, dispatcher: CstpDispatcher,
    ) -> None:
        mock_load.return_value = []

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.ready",
            params={},
            id="test-2",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")

        assert response.error is None
        assert response.result["actions"] == []
        assert response.result["total"] == 0

    @pytest.mark.asyncio
    @patch(
        "a2a.cstp.ready_service.load_all_decisions",
        new_callable=AsyncMock,
    )
    async def test_dispatch_with_filters(
        self, mock_load: AsyncMock, dispatcher: CstpDispatcher,
    ) -> None:
        mock_load.return_value = [
            _make_decision(id="hi", review_by=_days_ago(1), stakes="high"),
            _make_decision(id="lo", review_by=_days_ago(1), stakes="low"),
        ]

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.ready",
            params={
                "minPriority": "medium",
                "actionTypes": ["review_outcome"],
            },
            id="test-3",
        )
        response = await dispatcher.dispatch(request, agent_id="test-agent")

        assert response.error is None
        assert len(response.result["actions"]) == 1
        assert response.result["filtered"] == 1
