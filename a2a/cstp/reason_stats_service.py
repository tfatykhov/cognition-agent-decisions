"""Reason-type calibration statistics service for CSTP.

Analyzes which reason types (analysis, pattern, empirical, etc.) correlate
with better decision outcomes. Implements Minsky Ch 18 insight: parallel
bundles of independent reasons > single serial chains.

Key questions this answers:
- Which reason types predict success best?
- Do decisions with more diverse reason types have better outcomes?
- What's the optimal number of independent reasons?
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .decision_service import DECISIONS_PATH


# Valid reason types from the schema
VALID_REASON_TYPES = {
    "analysis",
    "pattern",
    "authority",
    "intuition",
    "empirical",
    "analogy",
    "elimination",
    "constraint",
}


@dataclass
class ReasonTypeStats:
    """Statistics for a single reason type.

    Attributes:
        reason_type: The type of reasoning (analysis, pattern, etc.).
        total_uses: How many decisions used this reason type.
        reviewed_uses: How many reviewed decisions used it.
        success_count: Decisions with this type that succeeded.
        partial_count: Decisions with this type that partially succeeded.
        failure_count: Decisions with this type that failed.
        success_rate: Proportion of successful outcomes (partial = 0.5).
        avg_confidence: Average confidence when this type is used.
        avg_strength: Average reason strength when this type is used.
        brier_score: Brier score for decisions using this type.
    """

    reason_type: str
    total_uses: int = 0
    reviewed_uses: int = 0
    success_count: int = 0
    partial_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_confidence: float = 0.0
    avg_strength: float = 0.0
    brier_score: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        result: dict[str, Any] = {
            "reasonType": self.reason_type,
            "totalUses": self.total_uses,
            "reviewedUses": self.reviewed_uses,
            "successCount": self.success_count,
            "partialCount": self.partial_count,
            "failureCount": self.failure_count,
            "successRate": round(self.success_rate, 3),
            "avgConfidence": round(self.avg_confidence, 3),
            "avgStrength": round(self.avg_strength, 3),
        }
        if self.brier_score is not None:
            result["brierScore"] = round(self.brier_score, 4)
        return result


@dataclass
class DiversityStats:
    """Statistics about reason type diversity (Minsky Ch 18 parallel bundles).

    Attributes:
        avg_types_per_decision: Average number of distinct reason types per decision.
        avg_reasons_per_decision: Average total reasons per decision.
        diversity_buckets: Outcome stats grouped by number of distinct reason types.
    """

    avg_types_per_decision: float = 0.0
    avg_reasons_per_decision: float = 0.0
    diversity_buckets: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "avgTypesPerDecision": round(self.avg_types_per_decision, 2),
            "avgReasonsPerDecision": round(self.avg_reasons_per_decision, 2),
            "diversityBuckets": self.diversity_buckets,
        }


@dataclass
class ReasonStatsRecommendation:
    """Recommendation based on reason-type analysis.

    Attributes:
        type: Recommendation type identifier.
        message: Human-readable recommendation.
        severity: info, warning, or error.
    """

    type: str
    message: str
    severity: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type,
            "message": self.message,
            "severity": self.severity,
        }


@dataclass
class GetReasonStatsRequest:
    """Request for reason-type calibration stats.

    Attributes:
        category: Filter by decision category.
        stakes: Filter by stakes level.
        project: Filter by project (owner/repo).
        since: Only decisions after this ISO date.
        until: Only decisions before this ISO date.
        min_reviewed: Minimum reviewed decisions to include a reason type.
    """

    category: str | None = None
    stakes: str | None = None
    project: str | None = None
    since: str | None = None
    until: str | None = None
    min_reviewed: int = 3

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GetReasonStatsRequest":
        """Create from dictionary (JSON-RPC params)."""
        filters = data.get("filters", {})
        return cls(
            category=filters.get("category"),
            stakes=filters.get("stakes"),
            project=filters.get("project"),
            since=filters.get("since"),
            until=filters.get("until"),
            min_reviewed=data.get("minReviewed", 3),
        )


@dataclass
class GetReasonStatsResponse:
    """Response with reason-type calibration statistics.

    Attributes:
        by_reason_type: Per-type statistics.
        diversity: Diversity analysis (parallel bundles).
        recommendations: Actionable recommendations.
        total_decisions: Total decisions analyzed.
        reviewed_decisions: Decisions with outcomes.
        query_time: When the query was executed.
    """

    by_reason_type: list[ReasonTypeStats] = field(default_factory=list)
    diversity: DiversityStats | None = None
    recommendations: list[ReasonStatsRecommendation] = field(default_factory=list)
    total_decisions: int = 0
    reviewed_decisions: int = 0
    query_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "byReasonType": [r.to_dict() for r in self.by_reason_type],
            "diversity": self.diversity.to_dict() if self.diversity else None,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "totalDecisions": self.total_decisions,
            "reviewedDecisions": self.reviewed_decisions,
            "queryTime": self.query_time,
        }


async def load_decisions_with_reasons(
    decisions_path: str | None = None,
    category: str | None = None,
    stakes: str | None = None,
    project: str | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """Load all decisions that have reasons attached.

    Args:
        decisions_path: Override for decisions directory.
        category: Filter by category.
        stakes: Filter by stakes level.
        project: Filter by project.
        since: Only decisions after this ISO date.
        until: Only decisions before this ISO date.

    Returns:
        List of decision data dictionaries with reasons.
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

            # Must have reasons
            reasons = data.get("reasons", [])
            if not reasons:
                continue

            # Apply filters
            if category and data.get("category") != category:
                continue
            if stakes and data.get("stakes") != stakes:
                continue
            if project and data.get("project") != project:
                continue

            # Date filters — normalize to YYYY-MM-DD for consistent comparison
            decision_date = data.get("date", data.get("created_at", ""))
            if isinstance(decision_date, str):
                date_str = decision_date[:10]
            else:
                date_str = ""

            since_normalized = since[:10] if since else None
            until_normalized = until[:10] if until else None

            if since_normalized and date_str < since_normalized:
                continue
            if until_normalized and date_str > until_normalized:
                continue

            decisions.append(data)

        except Exception:
            continue

    return decisions


def calculate_reason_type_stats(
    decisions: list[dict[str, Any]],
    min_reviewed: int = 3,
) -> list[ReasonTypeStats]:
    """Calculate per-reason-type calibration statistics.

    Args:
        decisions: List of decisions with reasons.
        min_reviewed: Minimum reviewed decisions to include a type.

    Returns:
        List of ReasonTypeStats sorted by success rate descending.
    """
    # Collect per-type data
    type_data: dict[str, dict[str, Any]] = {}

    for d in decisions:
        reasons = d.get("reasons", [])
        outcome = d.get("outcome")
        confidence = float(d.get("confidence", 0.5))
        is_reviewed = d.get("status") == "reviewed" and outcome is not None

        # Get unique reason types in this decision
        seen_types: set[str] = set()
        for r in reasons:
            rtype = r.get("type", "unknown")
            strength = float(r.get("strength", 0.8))

            if rtype not in type_data:
                type_data[rtype] = {
                    "total": 0,
                    "reviewed": 0,
                    "successes": 0,
                    "partials": 0,
                    "failures": 0,
                    "confidences": [],
                    "strengths": [],
                    "brier_pairs": [],  # (confidence, outcome) pairs
                }

            # Count each type once per decision (not per reason)
            if rtype not in seen_types:
                seen_types.add(rtype)
                type_data[rtype]["total"] += 1
                type_data[rtype]["confidences"].append(confidence)

                if is_reviewed:
                    type_data[rtype]["reviewed"] += 1
                    if outcome == "success":
                        type_data[rtype]["successes"] += 1
                        type_data[rtype]["brier_pairs"].append((confidence, 1.0))
                    elif outcome == "partial":
                        type_data[rtype]["partials"] += 1
                        type_data[rtype]["brier_pairs"].append((confidence, 0.5))
                    else:
                        type_data[rtype]["failures"] += 1
                        type_data[rtype]["brier_pairs"].append((confidence, 0.0))

            type_data[rtype]["strengths"].append(strength)

    # Build stats
    stats: list[ReasonTypeStats] = []
    for rtype, data in type_data.items():
        reviewed = data["reviewed"]

        # Calculate success rate
        if reviewed > 0:
            success_rate = (
                data["successes"] + data["partials"] * 0.5
            ) / reviewed
        else:
            success_rate = 0.0

        # Calculate Brier score
        brier = None
        if reviewed >= min_reviewed:
            pairs = data["brier_pairs"]
            brier = sum(
                (c - o) ** 2 for c, o in pairs
            ) / len(pairs)

        # Average confidence and strength
        avg_conf = (
            sum(data["confidences"]) / len(data["confidences"])
            if data["confidences"]
            else 0.0
        )
        avg_strength = (
            sum(data["strengths"]) / len(data["strengths"])
            if data["strengths"]
            else 0.0
        )

        stats.append(
            ReasonTypeStats(
                reason_type=rtype,
                total_uses=data["total"],
                reviewed_uses=reviewed,
                success_count=data["successes"],
                partial_count=data["partials"],
                failure_count=data["failures"],
                success_rate=success_rate,
                avg_confidence=avg_conf,
                avg_strength=avg_strength,
                brier_score=brier,
            )
        )

    # Sort by success rate descending (reviewed types first)
    stats.sort(
        key=lambda s: (s.reviewed_uses >= min_reviewed, s.success_rate),
        reverse=True,
    )

    return stats


def calculate_diversity_stats(
    decisions: list[dict[str, Any]],
) -> DiversityStats:
    """Calculate reason diversity statistics (Minsky Ch 18).

    Measures whether decisions with more diverse reason types
    (parallel bundles) have better outcomes.

    Args:
        decisions: List of decisions with reasons.

    Returns:
        DiversityStats with bucket-level outcome data.
    """
    # Per-decision: count unique reason types and total reasons
    diversity_data: dict[int, list[dict[str, Any]]] = {}  # n_types -> decisions
    total_types = 0
    total_reasons = 0

    for d in decisions:
        reasons = d.get("reasons", [])
        if not reasons:
            continue

        unique_types = {r.get("type", "unknown") for r in reasons}
        n_types = len(unique_types)
        n_reasons = len(reasons)

        total_types += n_types
        total_reasons += n_reasons

        if n_types not in diversity_data:
            diversity_data[n_types] = []
        diversity_data[n_types].append(d)

    n_decisions = len(decisions) if decisions else 1  # avoid div by zero

    # Build diversity buckets
    buckets: list[dict[str, Any]] = []
    for n_types in sorted(diversity_data.keys()):
        bucket_decisions = diversity_data[n_types]
        reviewed = [
            d for d in bucket_decisions
            if d.get("status") == "reviewed" and d.get("outcome") is not None
        ]

        if not reviewed:
            buckets.append({
                "distinctReasonTypes": n_types,
                "totalDecisions": len(bucket_decisions),
                "reviewedDecisions": 0,
                "successRate": None,
                "avgConfidence": round(
                    sum(float(d.get("confidence", 0.5)) for d in bucket_decisions)
                    / len(bucket_decisions),
                    3,
                ),
            })
            continue

        successes = sum(1 for d in reviewed if d.get("outcome") == "success")
        partials = sum(1 for d in reviewed if d.get("outcome") == "partial")
        success_rate = (successes + partials * 0.5) / len(reviewed)

        avg_conf = sum(
            float(d.get("confidence", 0.5)) for d in reviewed
        ) / len(reviewed)

        # Brier score for this bucket
        brier_sum = 0.0
        for d in reviewed:
            conf = float(d.get("confidence", 0.5))
            outcome_val = (
                1.0 if d.get("outcome") == "success"
                else 0.5 if d.get("outcome") == "partial"
                else 0.0
            )
            brier_sum += (conf - outcome_val) ** 2
        brier = brier_sum / len(reviewed)

        buckets.append({
            "distinctReasonTypes": n_types,
            "totalDecisions": len(bucket_decisions),
            "reviewedDecisions": len(reviewed),
            "successRate": round(success_rate, 3),
            "avgConfidence": round(avg_conf, 3),
            "brierScore": round(brier, 4),
        })

    return DiversityStats(
        avg_types_per_decision=round(total_types / n_decisions, 2),
        avg_reasons_per_decision=round(total_reasons / n_decisions, 2),
        diversity_buckets=buckets,
    )


def generate_reason_recommendations(
    type_stats: list[ReasonTypeStats],
    diversity: DiversityStats,
    min_reviewed: int = 3,
) -> list[ReasonStatsRecommendation]:
    """Generate actionable recommendations from reason-type analysis.

    Args:
        type_stats: Per-type calibration stats.
        diversity: Diversity analysis.
        min_reviewed: Minimum reviewed decisions for type-level recs.

    Returns:
        List of recommendations.
    """
    recs: list[ReasonStatsRecommendation] = []

    # Find best and worst performing types (with enough data)
    reviewed_stats = [s for s in type_stats if s.reviewed_uses >= min_reviewed]

    if reviewed_stats:
        best = max(reviewed_stats, key=lambda s: s.success_rate)
        worst = min(reviewed_stats, key=lambda s: s.success_rate)

        if best.success_rate > worst.success_rate + 0.15:
            recs.append(
                ReasonStatsRecommendation(
                    type="best_reason_type",
                    message=(
                        f"'{best.reason_type}' reasoning has {best.success_rate * 100:.0f}% "
                        f"success rate ({best.reviewed_uses} decisions), while "
                        f"'{worst.reason_type}' has {worst.success_rate * 100:.0f}%. "
                        f"Consider relying more on {best.reason_type}-based reasoning."
                    ),
                    severity="info",
                )
            )

    # Check for types with high confidence but low success
    for s in reviewed_stats:
        if s.avg_confidence > 0.8 and s.success_rate < 0.6:
            recs.append(
                ReasonStatsRecommendation(
                    type="overconfident_type",
                    message=(
                        f"'{s.reason_type}' reasoning: avg confidence {s.avg_confidence * 100:.0f}% "
                        f"but only {s.success_rate * 100:.0f}% success rate. "
                        f"Lower confidence when relying primarily on {s.reason_type}."
                    ),
                    severity="warning",
                )
            )

    # Diversity recommendations (Minsky Ch 18)
    if diversity.avg_types_per_decision < 1.5:
        recs.append(
            ReasonStatsRecommendation(
                type="low_diversity",
                message=(
                    f"Average {diversity.avg_types_per_decision:.1f} distinct reason types "
                    f"per decision. Minsky Ch 18: parallel bundles of ≥2 independent "
                    f"reason types are more robust than single-type chains."
                ),
                severity="warning",
            )
        )

    # Check if more diverse decisions actually perform better
    reviewed_buckets = [
        b for b in diversity.diversity_buckets
        if b.get("reviewedDecisions", 0) >= 2 and b.get("successRate") is not None
    ]
    if len(reviewed_buckets) >= 2:
        # Compare single-type vs multi-type decisions
        single = [b for b in reviewed_buckets if b["distinctReasonTypes"] == 1]
        multi = [b for b in reviewed_buckets if b["distinctReasonTypes"] >= 2]

        if single and multi:
            single_rate = single[0]["successRate"]
            multi_rate = max(b["successRate"] for b in multi)
            multi_n = sum(b["reviewedDecisions"] for b in multi)

            if multi_rate > single_rate + 0.1:
                recs.append(
                    ReasonStatsRecommendation(
                        type="diversity_benefit",
                        message=(
                            f"Multi-type reasoning ({multi_rate * 100:.0f}% success, n={multi_n}) "
                            f"outperforms single-type ({single_rate * 100:.0f}%). "
                            f"Parallel bundles work — use ≥2 independent reason types."
                        ),
                        severity="info",
                    )
                )
            elif single_rate > multi_rate + 0.1:
                recs.append(
                    ReasonStatsRecommendation(
                        type="diversity_no_benefit",
                        message=(
                            f"Single-type reasoning ({single_rate * 100:.0f}% success) "
                            f"currently outperforms multi-type ({multi_rate * 100:.0f}%). "
                            f"Quality of reasons may matter more than quantity here."
                        ),
                        severity="info",
                    )
                )

    # Rarely used types
    all_used = {s.reason_type for s in type_stats}
    unused = VALID_REASON_TYPES - all_used
    if unused:
        recs.append(
            ReasonStatsRecommendation(
                type="unused_types",
                message=(
                    f"Never-used reason types: {', '.join(sorted(unused))}. "
                    f"Consider whether these perspectives could strengthen decisions."
                ),
                severity="info",
            )
        )

    return recs


async def get_reason_stats(
    request: GetReasonStatsRequest,
    decisions_path: str | None = None,
) -> GetReasonStatsResponse:
    """Get reason-type calibration statistics.

    Args:
        request: The request with filters.
        decisions_path: Override for decisions directory.

    Returns:
        Response with per-type stats, diversity analysis, and recommendations.
    """
    now = datetime.now(UTC)

    # Load decisions with reasons
    decisions = await load_decisions_with_reasons(
        decisions_path=decisions_path,
        category=request.category,
        stakes=request.stakes,
        project=request.project,
        since=request.since,
        until=request.until,
    )

    reviewed = [
        d for d in decisions
        if d.get("status") == "reviewed" and d.get("outcome") is not None
    ]

    # Calculate per-type stats
    type_stats = calculate_reason_type_stats(decisions, request.min_reviewed)

    # Calculate diversity stats
    diversity = calculate_diversity_stats(decisions)

    # Generate recommendations
    recommendations = generate_reason_recommendations(
        type_stats, diversity, request.min_reviewed
    )

    return GetReasonStatsResponse(
        by_reason_type=type_stats,
        diversity=diversity,
        recommendations=recommendations,
        total_decisions=len(decisions),
        reviewed_decisions=len(reviewed),
        query_time=now.isoformat(),
    )
