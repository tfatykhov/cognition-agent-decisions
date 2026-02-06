"""Tests for confidence variance tracking (F016)."""
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from a2a.cstp.calibration_service import (
    ConfidenceStats,
    calculate_confidence_stats,
    generate_variance_recommendations,
)


class TestCalculateConfidenceStats:
    """Tests for calculate_confidence_stats function."""

    def test_basic_stats(self) -> None:
        """Test basic stats calculation."""
        decisions = [
            {"confidence": 0.80},
            {"confidence": 0.85},
            {"confidence": 0.90},
        ]
        stats = calculate_confidence_stats(decisions)

        assert stats is not None
        assert stats.count == 3
        assert stats.mean == pytest.approx(0.85, abs=0.01)
        assert stats.min_conf == 0.80
        assert stats.max_conf == 0.90

    def test_bucket_counts(self) -> None:
        """Test bucket distribution."""
        decisions = [
            {"confidence": 0.55},  # 0.5-0.6
            {"confidence": 0.65},  # 0.6-0.7
            {"confidence": 0.75},  # 0.7-0.8
            {"confidence": 0.85},  # 0.8-0.9
            {"confidence": 0.85},  # 0.8-0.9
            {"confidence": 0.95},  # 0.9-1.0
        ]
        stats = calculate_confidence_stats(decisions)

        assert stats is not None
        assert stats.bucket_counts["0.5-0.6"] == 1
        assert stats.bucket_counts["0.6-0.7"] == 1
        assert stats.bucket_counts["0.7-0.8"] == 1
        assert stats.bucket_counts["0.8-0.9"] == 2
        assert stats.bucket_counts["0.9-1.0"] == 1

    def test_std_dev_calculation(self) -> None:
        """Test standard deviation calculation."""
        # All same value - std_dev should be 0
        decisions = [{"confidence": 0.85} for _ in range(10)]
        stats = calculate_confidence_stats(decisions)

        assert stats is not None
        assert stats.std_dev == 0.0

    def test_varied_std_dev(self) -> None:
        """Test std dev with varied values."""
        decisions = [
            {"confidence": 0.50},
            {"confidence": 0.75},
            {"confidence": 1.00},
        ]
        stats = calculate_confidence_stats(decisions)

        assert stats is not None
        assert stats.std_dev > 0.15  # Should have significant variance

    def test_empty_decisions(self) -> None:
        """Test with no decisions."""
        stats = calculate_confidence_stats([])
        assert stats is None

    def test_no_confidence_field(self) -> None:
        """Test decisions without confidence field."""
        decisions = [{"summary": "test"}]
        stats = calculate_confidence_stats(decisions)
        assert stats is None


class TestGenerateVarianceRecommendations:
    """Tests for generate_variance_recommendations function."""

    def test_low_variance_recommendation(self) -> None:
        """Test low variance generates recommendation."""
        stats = ConfidenceStats(
            mean=0.85,
            std_dev=0.02,  # Very low variance
            min_conf=0.82,
            max_conf=0.88,
            count=20,
            bucket_counts={
                "0.5-0.6": 0,
                "0.6-0.7": 0,
                "0.7-0.8": 0,
                "0.8-0.9": 20,  # All in one bucket
                "0.9-1.0": 0,
            },
        )
        recs = generate_variance_recommendations(stats)

        assert len(recs) >= 1
        assert any(r.type == "low_variance" for r in recs)

    def test_overconfident_habit(self) -> None:
        """Test overconfident habit detection."""
        stats = ConfidenceStats(
            mean=0.90,
            std_dev=0.05,
            min_conf=0.80,  # All high
            max_conf=0.98,
            count=15,
            bucket_counts={
                "0.5-0.6": 0,
                "0.6-0.7": 0,
                "0.7-0.8": 0,
                "0.8-0.9": 5,
                "0.9-1.0": 10,
            },
        )
        recs = generate_variance_recommendations(stats)

        assert any(r.type == "overconfident_habit" for r in recs)

    def test_no_recommendation_good_variance(self) -> None:
        """Test no recommendations with good variance."""
        stats = ConfidenceStats(
            mean=0.75,
            std_dev=0.15,  # Good variance
            min_conf=0.50,
            max_conf=0.95,
            count=20,
            bucket_counts={
                "0.5-0.6": 4,
                "0.6-0.7": 4,
                "0.7-0.8": 4,
                "0.8-0.9": 4,
                "0.9-1.0": 4,
            },
        )
        recs = generate_variance_recommendations(stats)

        # Should have no variance warnings
        assert not any(r.type in ("low_variance", "overconfident_habit") for r in recs)

    def test_insufficient_decisions(self) -> None:
        """Test no recommendations with few decisions."""
        stats = ConfidenceStats(
            mean=0.85,
            std_dev=0.01,  # Would trigger low_variance
            min_conf=0.84,
            max_conf=0.86,
            count=5,  # Too few
            bucket_counts={"0.8-0.9": 5},
        )
        recs = generate_variance_recommendations(stats)

        assert len(recs) == 0  # Not enough data

    def test_underconfident_habit(self) -> None:
        """Test underconfident habit detection."""
        stats = ConfidenceStats(
            mean=0.55,
            std_dev=0.05,
            min_conf=0.50,
            max_conf=0.65,  # All low
            count=15,
            bucket_counts={
                "0.5-0.6": 10,
                "0.6-0.7": 5,
                "0.7-0.8": 0,
                "0.8-0.9": 0,
                "0.9-1.0": 0,
            },
        )
        recs = generate_variance_recommendations(stats)

        assert any(r.type == "underconfident_habit" for r in recs)
