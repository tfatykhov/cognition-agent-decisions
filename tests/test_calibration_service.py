"""Unit tests for calibration_service.py."""

from pathlib import Path

import pytest
import yaml

from a2a.cstp.calibration_service import (
    CalibrationResult,
    GetCalibrationRequest,
    calculate_buckets,
    calculate_calibration,
    generate_recommendations,
    get_calibration,
    get_reviewed_decisions,
)


def create_decision(
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


class TestGetReviewedDecisions:
    """Tests for get_reviewed_decisions."""

    @pytest.mark.asyncio
    async def test_empty_directory(self, tmp_path: Path) -> None:
        """Empty directory returns empty list."""
        result = await get_reviewed_decisions(decisions_path=str(tmp_path))
        assert result == []

    @pytest.mark.asyncio
    async def test_finds_reviewed_decisions(self, tmp_path: Path) -> None:
        """Finds reviewed decisions."""
        create_decision(tmp_path, "test1", 0.85, "success")
        create_decision(tmp_path, "test2", 0.70, "failure")

        result = await get_reviewed_decisions(decisions_path=str(tmp_path))
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_by_agent(self, tmp_path: Path) -> None:
        """Filters by agent."""
        create_decision(tmp_path, "test1", 0.85, "success", agent="agent-a")
        create_decision(tmp_path, "test2", 0.70, "failure", agent="agent-b")

        result = await get_reviewed_decisions(
            decisions_path=str(tmp_path), agent="agent-a"
        )
        assert len(result) == 1
        assert result[0]["recorded_by"] == "agent-a"

    @pytest.mark.asyncio
    async def test_filter_by_category(self, tmp_path: Path) -> None:
        """Filters by category."""
        create_decision(tmp_path, "test1", 0.85, "success", category="architecture")
        create_decision(tmp_path, "test2", 0.70, "failure", category="process")

        result = await get_reviewed_decisions(
            decisions_path=str(tmp_path), category="architecture"
        )
        assert len(result) == 1


class TestCalculateCalibration:
    """Tests for calculate_calibration."""

    def test_insufficient_data(self) -> None:
        """Returns None with fewer than 5 decisions."""
        decisions = [{"confidence": 0.8, "outcome": "success"} for _ in range(4)]
        result = calculate_calibration(decisions)
        assert result is None

    def test_perfect_calibration(self) -> None:
        """Perfect calibration has zero Brier score."""
        # All successes with confidence 1.0
        decisions = [{"confidence": 1.0, "outcome": "success"} for _ in range(5)]
        result = calculate_calibration(decisions)

        assert result is not None
        assert result.brier_score == 0.0
        assert result.accuracy == 1.0

    def test_overconfident(self) -> None:
        """Detects overconfidence."""
        # High confidence but low success rate
        decisions = [
            {"confidence": 0.9, "outcome": "failure"},
            {"confidence": 0.9, "outcome": "failure"},
            {"confidence": 0.9, "outcome": "failure"},
            {"confidence": 0.9, "outcome": "success"},
            {"confidence": 0.9, "outcome": "success"},
        ]
        result = calculate_calibration(decisions)

        assert result is not None
        assert result.calibration_gap < 0  # negative = overconfident
        assert "overconfident" in result.interpretation

    def test_underconfident(self) -> None:
        """Detects underconfidence."""
        # Low confidence but high success rate
        decisions = [
            {"confidence": 0.3, "outcome": "success"},
            {"confidence": 0.3, "outcome": "success"},
            {"confidence": 0.3, "outcome": "success"},
            {"confidence": 0.3, "outcome": "success"},
            {"confidence": 0.3, "outcome": "failure"},
        ]
        result = calculate_calibration(decisions)

        assert result is not None
        assert result.calibration_gap > 0  # positive = underconfident
        assert "underconfident" in result.interpretation

    def test_partial_outcomes(self) -> None:
        """Partial outcomes count as 0.5."""
        decisions = [
            {"confidence": 0.5, "outcome": "partial"},
            {"confidence": 0.5, "outcome": "partial"},
            {"confidence": 0.5, "outcome": "partial"},
            {"confidence": 0.5, "outcome": "partial"},
            {"confidence": 0.5, "outcome": "partial"},
        ]
        result = calculate_calibration(decisions)

        assert result is not None
        # 50% confidence, 50% success (partial) = well calibrated
        assert abs(result.calibration_gap) < 0.1


class TestCalculateBuckets:
    """Tests for calculate_buckets."""

    def test_groups_by_confidence(self) -> None:
        """Groups decisions into confidence buckets."""
        decisions = [
            {"confidence": 0.95, "outcome": "success"},
            {"confidence": 0.92, "outcome": "success"},
            {"confidence": 0.91, "outcome": "failure"},
            {"confidence": 0.75, "outcome": "success"},
            {"confidence": 0.72, "outcome": "success"},
            {"confidence": 0.71, "outcome": "success"},
        ]
        buckets = calculate_buckets(decisions)

        # Should have 0.9-1.0 and 0.7-0.9 buckets
        bucket_names = [b.bucket for b in buckets]
        assert "0.9-1.0" in bucket_names
        assert "0.7-0.9" in bucket_names

    def test_minimum_decisions_per_bucket(self) -> None:
        """Requires at least 3 decisions per bucket."""
        decisions = [
            {"confidence": 0.95, "outcome": "success"},
            {"confidence": 0.92, "outcome": "success"},
            # Only 2 in 0.9-1.0 bucket - should be excluded
        ]
        buckets = calculate_buckets(decisions)
        assert len(buckets) == 0


class TestGenerateRecommendations:
    """Tests for generate_recommendations."""

    def test_insufficient_data_recommendation(self) -> None:
        """Generates recommendation when data insufficient."""
        recs = generate_recommendations(
            overall=None, buckets=[], min_decisions=5, total_found=3
        )
        assert len(recs) == 1
        assert recs[0].type == "insufficient_data"
        assert "3" in recs[0].message

    def test_overconfident_recommendation(self) -> None:
        """Generates warning for overconfidence."""
        overall = CalibrationResult(
            brier_score=0.20,
            accuracy=0.60,
            total_decisions=10,
            reviewed_decisions=10,
            calibration_gap=-0.15,
            interpretation="overconfident",
        )
        recs = generate_recommendations(
            overall=overall, buckets=[], min_decisions=5, total_found=10
        )

        warning_recs = [r for r in recs if r.severity == "warning"]
        assert len(warning_recs) >= 1

    def test_well_calibrated_recommendation(self) -> None:
        """Generates positive feedback for good calibration."""
        overall = CalibrationResult(
            brier_score=0.08,
            accuracy=0.80,
            total_decisions=10,
            reviewed_decisions=10,
            calibration_gap=0.02,
            interpretation="well_calibrated",
        )
        recs = generate_recommendations(
            overall=overall, buckets=[], min_decisions=5, total_found=10
        )

        strength_recs = [r for r in recs if r.type in ("strength", "brier_score")]
        assert len(strength_recs) >= 1


class TestGetCalibration:
    """Integration tests for get_calibration."""

    @pytest.mark.asyncio
    async def test_full_workflow(self, tmp_path: Path) -> None:
        """Full calibration workflow."""
        # Create 10 decisions with varying outcomes
        for i in range(10):
            confidence = 0.7 + (i * 0.02)
            outcome = "success" if i % 2 == 0 else "failure"
            create_decision(tmp_path, f"test{i}", confidence, outcome)

        request = GetCalibrationRequest()
        response = await get_calibration(request, decisions_path=str(tmp_path))

        assert response.overall is not None
        assert response.overall.total_decisions == 10
        assert len(response.recommendations) > 0

    @pytest.mark.asyncio
    async def test_filter_by_agent(self, tmp_path: Path) -> None:
        """Filters calibration by agent."""
        # Agent A: mostly success
        for i in range(5):
            create_decision(tmp_path, f"a{i}", 0.8, "success", agent="agent-a")

        # Agent B: mostly failure
        for i in range(5):
            create_decision(tmp_path, f"b{i}", 0.8, "failure", agent="agent-b")

        # Get calibration for agent-a only
        request = GetCalibrationRequest(agent="agent-a")
        response = await get_calibration(request, decisions_path=str(tmp_path))

        assert response.overall is not None
        assert response.overall.total_decisions == 5
        assert response.overall.accuracy == 1.0  # All successes

    @pytest.mark.asyncio
    async def test_insufficient_data(self, tmp_path: Path) -> None:
        """Handles insufficient data gracefully."""
        create_decision(tmp_path, "test1", 0.85, "success")
        create_decision(tmp_path, "test2", 0.75, "failure")

        request = GetCalibrationRequest(min_decisions=5)
        response = await get_calibration(request, decisions_path=str(tmp_path))

        assert response.overall is None
        assert any(r.type == "insufficient_data" for r in response.recommendations)
