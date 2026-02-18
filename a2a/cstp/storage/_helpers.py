"""Shared helpers for in-memory filtering, sorting, and stats computation.

Used by MemoryDecisionStore and YAMLFileSystemStore to avoid duplicating
~200 lines of identical logic. This module is internal to the storage package.
"""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from typing import Any

from . import ListQuery, StatsQuery, StatsResult


def get_date_key(data: dict[str, Any]) -> str:
    """Get a comparable date string from decision data."""
    raw = data.get("created_at") or data.get("date") or ""
    return str(raw)


def _upper_bound(date_to: str) -> str:
    """Compute an upper-bound timestamp from a date_to value.

    If the value already contains a time component (has "T"), return as-is.
    Otherwise append "T23:59:59" to include the full day.
    """
    if "T" in date_to:
        return date_to
    return date_to + "T23:59:59"


def apply_filters(
    decisions: list[dict[str, Any]], query: ListQuery
) -> list[dict[str, Any]]:
    """Apply ListQuery filters to a list of decision dicts."""
    result: list[dict[str, Any]] = []

    for d in decisions:
        if query.category and d.get("category") != query.category:
            continue
        if query.stakes and d.get("stakes") != query.stakes:
            continue
        if query.status and d.get("status") != query.status:
            continue
        if query.agent and d.get("recorded_by") != query.agent:
            continue
        if query.project and d.get("project") != query.project:
            continue

        # Tags: any match
        if query.tags:
            d_tags = d.get("tags") or []
            if not any(t in d_tags for t in query.tags):
                continue

        # Date range
        date_val = get_date_key(d)
        if query.date_from and date_val < query.date_from:
            continue
        if query.date_to and date_val > _upper_bound(query.date_to):
            continue

        # Keyword search: case-insensitive substring across text fields
        if query.search:
            search_lower = query.search.lower()
            searchable = " ".join(
                str(d.get(f) or "")
                for f in ("decision", "summary", "context", "pattern")
            ).lower()
            if search_lower not in searchable:
                continue

        result.append(d)

    return result


def sort_decisions(
    decisions: list[dict[str, Any]], sort_field: str, order: str
) -> list[dict[str, Any]]:
    """Sort decisions by the given field and order."""
    reverse = order.lower() == "desc"

    def sort_key(d: dict[str, Any]) -> str:
        val = d.get(sort_field)
        if val is None:
            # For date fields, use the date/created_at fallback
            if sort_field in ("created_at", "date"):
                val = d.get("created_at") or d.get("date") or ""
            else:
                return ""
        return str(val)

    return sorted(decisions, key=sort_key, reverse=reverse)


def apply_stats_filters(
    decisions: list[dict[str, Any]], query: StatsQuery
) -> list[dict[str, Any]]:
    """Apply StatsQuery filters (date range, project)."""
    result: list[dict[str, Any]] = []

    for d in decisions:
        if query.project and d.get("project") != query.project:
            continue

        date_val = get_date_key(d)
        if query.date_from and date_val < query.date_from:
            continue
        if query.date_to and date_val > _upper_bound(query.date_to):
            continue

        result.append(d)

    return result


def compute_stats(decisions: list[dict[str, Any]]) -> StatsResult:
    """Compute aggregate statistics from a list of decisions."""
    by_category: Counter[str] = Counter()
    by_stakes: Counter[str] = Counter()
    by_status: Counter[str] = Counter()
    by_agent: Counter[str] = Counter()
    by_day: Counter[str] = Counter()
    tag_counter: Counter[str] = Counter()

    now = datetime.now(UTC)

    last_24h = 0
    last_7d = 0
    last_30d = 0

    for d in decisions:
        by_category[d.get("category") or "unknown"] += 1
        by_stakes[d.get("stakes") or "medium"] += 1
        by_status[d.get("status") or "pending"] += 1

        agent = d.get("recorded_by")
        if agent:
            by_agent[agent] += 1

        # Date aggregation
        date_str = get_date_key(d)
        if date_str:
            day = date_str[:10]  # YYYY-MM-DD
            by_day[day] += 1

            # Recent activity
            try:
                dt = datetime.fromisoformat(date_str)
                delta = (now - dt).total_seconds()
                if delta <= 86400:
                    last_24h += 1
                if delta <= 604800:
                    last_7d += 1
                if delta <= 2592000:
                    last_30d += 1
            except (ValueError, TypeError):
                pass

        # Tags
        for tag in d.get("tags") or []:
            tag_counter[tag] += 1

    # Format by_day as list of dicts sorted by date
    by_day_list = sorted(
        [{"date": day, "count": count} for day, count in by_day.items()],
        key=lambda x: x["date"],
    )

    # Top tags (top 20)
    top_tags = [
        {"tag": tag, "count": count}
        for tag, count in tag_counter.most_common(20)
    ]

    return StatsResult(
        total=len(decisions),
        by_category=dict(by_category),
        by_stakes=dict(by_stakes),
        by_status=dict(by_status),
        by_agent=dict(by_agent),
        by_day=by_day_list,
        top_tags=top_tags,
        recent_activity={
            "last24h": last_24h,
            "last7d": last_7d,
            "last30d": last_30d,
        },
    )


def matches_filters(d: dict[str, Any], filters: dict[str, Any]) -> bool:
    """Check if a decision matches keyword filters for count()."""
    for key, value in filters.items():
        if key == "tags":
            d_tags = d.get("tags") or []
            if isinstance(value, list):
                if not any(t in d_tags for t in value):
                    return False
            elif value not in d_tags:
                return False
        elif d.get(key) != value:
            return False
    return True
