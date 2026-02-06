"""Calibration service for CSTP.

Calculates confidence calibration statistics from reviewed decisions.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

from .decision_service import DECISIONS_PATH


def window_to_dates(window: str | None) -> tuple[str | None, str | None]:
    """Convert window shorthand to since/until dates.

    Args:
        window: "30d", "60d", "90d", or None/"all"

    Returns:
        (since_date, until_date) as ISO date strings (YYYY-MM-DD)
    """
    if not window or window == "all":
        return None, None

    now = datetime.now(UTC)
    until_date = now.strftime("%Y-%m-%d")

    days_map = {"30d": 30, "60d": 60, "90d": 90}
    days = days_map.get(window)

    if days is None:
        return None, None

    since = now - timedelta(days=days)
    since_date = since.strftime("%Y-%m-%d")
    return since_date, until_date


@dataclass
class ConfidenceBucket:
    """Calibration statistics for a confidence range."""

    bucket: str
    decisions: int
    success_rate: float
    expected_rate: float
    gap: float
    interpretation: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "bucket": self.bucket,
            "decisions": self.decisions,
            "successRate": self.success_rate,
            "expectedRate": self.expected_rate,
            "gap": self.gap,
            "interpretation": self.interpretation,
        }


@dataclass
class CalibrationResult:
    """Overall calibration statistics."""

    brier_score: float
    accuracy: float
    total_decisions: int
    reviewed_decisions: int
    calibration_gap: float
    interpretation: str
    # F014: Rolling window metadata
    window: str | None = None
    period_start: str | None = None
    period_end: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "brierScore": self.brier_score,
            "accuracy": self.accuracy,
            "totalDecisions": self.total_decisions,
            "reviewedDecisions": self.reviewed_decisions,
            "calibrationGap": self.calibration_gap,
            "interpretation": self.interpretation,
        }
        # F014: Add window metadata if present
        if self.window:
            result["window"] = self.window
        if self.period_start:
            result["periodStart"] = self.period_start
        if self.period_end:
            result["periodEnd"] = self.period_end
        return result


@dataclass
class CalibrationRecommendation:
    """Actionable recommendation based on calibration."""

    type: str
    message: str
    severity: str  # info, warning, error

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class GetCalibrationRequest:
    """Request for calibration statistics."""

    agent: str | None = None
    category: str | None = None
    stakes: str | None = None
    since: str | None = None
    until: str | None = None
    min_decisions: int = 5
    group_by: str | None = None
    # F010: Project context filters
    project: str | None = None
    feature: str | None = None
    # F014: Rolling window
    window: str | None = None  # "30d", "60d", "90d", or "all"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GetCalibrationRequest":
        """Create from dictionary (JSON-RPC params)."""
        filters = data.get("filters", {})
        return cls(
            agent=filters.get("agent"),
            category=filters.get("category"),
            stakes=filters.get("stakes"),
            since=filters.get("since"),
            until=filters.get("until"),
            min_decisions=filters.get("minDecisions", 5),
            group_by=data.get("groupBy"),
            # F010: Project context filters
            project=filters.get("project"),
            feature=filters.get("feature"),
            # F014: Rolling window (top-level param)
            window=data.get("window"),
        )


@dataclass
class GetCalibrationResponse:
    """Response with calibration statistics."""

    overall: CalibrationResult | None
    by_confidence_bucket: list[ConfidenceBucket] = field(default_factory=list)
    recommendations: list[CalibrationRecommendation] = field(default_factory=list)
    query_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "overall": self.overall.to_dict() if self.overall else None,
            "byConfidenceBucket": [b.to_dict() for b in self.by_confidence_bucket],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "queryTime": self.query_time,
        }


async def get_reviewed_decisions(
    decisions_path: str | None = None,
    agent: str | None = None,
    category: str | None = None,
    stakes: str | None = None,
    since: str | None = None,
    until: str | None = None,
    # F010: Project context filters
    project: str | None = None,
    feature: str | None = None,
) -> list[dict[str, Any]]:
    """Get all reviewed decisions matching filters.

    Args:
        decisions_path: Override for decisions directory.
        agent: Filter by recorded_by field.
        category: Filter by category.
        stakes: Filter by stakes level.
        since: Only decisions after this ISO date.
        until: Only decisions before this ISO date.
        project: Filter by project (owner/repo).
        feature: Filter by feature name.

    Returns:
        List of decision data dictionaries.
    """
    base = Path(decisions_path or DECISIONS_PATH)
    decisions: list[dict[str, Any]] = []

    if not base.exists():
        return decisions

    for yaml_file in base.rglob("*-decision-*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            # Must be reviewed with outcome
            if data.get("status") != "reviewed":
                continue
            if "outcome" not in data:
                continue

            # Apply filters
            if agent and data.get("recorded_by") != agent:
                continue
            if category and data.get("category") != category:
                continue
            if stakes and data.get("stakes") != stakes:
                continue

            # F010: Project context filters
            if project and data.get("project") != project:
                continue
            if feature and data.get("feature") != feature:
                continue

            # Date filters
            decision_date = data.get("date", "")
            if isinstance(decision_date, str):
                date_str = decision_date[:10]  # YYYY-MM-DD
            else:
                date_str = ""

            if since and date_str < since:
                continue
            if until and date_str > until:
                continue

            decisions.append(data)

        except Exception:
            # Skip corrupt files
            continue

    return decisions


def calculate_calibration(decisions: list[dict[str, Any]]) -> CalibrationResult | None:
    """Calculate overall calibration metrics.

    Args:
        decisions: List of reviewed decision data.

    Returns:
        CalibrationResult or None if insufficient data.
    """
    if len(decisions) < 3:
        return None

    outcomes: list[float] = []
    confidences: list[float] = []

    for d in decisions:
        confidence = float(d.get("confidence", 0.5))
        outcome_str = d.get("outcome", "")

        # Map outcome to numeric value
        if outcome_str == "success":
            outcome = 1.0
        elif outcome_str == "partial":
            outcome = 0.5
        else:  # failure, abandoned
            outcome = 0.0

        outcomes.append(outcome)
        confidences.append(confidence)

    # Brier score: mean squared error between confidence and outcome
    brier = sum((c - o) ** 2 for c, o in zip(confidences, outcomes, strict=True)) / len(decisions)

    # Accuracy: mean outcome value (partial = 0.5, success = 1.0, failure = 0.0)
    accuracy = sum(outcomes) / len(decisions)

    # Calibration gap: actual success rate - average confidence
    avg_confidence = sum(confidences) / len(confidences)
    gap = accuracy - avg_confidence

    # Interpretation
    if abs(gap) < 0.05:
        interpretation = "well_calibrated"
    elif gap < -0.10:
        interpretation = "overconfident"
    elif gap < 0:
        interpretation = "slightly_overconfident"
    elif gap > 0.10:
        interpretation = "underconfident"
    else:
        interpretation = "slightly_underconfident"

    return CalibrationResult(
        brier_score=round(brier, 3),
        accuracy=round(accuracy, 3),
        total_decisions=len(decisions),
        reviewed_decisions=len(decisions),
        calibration_gap=round(gap, 3),
        interpretation=interpretation,
    )


def calculate_buckets(decisions: list[dict[str, Any]]) -> list[ConfidenceBucket]:
    """Calculate calibration by confidence bucket.

    Args:
        decisions: List of reviewed decision data.

    Returns:
        List of ConfidenceBucket statistics.
    """
    bucket_defs = {
        "0.9-1.0": {"min": 0.9, "max": 1.01, "expected": 0.95},
        "0.7-0.9": {"min": 0.7, "max": 0.9, "expected": 0.80},
        "0.5-0.7": {"min": 0.5, "max": 0.7, "expected": 0.60},
        "0.0-0.5": {"min": 0.0, "max": 0.5, "expected": 0.25},
    }

    buckets: dict[str, list[dict[str, Any]]] = {name: [] for name in bucket_defs}

    for d in decisions:
        conf = float(d.get("confidence", 0.5))
        for name, bucket in bucket_defs.items():
            if bucket["min"] <= conf < bucket["max"]:
                buckets[name].append(d)
                break

    results: list[ConfidenceBucket] = []

    for name in ["0.9-1.0", "0.7-0.9", "0.5-0.7", "0.0-0.5"]:
        bucket_decisions = buckets[name]
        if len(bucket_decisions) < 3:
            continue

        successes = sum(
            1 for d in bucket_decisions if d.get("outcome") == "success"
        )
        partials = sum(
            0.5 for d in bucket_decisions if d.get("outcome") == "partial"
        )
        success_rate = (successes + partials) / len(bucket_decisions)
        expected = bucket_defs[name]["expected"]
        gap = success_rate - expected

        if abs(gap) < 0.10:
            interpretation = "well_calibrated"
        elif gap < 0:
            interpretation = "overconfident"
        else:
            interpretation = "underconfident"

        results.append(
            ConfidenceBucket(
                bucket=name,
                decisions=len(bucket_decisions),
                success_rate=round(success_rate, 2),
                expected_rate=expected,
                gap=round(gap, 2),
                interpretation=interpretation,
            )
        )

    return results


def generate_recommendations(
    overall: CalibrationResult | None,
    buckets: list[ConfidenceBucket],
    min_decisions: int,
    total_found: int,
) -> list[CalibrationRecommendation]:
    """Generate actionable recommendations.

    Args:
        overall: Overall calibration result.
        buckets: Bucket-level calibration.
        min_decisions: Minimum decisions required.
        total_found: Total reviewed decisions found.

    Returns:
        List of recommendations.
    """
    recs: list[CalibrationRecommendation] = []

    if overall is None:
        recs.append(
            CalibrationRecommendation(
                type="insufficient_data",
                message=f"Only {total_found} reviewed decisions found. Need at least {min_decisions} for calibration.",
                severity="info",
            )
        )
        return recs

    # Overall calibration feedback
    if overall.interpretation == "overconfident":
        recs.append(
            CalibrationRecommendation(
                type="confidence_adjustment",
                message=f"You're overconfident by {abs(overall.calibration_gap) * 100:.0f}%. Consider lowering confidence estimates.",
                severity="warning",
            )
        )
    elif overall.interpretation == "slightly_overconfident":
        recs.append(
            CalibrationRecommendation(
                type="confidence_adjustment",
                message=f"Slightly overconfident by {abs(overall.calibration_gap) * 100:.0f}%. Minor adjustment may help.",
                severity="info",
            )
        )
    elif overall.interpretation == "underconfident":
        recs.append(
            CalibrationRecommendation(
                type="confidence_adjustment",
                message=f"You're underconfident by {overall.calibration_gap * 100:.0f}%. Trust yourself more!",
                severity="info",
            )
        )
    elif overall.interpretation == "well_calibrated":
        recs.append(
            CalibrationRecommendation(
                type="strength",
                message="Your overall calibration is good. Keep it up!",
                severity="info",
            )
        )

    # Brier score feedback
    if overall.brier_score < 0.10:
        recs.append(
            CalibrationRecommendation(
                type="brier_score",
                message=f"Excellent Brier score ({overall.brier_score:.2f}). Your predictions are very accurate.",
                severity="info",
            )
        )
    elif overall.brier_score > 0.25:
        recs.append(
            CalibrationRecommendation(
                type="brier_score",
                message=f"Brier score ({overall.brier_score:.2f}) indicates room for improvement. Review past decisions to identify patterns.",
                severity="warning",
            )
        )

    # Bucket-specific feedback
    for bucket in buckets:
        if bucket.interpretation == "overconfident" and bucket.gap < -0.15:
            recs.append(
                CalibrationRecommendation(
                    type="bucket_warning",
                    message=f"At {bucket.bucket} confidence, actual success is {bucket.success_rate * 100:.0f}%. Consider using ~{bucket.success_rate * 100:.0f}% instead.",
                    severity="warning",
                )
            )

    # Strength recognition
    well_calibrated = [b for b in buckets if b.interpretation == "well_calibrated"]
    if well_calibrated and len(well_calibrated) < len(buckets):
        ranges = ", ".join(b.bucket for b in well_calibrated)
        recs.append(
            CalibrationRecommendation(
                type="strength",
                message=f"Well calibrated in {ranges} range. Trust these estimates.",
                severity="info",
            )
        )

    return recs


async def get_calibration(
    request: GetCalibrationRequest,
    decisions_path: str | None = None,
) -> GetCalibrationResponse:
    """Get calibration statistics.

    Args:
        request: The calibration request with filters.
        decisions_path: Override for decisions directory.

    Returns:
        Calibration response with statistics and recommendations.
    """
    now = datetime.now(UTC)

    # F014: Convert window to date filters
    window_since, window_until = window_to_dates(request.window)

    # Window overrides explicit since/until if set
    effective_since = window_since or request.since
    effective_until = window_until or request.until

    # Get reviewed decisions
    decisions = await get_reviewed_decisions(
        decisions_path=decisions_path,
        agent=request.agent,
        category=request.category,
        stakes=request.stakes,
        since=effective_since,
        until=effective_until,
        # F010: Project context filters
        project=request.project,
        feature=request.feature,
    )

    # Calculate overall calibration
    overall = (
        calculate_calibration(decisions)
        if len(decisions) >= request.min_decisions
        else None
    )

    # F014: Add window metadata to result
    if overall and request.window:
        overall.window = request.window
        overall.period_start = effective_since
        overall.period_end = effective_until

    # Calculate bucket calibration
    buckets = calculate_buckets(decisions)

    # Generate recommendations
    recommendations = generate_recommendations(
        overall=overall,
        buckets=buckets,
        min_decisions=request.min_decisions,
        total_found=len(decisions),
    )

    return GetCalibrationResponse(
        overall=overall,
        by_confidence_bucket=buckets,
        recommendations=recommendations,
        query_time=now.isoformat(),
    )
