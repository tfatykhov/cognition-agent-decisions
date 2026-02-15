"""F044: Agent Work Discovery service (cstp.ready).

Surfaces prioritized cognitive actions:
- review_outcome: Overdue outcome reviews (review_by date in past)
- stale_pending: Old pending decisions without review_by (>30d)
- calibration_drift: Per-category calibration degradation
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from .drift_service import CheckDriftRequest, check_drift
from .models import ReadyAction, ReadyRequest, ReadyResponse
from .query_service import load_all_decisions

logger = logging.getLogger("cstp.ready")

# Thresholds
STALE_MEDIUM_DAYS = 30
STALE_HIGH_DAYS = 60
DRIFT_HIGH_PCT = 40.0

# Priority ordering for filtering
PRIORITY_ORDER = {"low": 0, "medium": 1, "high": 2}

# Type ordering for tiebreaking (review_outcome first)
TYPE_ORDER = {"review_outcome": 0, "calibration_drift": 1, "stale_pending": 2}


async def get_ready_actions(
    request: ReadyRequest,
    preloaded_decisions: list[dict[str, Any]] | None = None,
) -> ReadyResponse:
    """Get prioritized cognitive actions.

    Args:
        request: Ready request with filters.
        preloaded_decisions: Pre-loaded decisions to avoid redundant disk reads.
            If None, decisions are loaded from disk.

    Returns:
        ReadyResponse with prioritized actions.
    """
    decisions = preloaded_decisions
    if decisions is None:
        decisions = await load_all_decisions()

    actions: list[ReadyAction] = []

    # 1. Review outcome actions
    if not request.action_types or "review_outcome" in request.action_types:
        actions.extend(_detect_review_outcome_actions(decisions))

    # 2. Stale pending actions
    if not request.action_types or "stale_pending" in request.action_types:
        actions.extend(_detect_stale_pending_actions(decisions))

    # 3. Calibration drift actions
    if not request.action_types or "calibration_drift" in request.action_types:
        try:
            drift_actions = await _detect_drift_actions(
                decisions, category_filter=request.category,
            )
            actions.extend(drift_actions)
        except Exception as e:
            logger.warning("Drift detection failed: %s", e)

    # Filter by category (non-drift actions match on their own category)
    if request.category:
        actions = [
            a for a in actions
            if a.category == request.category
        ]

    total = len(actions)

    # Filter by min_priority
    min_level = PRIORITY_ORDER.get(request.min_priority, 0)
    actions = [a for a in actions if PRIORITY_ORDER.get(a.priority, 0) >= min_level]

    filtered = total - len(actions)

    # Sort: high priority first, then type (review before stale), then oldest date
    actions.sort(key=lambda a: (
        -PRIORITY_ORDER.get(a.priority, 0),
        TYPE_ORDER.get(a.type, 9),
        a.date or "9999-99-99",
    ))

    actions = actions[:request.limit]

    return ReadyResponse(actions=actions, total=total, filtered=filtered)


def _detect_review_outcome_actions(
    decisions: list[dict[str, Any]],
) -> list[ReadyAction]:
    """Find pending decisions with overdue review_by dates.

    Priority based on stakes level.
    """
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    actions: list[ReadyAction] = []

    for d in decisions:
        if d.get("status") != "pending":
            continue

        review_by = str(d.get("review_by", "") or "")
        if not review_by or review_by >= today:
            continue

        decision_id = str(d.get("id", ""))[:8]
        title = str(d.get("summary") or d.get("decision") or "Untitled")[:80]
        date = str(d.get("date") or d.get("created_at") or "")[:10]
        stakes = str(d.get("stakes", "medium"))
        category = str(d.get("category", "")) or None

        priority = "high" if stakes in ("critical", "high") else (
            "medium" if stakes == "medium" else "low"
        )

        try:
            review_dt = datetime.fromisoformat(review_by + "T00:00:00+00:00")
            days_overdue = (datetime.now(UTC) - review_dt).days
        except ValueError:
            days_overdue = 0

        actions.append(ReadyAction(
            type="review_outcome",
            priority=priority,
            reason=f"Decision needs outcome review (due {review_by}, {days_overdue}d overdue)",
            suggestion="Use review_outcome to record what happened",
            decision_id=decision_id,
            category=category,
            date=date,
            title=title,
            detail=f"review by {review_by} ({days_overdue}d overdue)",
        ))

    return actions


def _detect_stale_pending_actions(
    decisions: list[dict[str, Any]],
) -> list[ReadyAction]:
    """Find pending decisions older than STALE_MEDIUM_DAYS without review_by.

    Priority based on age (>60d high, >30d medium).
    """
    today_dt = datetime.now(UTC)
    cutoff_medium = (today_dt - timedelta(days=STALE_MEDIUM_DAYS)).strftime("%Y-%m-%d")
    cutoff_high = (today_dt - timedelta(days=STALE_HIGH_DAYS)).strftime("%Y-%m-%d")

    actions: list[ReadyAction] = []

    for d in decisions:
        if d.get("status") != "pending":
            continue

        # Skip if has review_by (handled by review_outcome detector)
        if d.get("review_by"):
            continue

        date = str(d.get("date") or d.get("created_at") or "")[:10]
        if not date or date >= cutoff_medium:
            continue

        decision_id = str(d.get("id", ""))[:8]
        title = str(d.get("summary") or d.get("decision") or "Untitled")[:80]
        category = str(d.get("category", "")) or None

        try:
            dt = datetime.fromisoformat(date + "T00:00:00+00:00")
            days_old = (today_dt - dt).days
        except ValueError:
            days_old = STALE_MEDIUM_DAYS

        priority = "high" if date < cutoff_high else "medium"

        actions.append(ReadyAction(
            type="stale_pending",
            priority=priority,
            reason=f"Decision pending for {days_old} days with no outcome",
            suggestion="Review and record outcome, or mark as abandoned",
            decision_id=decision_id,
            category=category,
            date=date,
            title=title,
            detail=f"pending {days_old} days",
        ))

    return actions


async def _detect_drift_actions(
    decisions: list[dict[str, Any]],
    category_filter: str | None = None,
) -> list[ReadyAction]:
    """Detect per-category calibration drift.

    Delegates to drift_service.check_drift() per category, converts
    DriftAlert objects into ReadyAction items.

    Priority based on drift magnitude (>40% high, else medium).
    """
    # Extract unique categories from reviewed decisions
    categories: set[str] = set()
    for d in decisions:
        if d.get("status") == "reviewed" and d.get("category"):
            categories.add(str(d["category"]))

    if category_filter:
        categories = {category_filter} & categories
        if not categories:
            return []

    actions: list[ReadyAction] = []

    for category in sorted(categories):
        try:
            drift_req = CheckDriftRequest(
                threshold_brier=0.20,
                threshold_accuracy=0.15,
                category=category,
                min_decisions=5,
            )
            drift_resp = await check_drift(drift_req)

            if not drift_resp.drift_detected:
                continue

            for alert in drift_resp.alerts:
                change_pct = abs(alert.change_pct)
                priority = "high" if change_pct >= DRIFT_HIGH_PCT else "medium"

                actions.append(ReadyAction(
                    type="calibration_drift",
                    priority=priority,
                    reason=alert.message,
                    suggestion=(
                        f"Review recent {category} decisions — "
                        f"calibration has degraded from historical baseline"
                    ),
                    category=category,
                ))
        except Exception as e:
            logger.warning("Drift check failed for category %s: %s", category, e)

    return actions
