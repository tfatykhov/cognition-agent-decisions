"""Tests for F169: Bridge (structure/function) in DecisionSummary search results."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.models import DecisionSummary


class TestDecisionSummaryBridge:
    """DecisionSummary bridge field serialization."""

    def test_bridge_none_excluded_from_dict(self) -> None:
        """When bridge is None, it should not appear in to_dict output."""
        summary = DecisionSummary(
            id="abc12345",
            title="Test",
            category="architecture",
            confidence=0.9,
            stakes="medium",
            status="reviewed",
            outcome="success",
            date="2026-02-18",
            distance=0.1,
        )
        result = summary.to_dict()
        assert "bridge" not in result

    def test_bridge_included_in_dict(self) -> None:
        """When bridge has data, it should appear in to_dict output."""
        summary = DecisionSummary(
            id="abc12345",
            title="Test",
            category="architecture",
            confidence=0.9,
            stakes="medium",
            status="reviewed",
            outcome="success",
            date="2026-02-18",
            distance=0.1,
            bridge={"structure": "REST API endpoint", "function": "Serve user data"},
        )
        result = summary.to_dict()
        assert "bridge" in result
        assert result["bridge"]["structure"] == "REST API endpoint"
        assert result["bridge"]["function"] == "Serve user data"

    def test_bridge_structure_only(self) -> None:
        """Bridge with only structure should work."""
        summary = DecisionSummary(
            id="abc12345",
            title="Test",
            category="architecture",
            confidence=0.9,
            stakes="medium",
            status="reviewed",
            outcome=None,
            date="2026-02-18",
            distance=0.1,
            bridge={"structure": "Decorator pattern"},
        )
        result = summary.to_dict()
        assert result["bridge"] == {"structure": "Decorator pattern"}

    def test_bridge_function_only(self) -> None:
        """Bridge with only function should work."""
        summary = DecisionSummary(
            id="abc12345",
            title="Test",
            category="architecture",
            confidence=0.9,
            stakes="medium",
            status="reviewed",
            outcome=None,
            date="2026-02-18",
            distance=0.1,
            bridge={"function": "Decouple validation from business logic"},
        )
        result = summary.to_dict()
        assert result["bridge"] == {"function": "Decouple validation from business logic"}


class TestExtractBridge:
    """Test _extract_bridge helper in dispatcher."""

    def test_extract_bridge_full(self) -> None:
        """Should extract structure and function from bridge dict."""
        from a2a.cstp.dispatcher import _extract_bridge

        d = {
            "bridge": {
                "structure": "REST endpoint with pagination",
                "function": "Enable cursor-based data fetching",
                "enforcement": ["must have cursor param"],
                "prevention": ["no offset-based pagination"],
            },
        }
        result = _extract_bridge(d)
        assert result == {
            "structure": "REST endpoint with pagination",
            "function": "Enable cursor-based data fetching",
        }

    def test_extract_bridge_none_when_missing(self) -> None:
        """Should return None when bridge is not present."""
        from a2a.cstp.dispatcher import _extract_bridge

        assert _extract_bridge({}) is None
        assert _extract_bridge({"bridge": None}) is None

    def test_extract_bridge_none_when_empty(self) -> None:
        """Should return None when bridge has no structure or function."""
        from a2a.cstp.dispatcher import _extract_bridge

        assert _extract_bridge({"bridge": {}}) is None
        assert _extract_bridge({"bridge": {"enforcement": ["x"]}}) is None

    def test_extract_bridge_non_dict(self) -> None:
        """Should return None when bridge is not a dict."""
        from a2a.cstp.dispatcher import _extract_bridge

        assert _extract_bridge({"bridge": "not a dict"}) is None


class TestQueryResultBridgeParsing:
    """Test bridge_json parsing in query_service."""

    @pytest.fixture()
    def mock_store(self) -> AsyncMock:
        store = AsyncMock()
        store.get_collection_id = AsyncMock(return_value="test-collection")
        return store

    @pytest.fixture()
    def mock_provider(self) -> AsyncMock:
        provider = AsyncMock()
        provider.embed = AsyncMock(return_value=[0.1] * 768)
        return provider

    @dataclass
    class FakeVectorResult:
        id: str
        distance: float
        metadata: dict[str, Any]
        document: str = ""

    async def test_bridge_json_parsed_from_metadata(
        self, mock_store: AsyncMock, mock_provider: AsyncMock
    ) -> None:
        """bridge_json in metadata should be parsed into QueryResult.bridge."""
        bridge = {"structure": "Cache layer", "function": "Reduce DB load"}
        mock_store.query = AsyncMock(return_value=[
            self.FakeVectorResult(
                id="abcd1234-full-id",
                distance=0.15,
                metadata={
                    "title": "Add caching",
                    "category": "architecture",
                    "confidence": 0.9,
                    "stakes": "medium",
                    "status": "reviewed",
                    "date": "2026-02-18",
                    "bridge_json": json.dumps(bridge),
                },
            ),
        ])

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=mock_store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            response = await query_decisions(query="caching strategy", n_results=5)

        assert len(response.results) == 1
        assert response.results[0].bridge == bridge

    async def test_no_bridge_json_returns_none(
        self, mock_store: AsyncMock, mock_provider: AsyncMock
    ) -> None:
        """When bridge_json is absent, QueryResult.bridge should be None."""
        mock_store.query = AsyncMock(return_value=[
            self.FakeVectorResult(
                id="abcd1234-full-id",
                distance=0.15,
                metadata={
                    "title": "No bridge",
                    "category": "architecture",
                    "confidence": 0.9,
                    "stakes": "medium",
                    "status": "pending",
                    "date": "2026-02-18",
                },
            ),
        ])

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=mock_store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            response = await query_decisions(query="test", n_results=5)

        assert len(response.results) == 1
        assert response.results[0].bridge is None

    async def test_invalid_bridge_json_returns_none(
        self, mock_store: AsyncMock, mock_provider: AsyncMock
    ) -> None:
        """When bridge_json is malformed, QueryResult.bridge should be None."""
        mock_store.query = AsyncMock(return_value=[
            self.FakeVectorResult(
                id="abcd1234-full-id",
                distance=0.15,
                metadata={
                    "title": "Bad JSON",
                    "category": "architecture",
                    "confidence": 0.9,
                    "stakes": "medium",
                    "status": "pending",
                    "date": "2026-02-18",
                    "bridge_json": "not valid json{",
                },
            ),
        ])

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=mock_store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            response = await query_decisions(query="test", n_results=5)

        assert len(response.results) == 1
        assert response.results[0].bridge is None


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
class MockEvalResult:
    allowed: bool = True
    violations: list[Any] = field(default_factory=list)
    warnings: list[Any] = field(default_factory=list)
    evaluated: int = 3


@dataclass
class MockCalOverall:
    brier_score: float = 0.05
    accuracy: float = 0.9
    calibration_gap: float = 0.1
    interpretation: str = "well_calibrated"
    reviewed_decisions: int = 10


@dataclass
class MockCalibrationResponse:
    overall: MockCalOverall = field(default_factory=MockCalOverall)


class TestPreActionBridgePassthrough:
    """Bridge data flows from query results through to PreActionResponse."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    async def test_bridge_flows_to_relevant_decisions(
        self,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
    ) -> None:
        """Bridge from QueryResult should appear in PreActionResponse.relevant_decisions."""
        bridge_data = {"structure": "Decorator pattern", "function": "Add logging"}
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult(bridge=bridge_data)],
        )
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()

        from a2a.cstp.models import PreActionRequest
        from a2a.cstp.preaction_service import pre_action

        request = PreActionRequest.from_params({
            "action": {
                "description": "Test action",
                "category": "architecture",
                "stakes": "low",
                "confidence": 0.9,
            },
            "options": {"autoRecord": False},
        })
        response = await pre_action(request, agent_id="test-agent")

        assert len(response.relevant_decisions) == 1
        assert response.relevant_decisions[0].bridge == bridge_data

        # Verify serialization
        response_dict = response.to_dict()
        decisions = response_dict["relevantDecisions"]
        assert decisions[0]["bridge"] == bridge_data

    @pytest.mark.asyncio
    @patch("a2a.cstp.preaction_service.get_calibration")
    @patch("a2a.cstp.preaction_service.evaluate_guardrails")
    @patch("a2a.cstp.preaction_service.query_decisions")
    async def test_no_bridge_excluded_from_response(
        self,
        mock_query: AsyncMock,
        mock_guard: AsyncMock,
        mock_cal: AsyncMock,
    ) -> None:
        """When bridge is None, it should not appear in serialized response."""
        mock_query.return_value = MockQueryResponse(
            results=[MockQueryResult(bridge=None)],
        )
        mock_guard.return_value = MockEvalResult(allowed=True)
        mock_cal.return_value = MockCalibrationResponse()

        from a2a.cstp.models import PreActionRequest
        from a2a.cstp.preaction_service import pre_action

        request = PreActionRequest.from_params({
            "action": {
                "description": "Test action",
                "category": "architecture",
                "stakes": "low",
                "confidence": 0.9,
            },
            "options": {"autoRecord": False},
        })
        response = await pre_action(request, agent_id="test-agent")

        response_dict = response.to_dict()
        decisions = response_dict["relevantDecisions"]
        assert "bridge" not in decisions[0]
