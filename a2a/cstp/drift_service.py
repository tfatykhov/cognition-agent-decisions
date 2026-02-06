"""Drift detection service for CSTP.

Compares recent calibration (30d) against historical baseline (90d+)
and generates alerts when performance degrades.
"""

from dataclasses import dataclass, field
from typing import Any

from .calibration_service import (
    CalibrationResult,
    calculate_calibration,
    get_reviewed_decisions,
    window_to_dates,
)


@dataclass
class DriftAlert:
    """A calibration drift alert."""

    type: str  # brier_degradation, accuracy_drop
    category: str | None
    recent_value: float
    historical_value: float
    change_pct: float
    severity: str  # info, warning, error
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "category": self.category,
            "recentValue": self.recent_value,
            "historicalValue": self.historical_value,
            "changePct": round(self.change_pct, 1),
            "severity": self.severity,
            "message": self.message,
        }


@dataclass
class WindowStats:
    """Stats for a time window."""

    window: str
    brier_score: float
    accuracy: float
    decisions: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "window": self.window,
            "brierScore": self.brier_score,
            "accuracy": self.accuracy,
            "decisions": self.decisions,
        }


@dataclass
class CheckDriftRequest:
    """Request for drift check."""

    threshold_brier: float = 0.20  # 20% degradation triggers alert
    threshold_accuracy: float = 0.15  # 15% drop triggers alert
    category: str | None = None
    project: str | None = None
    min_decisions: int = 5  # Minimum decisions per period

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CheckDriftRequest":
        """Create from dictionary (JSON-RPC params)."""
        return cls(
            threshold_brier=float(data.get("thresholdBrier", 0.20)),
            threshold_accuracy=float(data.get("thresholdAccuracy", 0.15)),
            category=data.get("category"),
            project=data.get("project"),
            min_decisions=int(data.get("minDecisions", 5)),
        )


@dataclass
class CheckDriftResponse:
    """Response with drift detection results."""

    drift_detected: bool
    recent: WindowStats | None
    historical: WindowStats | None
    alerts: list[DriftAlert] = field(default_factory=list)
    recommendations: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "driftDetected": self.drift_detected,
            "recent": self.recent.to_dict() if self.recent else None,
            "historical": self.historical.to_dict() if self.historical else None,
            "alerts": [a.to_dict() for a in self.alerts],
            "recommendations": self.recommendations,
        }


def detect_drift_alerts(
    recent: CalibrationResult,
    historical: CalibrationResult,
    threshold_brier: float,
    threshold_accuracy: float,
    category: str | None,
) -> list[DriftAlert]:
    """Detect calibration drift between periods.

    Args:
        recent: Calibration stats for recent period (30d).
        historical: Calibration stats for historical period (90d+).
        threshold_brier: Brier score degradation threshold (e.g., 0.20 = 20%).
        threshold_accuracy: Accuracy drop threshold (e.g., 0.15 = 15%).
        category: Optional category for alert context.

    Returns:
        List of drift alerts.
    """
    alerts: list[DriftAlert] = []

    # Minimum absolute difference to avoid false positives on small values
    min_brier_diff = 0.03  # At least 0.03 absolute difference required
    min_accuracy_diff = 0.05  # At least 5% absolute accuracy drop required

    # Check Brier score degradation (higher is worse)
    brier_diff = recent.brier_score - historical.brier_score
    if historical.brier_score > 0.001 and brier_diff >= min_brier_diff:
        brier_change = brier_diff / historical.brier_score
        if brier_change > threshold_brier:
            severity = "error" if brier_change > 0.5 else "warning"
            cat_prefix = f"{category.title()} decisions: " if category else ""
            alerts.append(DriftAlert(
                type="brier_degradation",
                category=category,
                recent_value=recent.brier_score,
                historical_value=historical.brier_score,
                change_pct=brier_change * 100,
                severity=severity,
                message=f"{cat_prefix}Brier score degraded {brier_change*100:.0f}% ({historical.brier_score:.2f} → {recent.brier_score:.2f})",
            ))

    # Check accuracy drop (lower is worse)
    accuracy_diff = historical.accuracy - recent.accuracy
    if historical.accuracy > 0.001 and accuracy_diff >= min_accuracy_diff:
        accuracy_change = accuracy_diff / historical.accuracy
        if accuracy_change > threshold_accuracy:
            severity = "error" if accuracy_change > 0.25 else "warning"
            cat_prefix = f"{category.title()} decisions: " if category else ""
            alerts.append(DriftAlert(
                type="accuracy_drop",
                category=category,
                recent_value=recent.accuracy,
                historical_value=historical.accuracy,
                change_pct=-accuracy_change * 100,
                severity=severity,
                message=f"{cat_prefix}Accuracy dropped {accuracy_change*100:.0f}% ({historical.accuracy*100:.0f}% → {recent.accuracy*100:.0f}%)",
            ))

    return alerts


def generate_drift_recommendations(alerts: list[DriftAlert]) -> list[dict[str, str]]:
    """Generate recommendations based on drift alerts.

    Args:
        alerts: List of detected drift alerts.

    Returns:
        List of recommendation dictionaries.
    """
    recommendations: list[dict[str, str]] = []
    seen_types: set[str] = set()

    for alert in alerts:
        if alert.type in seen_types:
            continue
        seen_types.add(alert.type)

        if alert.type == "brier_degradation":
            recommendations.append({
                "type": "recalibrate",
                "message": "Consider adjusting confidence estimates - you may be overconfident recently",
                "severity": "info",
            })
        elif alert.type == "accuracy_drop":
            recommendations.append({
                "type": "review_process",
                "message": "Review recent decisions - accuracy has declined from historical baseline",
                "severity": "info",
            })

    return recommendations


async def check_drift(
    request: CheckDriftRequest,
    decisions_path: str | None = None,
) -> CheckDriftResponse:
    """Check for calibration drift between recent and historical periods.

    Compares 30-day window against 90-day+ baseline to detect degradation.

    Args:
        request: Drift check request with thresholds and filters.
        decisions_path: Override for decisions directory.

    Returns:
        CheckDriftResponse with drift status, stats, and alerts.
    """
    # Get recent decisions (last 30 days)
    recent_since, recent_until = window_to_dates("30d")
    recent_decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        category=request.category,
        project=request.project,
        since=recent_since,
        until=recent_until,
    )

    # Get historical decisions (30-120 days ago, bounded for performance)
    historical_since, _ = window_to_dates("120d")  # 120 days ago
    historical_decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        category=request.category,
        project=request.project,
        since=historical_since,  # Start from 120 days ago
        until=recent_since,  # Up to where recent window starts
    )

    # Need minimum decisions for meaningful comparison
    if len(recent_decisions) < request.min_decisions:
        return CheckDriftResponse(
            drift_detected=False,
            recent=None,
            historical=None,
            recommendations=[{
                "type": "insufficient_data",
                "message": f"Need at least {request.min_decisions} recent decisions for drift detection (found {len(recent_decisions)})",
                "severity": "info",
            }],
        )

    if len(historical_decisions) < request.min_decisions:
        return CheckDriftResponse(
            drift_detected=False,
            recent=None,
            historical=None,
            recommendations=[{
                "type": "insufficient_data",
                "message": f"Need at least {request.min_decisions} historical decisions for drift detection (found {len(historical_decisions)})",
                "severity": "info",
            }],
        )

    # Calculate calibration for both periods
    recent_cal = calculate_calibration(recent_decisions)
    historical_cal = calculate_calibration(historical_decisions)

    if not recent_cal or not historical_cal:
        return CheckDriftResponse(
            drift_detected=False,
            recent=None,
            historical=None,
            recommendations=[{
                "type": "calculation_error",
                "message": "Could not calculate calibration metrics",
                "severity": "warning",
            }],
        )

    recent_stats = WindowStats(
        window="30d",
        brier_score=recent_cal.brier_score,
        accuracy=recent_cal.accuracy,
        decisions=len(recent_decisions),
    )

    historical_stats = WindowStats(
        window="90d+",
        brier_score=historical_cal.brier_score,
        accuracy=historical_cal.accuracy,
        decisions=len(historical_decisions),
    )

    # Detect drift
    alerts = detect_drift_alerts(
        recent_cal,
        historical_cal,
        request.threshold_brier,
        request.threshold_accuracy,
        request.category,
    )

    # Generate recommendations
    recommendations = generate_drift_recommendations(alerts)

    return CheckDriftResponse(
        drift_detected=len(alerts) > 0,
        recent=recent_stats,
        historical=historical_stats,
        alerts=alerts,
        recommendations=recommendations,
    )
