"""Integration tests for F007 recordDecision endpoint."""

from pathlib import Path
from unittest.mock import patch

import pytest

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.models.jsonrpc import JsonRpcRequest


@pytest.fixture
def dispatcher() -> CstpDispatcher:
    """Create dispatcher with registered methods."""
    d = CstpDispatcher()
    register_methods(d)
    return d


class TestRecordDecisionEndpoint:
    """Tests for cstp.recordDecision JSON-RPC endpoint."""

    @pytest.mark.asyncio
    async def test_method_registered(self, dispatcher: CstpDispatcher) -> None:
        """recordDecision method is registered."""
        assert "cstp.recordDecision" in dispatcher._methods

    @pytest.mark.asyncio
    async def test_minimal_request(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Minimal valid request succeeds."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Use SQLite for testing",
                "confidence": 0.90,
                "category": "tooling",
            },
            id=1,
        )

        with patch(
            "a2a.cstp.decision_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        assert response.result is not None
        assert response.result["success"] is True
        assert len(response.result["id"]) == 8
        assert "path" in response.result

    @pytest.mark.asyncio
    async def test_full_request(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Full request with all fields succeeds."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Use PostgreSQL for production",
                "confidence": 0.85,
                "category": "architecture",
                "stakes": "high",
                "context": "Choosing primary database",
                "reasons": [
                    {"type": "analysis", "text": "ACID compliance needed", "strength": 0.9},
                    {"type": "pattern", "text": "Similar to prior successful choice"},
                ],
                "kpiIndicators": ["latency", "availability"],
                "mentalState": "deliberate",
                "reviewIn": "30d",
                "tags": ["database", "infrastructure"],
                "preDecision": {
                    "queryRun": True,
                    "similarFound": 2,
                    "guardrailsChecked": True,
                    "guardrailsPassed": True,
                },
            },
            id=2,
        )

        with patch(
            "a2a.cstp.decision_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "emerson")

        assert response.error is None
        assert response.result["success"] is True

    @pytest.mark.asyncio
    async def test_validation_error_missing_decision(
        self, dispatcher: CstpDispatcher
    ) -> None:
        """Missing decision field returns validation error."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "confidence": 0.85,
                "category": "architecture",
            },
            id=3,
        )

        response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is not None
        assert "decision" in response.error.message.lower()

    @pytest.mark.asyncio
    async def test_validation_error_invalid_confidence(
        self, dispatcher: CstpDispatcher
    ) -> None:
        """Invalid confidence returns validation error."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Test",
                "confidence": 1.5,  # Invalid: > 1.0
                "category": "architecture",
            },
            id=4,
        )

        response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is not None
        assert "confidence" in response.error.message.lower()

    @pytest.mark.asyncio
    async def test_validation_error_invalid_category(
        self, dispatcher: CstpDispatcher
    ) -> None:
        """Invalid category returns validation error."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Test",
                "confidence": 0.85,
                "category": "invalid_category",
            },
            id=5,
        )

        response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is not None
        assert "category" in response.error.message.lower()

    @pytest.mark.asyncio
    async def test_agent_id_recorded(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Agent ID from auth is recorded in decision."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Test agent attribution",
                "confidence": 0.85,
                "category": "process",
            },
            id=6,
        )

        with patch(
            "a2a.cstp.decision_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "my-agent-id")

        assert response.result["success"] is True

        # Read the file and verify agent_id
        import yaml
        with open(response.result["path"]) as f:
            data = yaml.safe_load(f)
        assert data.get("recorded_by") == "my-agent-id"

    @pytest.mark.asyncio
    async def test_indexing_attempted(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Indexing is attempted (may fail in tests without ChromaDB)."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.recordDecision",
            params={
                "decision": "Test indexing",
                "confidence": 0.85,
                "category": "architecture",
            },
            id=7,
        )

        with patch(
            "a2a.cstp.decision_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        # Should succeed even if indexing fails
        assert response.result["success"] is True
        # indexed field should be present (True or False)
        assert "indexed" in response.result
