"""Integration tests for F009 getCalibration endpoint."""

from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.models.jsonrpc import JsonRpcRequest


@pytest.fixture(autouse=True)
def _force_yaml_fallback():
    """Force _scan_decisions to use YAML fallback so tests control data via tmp_path."""
    with patch(
        "a2a.cstp.storage.factory.get_decision_store",
        side_effect=RuntimeError("force YAML fallback"),
    ):
        yield


@pytest.fixture
def dispatcher() -> CstpDispatcher:
    """Create dispatcher with registered methods."""
    d = CstpDispatcher()
    register_methods(d)
    return d


def create_reviewed_decision(
    tmp_path: Path,
    decision_id: str,
    confidence: float,
    outcome: str,
    category: str = "architecture",
    agent: str = "test-agent",
) -> None:
    """Helper to create a reviewed decision file."""
    year_dir = tmp_path / "2026" / "02"
    year_dir.mkdir(parents=True, exist_ok=True)

    data = {
        "id": decision_id,
        "summary": f"Test decision {decision_id}",
        "category": category,
        "confidence": confidence,
        "status": "reviewed",
        "outcome": outcome,
        "date": "2026-02-05T00:00:00Z",
        "recorded_by": agent,
    }

    file_path = year_dir / f"2026-02-05-decision-{decision_id}.yaml"
    with open(file_path, "w") as f:
        yaml.dump(data, f)


class TestGetCalibrationEndpoint:
    """Tests for cstp.getCalibration JSON-RPC endpoint."""

    @pytest.mark.asyncio
    async def test_method_registered(self, dispatcher: CstpDispatcher) -> None:
        """getCalibration method is registered."""
        assert "cstp.getCalibration" in dispatcher._methods

    @pytest.mark.asyncio
    async def test_basic_request(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Basic calibration request works."""
        # Create some reviewed decisions
        for i in range(6):
            outcome = "success" if i < 4 else "failure"
            create_reviewed_decision(tmp_path, f"dec{i}", 0.75, outcome)

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getCalibration",
            params={},
            id=1,
        )

        with patch(
            "a2a.cstp.calibration_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        assert response.result is not None
        assert response.result["overall"] is not None
        assert response.result["overall"]["totalDecisions"] == 6

    @pytest.mark.asyncio
    async def test_with_filters(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Calibration with filters."""
        # Create decisions for different agents
        for i in range(5):
            create_reviewed_decision(
                tmp_path, f"a{i}", 0.80, "success", agent="agent-a"
            )
        for i in range(5):
            create_reviewed_decision(
                tmp_path, f"b{i}", 0.80, "failure", agent="agent-b"
            )

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getCalibration",
            params={
                "filters": {
                    "agent": "agent-a",
                }
            },
            id=2,
        )

        with patch(
            "a2a.cstp.calibration_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        assert response.result["overall"]["totalDecisions"] == 5
        assert response.result["overall"]["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_insufficient_data(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Returns recommendations when data insufficient."""
        create_reviewed_decision(tmp_path, "only1", 0.80, "success")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getCalibration",
            params={
                "filters": {"minDecisions": 5}
            },
            id=3,
        )

        with patch(
            "a2a.cstp.calibration_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        assert response.result["overall"] is None
        assert len(response.result["recommendations"]) > 0
        assert any(
            r["type"] == "insufficient_data"
            for r in response.result["recommendations"]
        )

    @pytest.mark.asyncio
    async def test_buckets_included(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Response includes confidence buckets."""
        # Create decisions in different confidence ranges
        for i in range(4):
            create_reviewed_decision(tmp_path, f"high{i}", 0.92, "success")
        for i in range(4):
            create_reviewed_decision(tmp_path, f"med{i}", 0.75, "success")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getCalibration",
            params={},
            id=4,
        )

        with patch(
            "a2a.cstp.calibration_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        buckets = response.result["byConfidenceBucket"]
        assert len(buckets) >= 1

    @pytest.mark.asyncio
    async def test_recommendations_included(
        self, dispatcher: CstpDispatcher, tmp_path: Path
    ) -> None:
        """Response includes recommendations."""
        for i in range(6):
            create_reviewed_decision(tmp_path, f"dec{i}", 0.85, "success")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getCalibration",
            params={},
            id=5,
        )

        with patch(
            "a2a.cstp.calibration_service.DECISIONS_PATH", str(tmp_path)
        ):
            response = await dispatcher.dispatch(request, "test-agent")

        assert response.error is None
        assert "recommendations" in response.result
        assert "queryTime" in response.result
