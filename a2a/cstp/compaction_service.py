"""F041: Memory Compaction service.

Implements time-based compaction levels for decision query responses.
Raw data is NEVER deleted — compaction only shapes what is returned.

Compaction levels:
- FULL (< 7 days): Complete decision with all fields
- SUMMARY (7-30 days): Decision text, outcome, pattern, confidence vs actual
- DIGEST (30-90 days): One-line summary
- WISDOM (90+ days): Statistical aggregates + extracted principles

CSTP methods:
- cstp.compact — Run compaction cycle (recalculate levels)
- cstp.getCompacted — Get decisions at appropriate compaction level
- cstp.setPreserve — Mark decision as never-compact
- cstp.getWisdom — Get category-level distilled principles
"""

import logging
import os
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import yaml

from .decision_service import find_decision
from .models import (
    COMPACTION_THRESHOLDS,
    CompactedDecision,
    CompactLevelCount,
    CompactRequest,
    CompactResponse,
    GetCompactedRequest,
    GetCompactedResponse,
    GetWisdomRequest,
    GetWisdomResponse,
    SetPreserveRequest,
    SetPreserveResponse,
    WisdomEntry,
    WisdomPrinciple,
)
from .query_service import load_all_decisions

logger = logging.getLogger("cstp.compaction")

# Outcome-to-confidence mapping for actual_confidence field
OUTCOME_CONFIDENCE: dict[str, float] = {
    "success": 1.0,
    "partial": 0.5,
    "failure": 0.0,
    "abandoned": 0.0,
}


def determine_compaction_level(
    decision: dict[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Determine the compaction level for a decision based on age.

    Rules:
    - preserve=True → always "full"
    - status="pending" (unreviewed) → always "full"
    - < 7 days → "full"
    - 7-30 days → "summary"
    - 30-90 days → "digest"
    - 90+ days → "wisdom"

    Args:
        decision: Raw decision dict from YAML.
        now: Current time (injectable for testing).

    Returns:
        Compaction level string: "full", "summary", "digest", or "wisdom".
    """
    # Preserved decisions always stay full
    if decision.get("preserve"):
        return "full"

    # Unreviewed decisions stay full (per spec)
    if decision.get("status") != "reviewed":
        return "full"

    if now is None:
        now = datetime.now(UTC)

    # Parse decision date
    date_str = str(decision.get("date") or decision.get("created_at") or "")
    if not date_str:
        return "full"

    try:
        # Handle both ISO datetime and date-only formats
        if "T" in date_str:
            decision_dt = datetime.fromisoformat(
                date_str.replace("Z", "+00:00")
            )
        else:
            decision_dt = datetime.fromisoformat(
                date_str[:10] + "T00:00:00+00:00"
            )
    except ValueError:
        return "full"

    age_days = (now - decision_dt).days

    if age_days < COMPACTION_THRESHOLDS["full"]:  # type: ignore[arg-type]
        return "full"
    if age_days < COMPACTION_THRESHOLDS["summary"]:  # type: ignore[arg-type]
        return "summary"
    if age_days < COMPACTION_THRESHOLDS["digest"]:  # type: ignore[arg-type]
        return "digest"
    return "wisdom"


def compact_decision(
    decision: dict[str, Any],
    level: str,
) -> CompactedDecision:
    """Shape a decision dict into a CompactedDecision at the given level.

    Args:
        decision: Raw decision dict from YAML.
        level: Target compaction level.

    Returns:
        CompactedDecision shaped to the requested level.
    """
    decision_id = str(decision.get("id", ""))[:8]
    decision_text = str(
        decision.get("summary") or decision.get("decision") or "Untitled"
    )
    category = str(decision.get("category", ""))
    date = str(decision.get("date") or decision.get("created_at") or "")[:10]
    preserved = bool(decision.get("preserve"))

    # Map outcome to actual_confidence
    outcome = decision.get("outcome")
    actual_confidence: float | None = None
    if outcome and outcome in OUTCOME_CONFIDENCE:
        actual_confidence = OUTCOME_CONFIDENCE[outcome]

    if level == "digest":
        # One-line summary: truncated decision text
        one_line = decision_text[:80]
        if len(decision_text) > 80:
            one_line = one_line[:77] + "..."
        return CompactedDecision(
            id=decision_id,
            level=level,
            decision=decision_text,
            category=category,
            date=date,
            preserved=preserved,
            one_line=one_line,
        )

    if level == "summary":
        return CompactedDecision(
            id=decision_id,
            level=level,
            decision=decision_text,
            category=category,
            date=date,
            preserved=preserved,
            outcome=outcome,
            confidence=decision.get("confidence"),
            actual_confidence=actual_confidence,
            pattern=decision.get("pattern"),
            stakes=decision.get("stakes"),
        )

    # full level — include everything
    reasons = decision.get("reasons")
    tags = decision.get("tags")
    if isinstance(tags, str):
        tags = tags.split(",")

    return CompactedDecision(
        id=decision_id,
        level="full",
        decision=decision_text,
        category=category,
        date=date,
        preserved=preserved,
        outcome=outcome,
        confidence=decision.get("confidence"),
        actual_confidence=actual_confidence,
        pattern=decision.get("pattern"),
        stakes=decision.get("stakes"),
        context=decision.get("context"),
        reasons=reasons,
        tags=tags,
        bridge=decision.get("bridge"),
        deliberation=decision.get("deliberation"),
    )


async def run_compaction(
    request: CompactRequest,
    preloaded_decisions: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> CompactResponse:
    """Run a compaction cycle — recalculate levels for all decisions.

    P1: Only determines and counts levels; does NOT write summaries
    or modify files. Raw data is always preserved.

    Args:
        request: Compaction request with optional category filter.
        preloaded_decisions: Pre-loaded decisions (for testing).

    Returns:
        CompactResponse with level counts and statistics.
    """
    decisions = preloaded_decisions
    if decisions is None:
        decisions = await load_all_decisions(category=request.category)

    levels = CompactLevelCount()
    preserved = 0
    errors: list[str] = []

    for d in decisions:
        if d.get("preserve"):
            preserved += 1

        try:
            level = determine_compaction_level(d, now=now)
            match level:
                case "full":
                    levels.full += 1
                case "summary":
                    levels.summary += 1
                case "digest":
                    levels.digest += 1
                case "wisdom":
                    levels.wisdom += 1
        except Exception as e:
            decision_id = str(d.get("id", "unknown"))[:8]
            errors.append(f"Error processing {decision_id}: {e}")

    total = levels.full + levels.summary + levels.digest + levels.wisdom

    return CompactResponse(
        compacted=total,
        preserved=preserved,
        levels=levels,
        dry_run=request.dry_run,
        errors=errors,
    )


async def get_compacted_decisions(
    request: GetCompactedRequest,
    preloaded_decisions: list[dict[str, Any]] | None = None,
    *,
    now: datetime | None = None,
) -> GetCompactedResponse:
    """Get decisions shaped at their appropriate compaction level.

    Args:
        request: Request with optional category/level filter.
        preloaded_decisions: Pre-loaded decisions (for testing).

    Returns:
        GetCompactedResponse with shaped decisions.
    """
    decisions = preloaded_decisions
    if decisions is None:
        decisions = await load_all_decisions(category=request.category)

    levels = CompactLevelCount()
    shaped: list[CompactedDecision] = []

    for d in decisions:
        level = determine_compaction_level(d, now=now)

        # Skip preserved if not included
        if d.get("preserve") and not request.include_preserved:
            continue

        # Filter by forced level
        if request.level and level != request.level:
            # Preserved decisions always included at full level
            if not (d.get("preserve") and request.level == "full"):
                continue

        # Don't return individual decisions at wisdom level — those are
        # aggregated via get_wisdom
        if level == "wisdom" and not request.level:
            match level:
                case "wisdom":
                    levels.wisdom += 1
            continue

        compacted = compact_decision(d, level)
        shaped.append(compacted)

        match level:
            case "full":
                levels.full += 1
            case "summary":
                levels.summary += 1
            case "digest":
                levels.digest += 1
            case "wisdom":
                levels.wisdom += 1

    # Sort by date descending
    shaped.sort(key=lambda c: c.date, reverse=True)
    shaped = shaped[:request.limit]

    return GetCompactedResponse(
        decisions=shaped,
        total=len(shaped),
        levels=levels,
    )


async def set_preserve(
    request: SetPreserveRequest,
) -> SetPreserveResponse:
    """Mark a decision as never-compact (or remove the mark).

    Sets the 'preserve' field in the decision YAML file.

    Args:
        request: Request with decision ID and preserve flag.

    Returns:
        SetPreserveResponse with success status.
    """
    result = await find_decision(request.decision_id)
    if not result:
        return SetPreserveResponse(
            success=False,
            decision_id=request.decision_id,
            preserve=request.preserve,
            error=f"Decision not found: {request.decision_id}",
        )

    file_path, data = result

    # Update preserve flag
    if request.preserve:
        data["preserve"] = True
    else:
        data.pop("preserve", None)

    # Write back atomically
    try:
        import tempfile
        temp_fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            dir=file_path.parent,
        )
        try:
            with os.fdopen(temp_fd, "w") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, file_path)
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise
    except Exception as e:
        return SetPreserveResponse(
            success=False,
            decision_id=request.decision_id,
            preserve=request.preserve,
            error=f"Failed to write: {e}",
        )

    return SetPreserveResponse(
        success=True,
        decision_id=request.decision_id,
        preserve=request.preserve,
    )


def build_wisdom(
    decisions: list[dict[str, Any]],
    min_decisions: int = 5,
    category_filter: str | None = None,
) -> list[WisdomEntry]:
    """Aggregate decisions into category-level wisdom entries.

    Only considers reviewed decisions at wisdom age (90+ days).
    Extracts key principles from patterns, identifies failure modes,
    and computes calibration metrics.

    Args:
        decisions: All decision dicts.
        min_decisions: Minimum reviewed decisions per category.
        category_filter: Optional single-category filter.

    Returns:
        List of WisdomEntry aggregates per category.
    """
    now = datetime.now(UTC)

    # Group reviewed decisions by category
    by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for d in decisions:
        if d.get("status") != "reviewed":
            continue

        category = str(d.get("category", ""))
        if not category:
            continue
        if category_filter and category != category_filter:
            continue

        # Only include wisdom-age decisions (90+ days)
        level = determine_compaction_level(d, now=now)
        if level != "wisdom":
            continue

        by_category[category].append(d)

    entries: list[WisdomEntry] = []
    for category, cat_decisions in sorted(by_category.items()):
        if len(cat_decisions) < min_decisions:
            continue

        # Calculate success rate
        outcomes = [d.get("outcome") for d in cat_decisions if d.get("outcome")]
        success_count = sum(1 for o in outcomes if o == "success")
        success_rate = (
            round(success_count / len(outcomes), 3) if outcomes else None
        )

        # Extract patterns as principles (grouped by text, counted)
        pattern_counts: dict[str, list[str]] = defaultdict(list)
        failure_patterns: dict[str, int] = defaultdict(int)

        for d in cat_decisions:
            pattern = d.get("pattern")
            if pattern:
                decision_id = str(d.get("id", ""))[:8]
                pattern_counts[pattern].append(decision_id)

                if d.get("outcome") in ("failure", "partial"):
                    failure_patterns[pattern] += 1

        principles = [
            WisdomPrinciple(
                text=text,
                confirmations=len(ids),
                example_ids=ids[:3],
            )
            for text, ids in sorted(
                pattern_counts.items(),
                key=lambda x: len(x[1]),
                reverse=True,
            )
            if len(ids) >= 2
        ][:5]  # Top 5 principles

        # Common failure mode
        common_failure: str | None = None
        if failure_patterns:
            common_failure = max(
                failure_patterns, key=failure_patterns.get  # type: ignore[arg-type]
            )

        # Average confidence
        confidences = [
            d.get("confidence")
            for d in cat_decisions
            if d.get("confidence") is not None
        ]
        avg_confidence = (
            round(sum(confidences) / len(confidences), 3)  # type: ignore[arg-type]
            if confidences
            else None
        )

        # Brier score (mean squared error of confidence vs outcome)
        brier_pairs: list[tuple[float, float]] = []
        for d in cat_decisions:
            conf = d.get("confidence")
            outcome = d.get("outcome")
            if conf is not None and outcome in OUTCOME_CONFIDENCE:
                actual = OUTCOME_CONFIDENCE[outcome]
                brier_pairs.append((conf, actual))

        brier_score: float | None = None
        if brier_pairs:
            brier_score = round(
                sum((c - a) ** 2 for c, a in brier_pairs) / len(brier_pairs),
                4,
            )

        entries.append(WisdomEntry(
            category=category,
            decisions=len(cat_decisions),
            success_rate=success_rate,
            key_principles=principles,
            common_failure_mode=common_failure,
            avg_confidence=avg_confidence,
            brier_score=brier_score,
        ))

    return entries


async def get_wisdom(
    request: GetWisdomRequest,
    preloaded_decisions: list[dict[str, Any]] | None = None,
) -> GetWisdomResponse:
    """Get category-level distilled principles.

    Args:
        request: Request with optional category filter and min_decisions.
        preloaded_decisions: Pre-loaded decisions (for testing).

    Returns:
        GetWisdomResponse with wisdom entries.
    """
    decisions = preloaded_decisions
    if decisions is None:
        decisions = await load_all_decisions(category=request.category)

    wisdom = build_wisdom(
        decisions,
        min_decisions=request.min_decisions,
        category_filter=request.category,
    )

    total_decisions = sum(w.decisions for w in wisdom)

    return GetWisdomResponse(
        wisdom=wisdom,
        total_decisions=total_decisions,
        categories_analyzed=len(wisdom),
    )
