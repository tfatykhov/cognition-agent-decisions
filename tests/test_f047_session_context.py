"""Tests for F047: cstp.getSessionContext implementation."""

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.models import (
    AgentProfile,
    ConfirmedPattern,
    ReadyQueueItem,
    SessionContextRequest,
    SessionContextResponse,
)
from a2a.cstp.session_context_service import (
    _build_agent_profile,
    _build_calibration_by_category,
    _build_ready_queue,
    _extract_confirmed_patterns,
    _render_markdown,
)
from a2a.models.jsonrpc import JsonRpcRequest


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestSessionContextRequest:
    def test_from_params_defaults(self) -> None:
        req = SessionContextRequest.from_params({})
        assert req.task_description is None
        assert req.decisions_limit == 10
        assert req.ready_limit == 5
        assert req.format == "json"
        assert "decisions" in req.include
        assert "guardrails" in req.include
        assert "calibration" in req.include
        assert "ready" in req.include
        assert "patterns" in req.include

    def test_from_params_custom(self) -> None:
        req = SessionContextRequest.from_params({
            "taskDescription": "Fix auth bug",
            "include": ["decisions", "guardrails"],
            "decisionsLimit": 3,
            "readyLimit": 2,
            "format": "markdown",
        })
        assert req.task_description == "Fix auth bug"
        assert req.decisions_limit == 3
        assert req.ready_limit == 2
        assert req.format == "markdown"
        assert req.include == ["decisions", "guardrails"]

    def test_from_params_clamps_limits(self) -> None:
        req = SessionContextRequest.from_params({
            "decisionsLimit": 999,
            "readyLimit": -5,
        })
        assert req.decisions_limit == 50
        assert req.ready_limit == 1

    def test_from_params_invalid_format(self) -> None:
        req = SessionContextRequest.from_params({"format": "xml"})
        assert req.format == "json"


class TestAgentProfileModel:
    def test_to_dict_empty(self) -> None:
        profile = AgentProfile()
        data = profile.to_dict()
        assert data["totalDecisions"] == 0
        assert data["reviewed"] == 0
        assert "overallAccuracy" not in data

    def test_to_dict_full(self) -> None:
        profile = AgentProfile(
            total_decisions=47,
            reviewed=32,
            overall_accuracy=0.94,
            brier_score=0.028,
            tendency="slightly_underconfident",
            strongest_category="tooling",
            weakest_category="security",
            active_since="2026-01-15",
        )
        data = profile.to_dict()
        assert data["totalDecisions"] == 47
        assert data["reviewed"] == 32
        assert data["overallAccuracy"] == 0.94
        assert data["brierScore"] == 0.028
        assert data["tendency"] == "slightly_underconfident"
        assert data["strongestCategory"] == "tooling"
        assert data["weakestCategory"] == "security"
        assert data["activeSince"] == "2026-01-15"


class TestSessionContextResponse:
    def test_to_dict_json_format(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(total_decisions=5),
            query_time_ms=100,
        )
        data = resp.to_dict()
        assert "agentProfile" in data
        assert data["agentProfile"]["totalDecisions"] == 5
        assert data["queryTimeMs"] == 100

    def test_to_dict_markdown_format(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(),
            markdown="## Context\nHello",
            query_time_ms=50,
        )
        data = resp.to_dict()
        assert data["markdown"] == "## Context\nHello"
        assert data["queryTimeMs"] == 50
        assert "agentProfile" not in data


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestBuildAgentProfile:
    def test_empty_decisions(self) -> None:
        profile = _build_agent_profile([])
        assert profile.total_decisions == 0
        assert profile.reviewed == 0
        assert profile.overall_accuracy is None
        assert profile.tendency is None

    def test_all_successful(self) -> None:
        decisions = [
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-01"},
            {"confidence": 0.9, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-02"},
            {"confidence": 0.7, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-03"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.total_decisions == 3
        assert profile.reviewed == 3
        assert profile.overall_accuracy == 1.0
        assert profile.active_since == "2026-01-01"

    def test_mixed_outcomes(self) -> None:
        decisions = [
            {"confidence": 0.9, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-01"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "failure",
             "category": "arch", "date": "2026-01-02"},
            {"confidence": 0.7, "status": "reviewed", "outcome": "partial",
             "category": "arch", "date": "2026-01-03"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.total_decisions == 3
        assert profile.reviewed == 3
        # accuracy = (1.0 + 0.0 + 0.5) / 3 = 0.5
        assert profile.overall_accuracy == 0.5
        assert profile.brier_score is not None

    def test_tendency_overconfident(self) -> None:
        """High confidence but low accuracy => overconfident."""
        decisions = [
            {"confidence": 0.95, "status": "reviewed", "outcome": "failure",
             "category": "security", "date": "2026-01-01"},
            {"confidence": 0.90, "status": "reviewed", "outcome": "failure",
             "category": "security", "date": "2026-01-02"},
            {"confidence": 0.85, "status": "reviewed", "outcome": "failure",
             "category": "security", "date": "2026-01-03"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.tendency == "overconfident"

    def test_tendency_underconfident(self) -> None:
        """Low confidence but high accuracy => underconfident."""
        decisions = [
            {"confidence": 0.3, "status": "reviewed", "outcome": "success",
             "category": "tooling", "date": "2026-01-01"},
            {"confidence": 0.4, "status": "reviewed", "outcome": "success",
             "category": "tooling", "date": "2026-01-02"},
            {"confidence": 0.35, "status": "reviewed", "outcome": "success",
             "category": "tooling", "date": "2026-01-03"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.tendency == "underconfident"

    def test_strongest_weakest_category(self) -> None:
        decisions = [
            # Architecture: 3/3 success
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "architecture", "date": "2026-01-01"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "architecture", "date": "2026-01-02"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "architecture", "date": "2026-01-03"},
            # Security: 1/3 success
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "security", "date": "2026-01-04"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "failure",
             "category": "security", "date": "2026-01-05"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "failure",
             "category": "security", "date": "2026-01-06"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.strongest_category == "architecture"
        assert profile.weakest_category == "security"

    def test_category_needs_min_3_decisions(self) -> None:
        """Categories with < 3 reviewed decisions shouldn't count."""
        decisions = [
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-01"},
            {"confidence": 0.8, "status": "reviewed", "outcome": "failure",
             "category": "arch", "date": "2026-01-02"},
            # Only 2 arch decisions - not enough
            {"confidence": 0.8, "status": "reviewed", "outcome": "success",
             "category": "tooling", "date": "2026-01-03"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.strongest_category is None
        assert profile.weakest_category is None

    def test_pending_not_counted_as_reviewed(self) -> None:
        decisions = [
            {"confidence": 0.8, "status": "pending", "category": "arch",
             "date": "2026-01-01"},
            {"confidence": 0.9, "status": "reviewed", "outcome": "success",
             "category": "arch", "date": "2026-01-02"},
        ]
        profile = _build_agent_profile(decisions)
        assert profile.total_decisions == 2
        assert profile.reviewed == 1


class TestBuildReadyQueue:
    def test_overdue_review(self) -> None:
        decisions = [
            {"id": "abc12345", "summary": "Old decision", "status": "pending",
             "date": "2025-12-01", "review_by": "2026-01-01"},
        ]
        items = _build_ready_queue(decisions, limit=5)
        assert len(items) == 1
        assert items[0].reason == "overdue_review"
        assert items[0].id == "abc12345"
        assert "2026-01-01" in items[0].detail

    def test_stale_pending(self) -> None:
        decisions = [
            {"id": "def67890", "summary": "Stale decision",
             "status": "pending", "date": "2025-01-01"},
        ]
        items = _build_ready_queue(decisions, limit=5)
        assert len(items) >= 1
        assert items[0].reason == "stale_pending"
        assert "pending" in items[0].detail

    def test_reviewed_excluded(self) -> None:
        decisions = [
            {"id": "rev12345", "summary": "Done", "status": "reviewed",
             "outcome": "success", "date": "2025-01-01"},
        ]
        items = _build_ready_queue(decisions, limit=5)
        assert len(items) == 0

    def test_recent_pending_excluded(self) -> None:
        """Pending decisions younger than STALE_DAYS should not appear."""
        decisions = [
            {"id": "new12345", "summary": "Recent", "status": "pending",
             "date": "2026-02-10"},
        ]
        items = _build_ready_queue(decisions, limit=5)
        assert len(items) == 0

    def test_overdue_before_stale(self) -> None:
        """Overdue reviews should sort before stale pending."""
        decisions = [
            {"id": "stale123", "summary": "Stale", "status": "pending",
             "date": "2025-01-01"},
            {"id": "overdue1", "summary": "Overdue", "status": "pending",
             "date": "2025-12-01", "review_by": "2026-01-01"},
        ]
        items = _build_ready_queue(decisions, limit=5)
        assert len(items) == 2
        assert items[0].reason == "overdue_review"
        assert items[1].reason == "stale_pending"

    def test_limit_respected(self) -> None:
        decisions = [
            {"id": f"id{i:06d}", "summary": f"Dec {i}", "status": "pending",
             "date": "2025-01-01"}
            for i in range(10)
        ]
        items = _build_ready_queue(decisions, limit=3)
        assert len(items) == 3


class TestExtractConfirmedPatterns:
    def test_groups_by_pattern(self) -> None:
        decisions = [
            {"id": "a1234567", "pattern": "Override defaults",
             "category": "arch"},
            {"id": "b1234567", "pattern": "Override defaults",
             "category": "tooling"},
            {"id": "c1234567", "pattern": "Unique pattern",
             "category": "process"},
        ]
        patterns = _extract_confirmed_patterns(decisions)
        assert len(patterns) == 1
        assert patterns[0].pattern == "Override defaults"
        assert patterns[0].count == 2
        assert set(patterns[0].categories) == {"arch", "tooling"}

    def test_single_occurrence_excluded(self) -> None:
        decisions = [
            {"id": "a1234567", "pattern": "Only once", "category": "arch"},
        ]
        patterns = _extract_confirmed_patterns(decisions)
        assert len(patterns) == 0

    def test_no_patterns(self) -> None:
        decisions = [
            {"id": "a1234567", "category": "arch"},
            {"id": "b1234567", "category": "process"},
        ]
        patterns = _extract_confirmed_patterns(decisions)
        assert len(patterns) == 0

    def test_sorted_by_count_descending(self) -> None:
        decisions = [
            {"id": "a1", "pattern": "Less common", "category": "arch"},
            {"id": "a2", "pattern": "Less common", "category": "arch"},
            {"id": "b1", "pattern": "Most common", "category": "arch"},
            {"id": "b2", "pattern": "Most common", "category": "arch"},
            {"id": "b3", "pattern": "Most common", "category": "arch"},
        ]
        patterns = _extract_confirmed_patterns(decisions)
        assert len(patterns) == 2
        assert patterns[0].pattern == "Most common"
        assert patterns[0].count == 3
        assert patterns[1].pattern == "Less common"
        assert patterns[1].count == 2


class TestBuildCalibrationByCategory:
    @patch("a2a.cstp.session_context_service.calculate_calibration")
    def test_groups_by_category(self, mock_calc: AsyncMock) -> None:
        from a2a.cstp.calibration_service import CalibrationResult

        mock_calc.return_value = CalibrationResult(
            brier_score=0.05,
            accuracy=0.90,
            total_decisions=5,
            reviewed_decisions=5,
            calibration_gap=-0.02,
            interpretation="well_calibrated",
        )

        decisions = [
            {"status": "reviewed", "outcome": "success", "confidence": 0.8,
             "category": "architecture"},
            {"status": "reviewed", "outcome": "success", "confidence": 0.9,
             "category": "architecture"},
            {"status": "reviewed", "outcome": "failure", "confidence": 0.7,
             "category": "architecture"},
            {"status": "reviewed", "outcome": "success", "confidence": 0.8,
             "category": "security"},
        ]
        result = _build_calibration_by_category(decisions)
        # calculate_calibration returns None for < 3 decisions,
        # but we mocked it to always return, so both categories show up
        assert "architecture" in result
        assert "security" in result

    @patch("a2a.cstp.session_context_service.calculate_calibration")
    def test_returns_none_for_insufficient(self, mock_calc: AsyncMock) -> None:
        mock_calc.return_value = None

        decisions = [
            {"status": "reviewed", "outcome": "success", "confidence": 0.8,
             "category": "arch"},
        ]
        result = _build_calibration_by_category(decisions)
        assert result == {}


class TestRenderMarkdown:
    def test_basic_rendering(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(
                total_decisions=10,
                reviewed=7,
                overall_accuracy=0.85,
                brier_score=0.05,
                tendency="well_calibrated",
            ),
        )
        md = _render_markdown(resp, "test-agent")
        assert "test-agent" in md
        assert "10 total" in md
        assert "7 reviewed" in md
        assert "85%" in md
        assert "pre_action" in md

    def test_guardrails_section(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(),
            active_guardrails=[
                {"id": "g1", "description": "No prod without review",
                 "action": "block"},
            ],
        )
        md = _render_markdown(resp, "test-agent")
        assert "Guardrails" in md
        assert "[block]" in md
        assert "No prod without review" in md

    def test_ready_queue_section(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(),
            ready_queue=[
                ReadyQueueItem(
                    id="abc123", title="Old decision",
                    reason="overdue_review", date="2025-12-01",
                    detail="review by 2026-01-01",
                ),
            ],
        )
        md = _render_markdown(resp, "test-agent")
        assert "OVERDUE" in md
        assert "abc123" in md

    def test_patterns_section(self) -> None:
        resp = SessionContextResponse(
            agent_profile=AgentProfile(),
            confirmed_patterns=[
                ConfirmedPattern(
                    pattern="Stateless auth",
                    count=3,
                    categories=["architecture"],
                    example_ids=["a1", "a2", "a3"],
                ),
            ],
        )
        md = _render_markdown(resp, "test-agent")
        assert "Stateless auth" in md
        assert "3x" in md


# ---------------------------------------------------------------------------
# Service tests
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


@dataclass
class MockQueryResponse:
    results: list[MockQueryResult] = field(default_factory=list)
    query: str = "test"
    query_time_ms: int = 10
    error: str | None = None


class TestSessionContextService:
    @pytest.mark.asyncio
    @patch("a2a.cstp.session_context_service.list_guardrails")
    @patch("a2a.cstp.session_context_service.query_decisions")
    @patch("a2a.cstp.session_context_service.load_all_decisions")
    async def test_full_json_context(
        self,
        mock_load: AsyncMock,
        mock_query: AsyncMock,
        mock_guardrails: AsyncMock,
    ) -> None:
        mock_load.return_value = [
            {"id": "a1", "status": "reviewed", "outcome": "success",
             "confidence": 0.8, "category": "arch", "date": "2026-01-01",
             "pattern": "Override defaults"},
            {"id": "a2", "status": "reviewed", "outcome": "success",
             "confidence": 0.9, "category": "arch", "date": "2026-01-02",
             "pattern": "Override defaults"},
            {"id": "a3", "status": "reviewed", "outcome": "failure",
             "confidence": 0.7, "category": "arch", "date": "2026-01-03"},
        ]
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult()],
        )
        mock_guardrails.return_value = [
            {"id": "g1", "description": "Test", "action": "warn"},
        ]

        from a2a.cstp.session_context_service import get_session_context

        req = SessionContextRequest.from_params({
            "taskDescription": "Build auth service",
        })
        resp = await get_session_context(req, agent_id="test-agent")

        assert resp.agent_profile.total_decisions == 3
        assert resp.agent_profile.reviewed == 3
        assert len(resp.relevant_decisions) == 1
        assert len(resp.active_guardrails) == 1
        assert len(resp.confirmed_patterns) == 1
        assert resp.confirmed_patterns[0].pattern == "Override defaults"
        assert resp.markdown is None  # json format

    @pytest.mark.asyncio
    @patch("a2a.cstp.session_context_service.list_guardrails")
    @patch("a2a.cstp.session_context_service.query_decisions")
    @patch("a2a.cstp.session_context_service.load_all_decisions")
    async def test_markdown_format(
        self,
        mock_load: AsyncMock,
        mock_query: AsyncMock,
        mock_guardrails: AsyncMock,
    ) -> None:
        mock_load.return_value = [
            {"id": "a1", "status": "reviewed", "outcome": "success",
             "confidence": 0.8, "category": "arch", "date": "2026-01-01"},
        ]
        mock_query.return_value = MockQueryResponse()
        mock_guardrails.return_value = []

        from a2a.cstp.session_context_service import get_session_context

        req = SessionContextRequest.from_params({
            "taskDescription": "Test",
            "format": "markdown",
        })
        resp = await get_session_context(req, agent_id="test-agent")

        assert resp.markdown is not None
        data = resp.to_dict()
        assert "markdown" in data
        assert "agentProfile" not in data

    @pytest.mark.asyncio
    @patch("a2a.cstp.session_context_service.load_all_decisions")
    async def test_selective_include(self, mock_load: AsyncMock) -> None:
        """Only requested sections should be populated."""
        mock_load.return_value = []

        from a2a.cstp.session_context_service import get_session_context

        req = SessionContextRequest.from_params({
            "include": ["patterns"],
        })
        resp = await get_session_context(req, agent_id="test-agent")

        # Guardrails not requested, should be empty
        assert resp.active_guardrails == []
        # Decisions not requested (no task_description anyway)
        assert resp.relevant_decisions == []


# ---------------------------------------------------------------------------
# Dispatcher integration tests
# ---------------------------------------------------------------------------


class TestSessionContextEndpoint:
    @pytest.fixture
    def dispatcher(self) -> CstpDispatcher:
        d = CstpDispatcher()
        register_methods(d)
        return d

    def test_method_registered(self, dispatcher: CstpDispatcher) -> None:
        assert "cstp.getSessionContext" in dispatcher._methods

    @pytest.mark.asyncio
    @patch("a2a.cstp.session_context_service.list_guardrails")
    @patch("a2a.cstp.session_context_service.query_decisions")
    @patch("a2a.cstp.session_context_service.load_all_decisions")
    async def test_dispatch_round_trip(
        self,
        mock_load: AsyncMock,
        mock_query: AsyncMock,
        mock_guardrails: AsyncMock,
        dispatcher: CstpDispatcher,
    ) -> None:
        mock_load.return_value = []
        mock_query.return_value = MockQueryResponse()
        mock_guardrails.return_value = []

        request = JsonRpcRequest(
            id="1",
            method="cstp.getSessionContext",
            params={"taskDescription": "Test dispatch"},
        )
        response = await dispatcher.dispatch(request, agent_id="test")

        assert response.error is None
        assert response.result is not None
        assert "agentProfile" in response.result
