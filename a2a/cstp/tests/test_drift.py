"""Tests for drift detection service."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from a2a.cstp.drift_service import (
    CheckDriftRequest,
    DriftAlert,
    detect_drift_alerts,
    generate_drift_recommendations,
)


class MockCalibrationResult:
    """Mock CalibrationResult for testing."""

    def __init__(self, brier_score: float, accuracy: float) -> None:
        self.brier_score = brier_score
        self.accuracy = accuracy


class TestDetectDriftAlerts:
    """Tests for detect_drift_alerts function."""

    def test_brier_degradation_detected(self) -> None:
        """Test Brier score degradation is detected."""
        recent = MockCalibrationResult(brier_score=0.15, accuracy=0.85)
        historical = MockCalibrationResult(brier_score=0.08, accuracy=0.88)

        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.15,
            category=None,
        )

        assert len(alerts) >= 1
        brier_alert = next((a for a in alerts if a.type == "brier_degradation"), None)
        assert brier_alert is not None
        assert brier_alert.recent_value == 0.15
        assert brier_alert.historical_value == 0.08
        assert brier_alert.change_pct > 80  # ~87.5% increase

    def test_accuracy_drop_detected(self) -> None:
        """Test accuracy drop is detected."""
        recent = MockCalibrationResult(brier_score=0.10, accuracy=0.70)
        historical = MockCalibrationResult(brier_score=0.10, accuracy=0.90)

        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.15,
            category="architecture",
        )

        assert len(alerts) >= 1
        accuracy_alert = next((a for a in alerts if a.type == "accuracy_drop"), None)
        assert accuracy_alert is not None
        assert accuracy_alert.recent_value == 0.70
        assert accuracy_alert.historical_value == 0.90
        assert accuracy_alert.category == "architecture"

    def test_no_drift_when_stable(self) -> None:
        """Test no alerts when metrics are stable."""
        recent = MockCalibrationResult(brier_score=0.10, accuracy=0.85)
        historical = MockCalibrationResult(brier_score=0.09, accuracy=0.87)

        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.15,
            category=None,
        )

        assert len(alerts) == 0

    def test_no_alerts_when_improving(self) -> None:
        """Test no alerts when calibration is improving."""
        recent = MockCalibrationResult(brier_score=0.05, accuracy=0.95)
        historical = MockCalibrationResult(brier_score=0.10, accuracy=0.85)

        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.15,
            category=None,
        )

        assert len(alerts) == 0

    def test_severity_warning_for_moderate_drift(self) -> None:
        """Test warning severity for moderate drift."""
        recent = MockCalibrationResult(brier_score=0.12, accuracy=0.80)
        historical = MockCalibrationResult(brier_score=0.08, accuracy=0.88)

        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.05,
            category=None,
        )

        for alert in alerts:
            assert alert.severity in ("warning", "error")

    def test_handles_zero_historical(self) -> None:
        """Test no division by zero with zero historical values."""
        recent = MockCalibrationResult(brier_score=0.10, accuracy=0.80)
        historical = MockCalibrationResult(brier_score=0.0, accuracy=0.0)

        # Should not raise
        alerts = detect_drift_alerts(
            recent=recent,  # type: ignore
            historical=historical,  # type: ignore
            threshold_brier=0.20,
            threshold_accuracy=0.15,
            category=None,
        )

        assert isinstance(alerts, list)


class TestGenerateDriftRecommendations:
    """Tests for generate_drift_recommendations function."""

    def test_brier_degradation_recommendation(self) -> None:
        """Test recommendation for Brier degradation."""
        alerts = [
            DriftAlert(
                type="brier_degradation",
                category=None,
                recent_value=0.15,
                historical_value=0.08,
                change_pct=87.5,
                severity="warning",
                message="Test",
            )
        ]

        recs = generate_drift_recommendations(alerts)

        assert len(recs) == 1
        assert recs[0]["type"] == "recalibrate"
        assert "confidence" in recs[0]["message"].lower()

    def test_accuracy_drop_recommendation(self) -> None:
        """Test recommendation for accuracy drop."""
        alerts = [
            DriftAlert(
                type="accuracy_drop",
                category=None,
                recent_value=0.70,
                historical_value=0.90,
                change_pct=-22.2,
                severity="warning",
                message="Test",
            )
        ]

        recs = generate_drift_recommendations(alerts)

        assert len(recs) == 1
        assert recs[0]["type"] == "review_process"

    def test_no_duplicate_recommendations(self) -> None:
        """Test no duplicate recommendations for same alert type."""
        alerts = [
            DriftAlert(type="brier_degradation", category="a", recent_value=0.1,
                      historical_value=0.05, change_pct=100, severity="warning", message="1"),
            DriftAlert(type="brier_degradation", category="b", recent_value=0.2,
                      historical_value=0.1, change_pct=100, severity="warning", message="2"),
        ]

        recs = generate_drift_recommendations(alerts)

        # Should only have one recalibrate recommendation
        recalibrate_recs = [r for r in recs if r["type"] == "recalibrate"]
        assert len(recalibrate_recs) == 1


class TestCheckDriftRequest:
    """Tests for CheckDriftRequest parsing."""

    def test_from_dict_defaults(self) -> None:
        """Test default values."""
        request = CheckDriftRequest.from_dict({})

        assert request.threshold_brier == 0.20
        assert request.threshold_accuracy == 0.15
        assert request.category is None
        assert request.min_decisions == 5

    def test_from_dict_custom_values(self) -> None:
        """Test custom values are parsed."""
        request = CheckDriftRequest.from_dict({
            "thresholdBrier": 0.30,
            "thresholdAccuracy": 0.10,
            "category": "architecture",
            "minDecisions": 10,
        })

        assert request.threshold_brier == 0.30
        assert request.threshold_accuracy == 0.10
        assert request.category == "architecture"
        assert request.min_decisions == 10
