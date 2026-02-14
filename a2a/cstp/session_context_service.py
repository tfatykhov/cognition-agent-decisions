"""F047: Session context service.

Provides full cognitive context for session start: agent profile, relevant
decisions, active guardrails, calibration by category, ready queue, and
confirmed patterns.
"""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

from .calibration_service import calculate_calibration
from .guardrails_service import list_guardrails
from .models import (
    AgentProfile,
    ConfirmedPattern,
    DecisionSummary,
    ReadyQueueItem,
    SessionContextRequest,
    SessionContextResponse,
)
from .query_service import load_all_decisions, query_decisions

logger = logging.getLogger("cstp.session_context")

# Days before a pending decision is considered stale
STALE_DAYS = 30


async def get_session_context(
    request: SessionContextRequest,
    agent_id: str,
) -> SessionContextResponse:
    """Build full session context for an agent.

    Args:
        request: Parsed SessionContextRequest.
        agent_id: Authenticated agent ID.

    Returns:
        SessionContextResponse with all requested sections.
    """
    start_time = time.time()
    include = set(request.include)

    # Load all decisions once (shared data source for profile, ready, patterns)
    all_decisions = await load_all_decisions()

    # --- Agent Profile (always included) ---
    agent_profile = _build_agent_profile(all_decisions)

    # --- Relevant Decisions ---
    relevant_decisions: list[DecisionSummary] = []
    if "decisions" in include and request.task_description:
        try:
            qr = await query_decisions(
                query=request.task_description,
                n_results=request.decisions_limit,
            )
            if not qr.error:
                for r in qr.results:
                    relevant_decisions.append(DecisionSummary(
                        id=r.id,
                        title=r.title,
                        category=r.category,
                        confidence=r.confidence,
                        stakes=r.stakes,
                        status=r.status,
                        outcome=r.outcome,
                        date=r.date,
                        distance=r.distance,
                        tags=r.tags,
                        pattern=r.pattern,
                    ))
        except Exception as e:
            logger.warning("Failed to query decisions for session context: %s", e)

    # --- Active Guardrails ---
    active_guardrails: list[dict[str, Any]] = []
    if "guardrails" in include:
        try:
            active_guardrails = list_guardrails()
        except Exception as e:
            logger.warning("Failed to list guardrails: %s", e)

    # --- Calibration by Category ---
    calibration_by_category: dict[str, Any] = {}
    if "calibration" in include:
        calibration_by_category = _build_calibration_by_category(all_decisions)

    # --- Ready Queue ---
    ready_queue: list[ReadyQueueItem] = []
    if "ready" in include:
        ready_queue = _build_ready_queue(all_decisions, request.ready_limit)

    # --- Confirmed Patterns ---
    confirmed_patterns: list[ConfirmedPattern] = []
    if "patterns" in include:
        confirmed_patterns = _extract_confirmed_patterns(all_decisions)

    query_time_ms = int((time.time() - start_time) * 1000)

    response = SessionContextResponse(
        agent_profile=agent_profile,
        relevant_decisions=relevant_decisions,
        active_guardrails=active_guardrails,
        calibration_by_category=calibration_by_category,
        ready_queue=ready_queue,
        confirmed_patterns=confirmed_patterns,
        query_time_ms=query_time_ms,
    )

    if request.format == "markdown":
        response.markdown = _render_markdown(response, agent_id)

    return response


def _build_agent_profile(decisions: list[dict[str, Any]]) -> AgentProfile:
    """Compute agent profile from decision history."""
    total = len(decisions)
    reviewed = [
        d for d in decisions
        if d.get("status") == "reviewed" and "outcome" in d
    ]

    profile = AgentProfile(total_decisions=total, reviewed=len(reviewed))

    if reviewed:
        # Accuracy: success=1.0, partial=0.5, failure/abandoned=0.0
        outcome_values = []
        for d in reviewed:
            outcome = d.get("outcome", "")
            if outcome == "success":
                outcome_values.append(1.0)
            elif outcome == "partial":
                outcome_values.append(0.5)
            else:
                outcome_values.append(0.0)
        profile.overall_accuracy = round(
            sum(outcome_values) / len(outcome_values), 3
        )

        # Brier score: mean((confidence - actual)^2)
        brier_sum = 0.0
        for d, actual in zip(reviewed, outcome_values, strict=True):
            conf = float(d.get("confidence", 0.5))
            brier_sum += (conf - actual) ** 2
        profile.brier_score = round(brier_sum / len(reviewed), 3)

        # Tendency based on calibration gap
        avg_conf = sum(
            float(d.get("confidence", 0.5)) for d in reviewed
        ) / len(reviewed)
        gap = profile.overall_accuracy - avg_conf
        if abs(gap) < 0.05:
            profile.tendency = "well_calibrated"
        elif gap < -0.10:
            profile.tendency = "overconfident"
        elif gap < 0:
            profile.tendency = "slightly_overconfident"
        elif gap > 0.10:
            profile.tendency = "underconfident"
        else:
            profile.tendency = "slightly_underconfident"

        # Strongest / weakest category (min 3 reviewed decisions)
        cat_stats: dict[str, dict[str, int]] = {}
        for d in reviewed:
            cat = d.get("category", "unknown")
            if cat not in cat_stats:
                cat_stats[cat] = {"success": 0, "total": 0}
            cat_stats[cat]["total"] += 1
            if d.get("outcome") == "success":
                cat_stats[cat]["success"] += 1

        viable = {
            c: s["success"] / s["total"]
            for c, s in cat_stats.items()
            if s["total"] >= 3
        }
        if viable:
            profile.strongest_category = max(viable, key=viable.get)  # type: ignore[arg-type]
            profile.weakest_category = min(viable, key=viable.get)  # type: ignore[arg-type]

    # Active since (earliest decision date)
    if decisions:
        dates = [d.get("date", d.get("created_at", "")) for d in decisions]
        valid_dates = [str(dt)[:10] for dt in dates if dt]
        if valid_dates:
            profile.active_since = min(valid_dates)

    return profile


def _build_ready_queue(
    decisions: list[dict[str, Any]],
    limit: int,
) -> list[ReadyQueueItem]:
    """Find decisions needing attention (overdue reviews, stale pending)."""
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    cutoff = (datetime.now(UTC) - timedelta(days=STALE_DAYS)).strftime("%Y-%m-%d")

    items: list[ReadyQueueItem] = []

    for d in decisions:
        if d.get("status") != "pending":
            continue

        decision_id = str(d.get("id", ""))[:8]
        title = str(d.get("summary") or d.get("decision") or "Untitled")[:80]
        date = str(d.get("date") or d.get("created_at") or "")[:10]

        # Overdue review (has review_by date in the past)
        review_by = str(d.get("review_by", "") or "")
        if review_by and review_by < today:
            items.append(ReadyQueueItem(
                id=decision_id,
                title=title,
                reason="overdue_review",
                date=date,
                detail=f"review by {review_by}",
            ))
            continue

        # Stale pending (older than STALE_DAYS with no outcome)
        if date and date < cutoff:
            try:
                dt = datetime.fromisoformat(date + "T00:00:00+00:00")
                days_old = (datetime.now(UTC) - dt).days
            except ValueError:
                days_old = STALE_DAYS
            items.append(ReadyQueueItem(
                id=decision_id,
                title=title,
                reason="stale_pending",
                date=date,
                detail=f"pending {days_old} days",
            ))

    # Sort: overdue first, then stale by oldest date
    items.sort(key=lambda x: (0 if x.reason == "overdue_review" else 1, x.date))
    return items[:limit]


def _extract_confirmed_patterns(
    decisions: list[dict[str, Any]],
) -> list[ConfirmedPattern]:
    """Extract patterns appearing in 2+ decisions."""
    pattern_data: dict[str, dict[str, Any]] = {}

    for d in decisions:
        pat = d.get("pattern")
        if not pat:
            continue
        if pat not in pattern_data:
            pattern_data[pat] = {"ids": [], "categories": set()}
        pattern_data[pat]["ids"].append(str(d.get("id", ""))[:8])
        cat = d.get("category", "")
        if cat:
            pattern_data[pat]["categories"].add(cat)

    confirmed: list[ConfirmedPattern] = []
    for pat, data in pattern_data.items():
        if len(data["ids"]) >= 2:
            confirmed.append(ConfirmedPattern(
                pattern=pat,
                count=len(data["ids"]),
                categories=sorted(data["categories"]),
                example_ids=data["ids"][:5],
            ))

    confirmed.sort(key=lambda p: p.count, reverse=True)
    return confirmed


def _build_calibration_by_category(
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build calibration stats per category from decisions."""
    reviewed = [
        d for d in decisions
        if d.get("status") == "reviewed" and "outcome" in d
    ]

    by_category: dict[str, list[dict[str, Any]]] = {}
    for d in reviewed:
        cat = d.get("category", "unknown")
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(d)

    result: dict[str, Any] = {}
    for cat, cat_decisions in by_category.items():
        cal = calculate_calibration(cat_decisions)
        if cal:
            result[cat] = cal.to_dict()

    return result


def _render_markdown(
    response: SessionContextResponse,
    agent_id: str,
) -> str:
    """Render session context as markdown for system prompt injection."""
    lines: list[str] = []
    p = response.agent_profile

    # Header
    lines.append(f"## CSTP Decision Context ({agent_id})")
    lines.append("")

    # Profile
    lines.append("### Profile")
    lines.append(
        f"- **Decisions:** {p.total_decisions} total, "
        f"{p.reviewed} reviewed"
    )
    if p.overall_accuracy is not None:
        lines.append(
            f"- **Accuracy:** {p.overall_accuracy:.0%} | "
            f"**Brier:** {p.brier_score} | "
            f"**Tendency:** {p.tendency}"
        )
    if p.strongest_category:
        lines.append(
            f"- **Strongest:** {p.strongest_category} | "
            f"**Weakest:** {p.weakest_category}"
        )
    lines.append("")

    # Guardrails
    if response.active_guardrails:
        lines.append("### Active Guardrails")
        for g in response.active_guardrails:
            action = g.get("action", "warn")
            desc = g.get("description", g.get("id", ""))
            lines.append(f"- [{action}] {desc}")
        lines.append("")

    # Calibration
    if response.calibration_by_category:
        lines.append("### Calibration by Category")
        lines.append("| Category | Accuracy | Brier | Decisions |")
        lines.append("|----------|----------|-------|-----------|")
        for cat, cal in response.calibration_by_category.items():
            acc = cal.get("accuracy", "?")
            brier = cal.get("brierScore", "?")
            count = cal.get("reviewedDecisions", "?")
            lines.append(f"| {cat} | {acc} | {brier} | {count} |")
        lines.append("")

    # Ready queue
    if response.ready_queue:
        lines.append(f"### Pending Actions ({len(response.ready_queue)})")
        for item in response.ready_queue:
            tag = "OVERDUE" if item.reason == "overdue_review" else "STALE"
            lines.append(f"- [{tag}] {item.id}: {item.title} ({item.detail})")
        lines.append("")

    # Confirmed patterns
    if response.confirmed_patterns:
        lines.append("### Confirmed Patterns")
        for pat in response.confirmed_patterns:
            cats = ", ".join(pat.categories)
            lines.append(f"- {pat.pattern} ({pat.count}x, {cats})")
        lines.append("")

    # Relevant decisions
    if response.relevant_decisions:
        lines.append("### Relevant Decisions")
        for d in response.relevant_decisions:
            outcome = d.outcome or "pending"
            lines.append(
                f"- [{d.confidence}] {d.title} "
                f"({d.category}, {outcome})"
            )
        lines.append("")

    # Protocol reminder
    lines.append("### Protocol")
    lines.append("Use `pre_action` tool before any significant decision.")
    lines.append("")

    return "\n".join(lines)
