"""YAML filesystem storage backend for decisions.

Legacy backend that wraps the existing YAML-per-decision file storage.
Provides backward compatibility during the migration to SQLite.
"""

from __future__ import annotations

import logging
import os
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from . import DecisionStore, ListQuery, ListResult, StatsQuery, StatsResult

logger = logging.getLogger(__name__)

# Default decisions directory (matches decision_service.py)
DECISIONS_PATH = os.getenv("DECISIONS_PATH", "decisions")


class YAMLFileSystemStore(DecisionStore):
    """YAML filesystem-backed decision storage (legacy).

    Each decision is stored as an individual YAML file in the decisions
    directory tree: ``decisions/YYYY/MM/YYYY-MM-DD-decision-{id}.yaml``.

    Configuration via environment variables:
        - DECISIONS_PATH: Directory for YAML files (default: decisions/)
    """

    def __init__(self, base_path: str | None = None) -> None:
        self._base = Path(base_path or DECISIONS_PATH)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Ensure the decisions directory exists."""
        self._base.mkdir(parents=True, exist_ok=True)

    async def close(self) -> None:
        """No-op for filesystem storage."""

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, decision_id: str, data: dict[str, Any]) -> bool:
        """Write decision data to a YAML file atomically."""
        date_str = _extract_date(data)
        dt = _parse_date(date_str)

        # Build directory: decisions/YYYY/MM/
        year_month_dir = self._base / str(dt.year) / f"{dt.month:02d}"
        year_month_dir.mkdir(parents=True, exist_ok=True)

        # File: YYYY-MM-DD-decision-{id}.yaml
        filename = f"{dt.strftime('%Y-%m-%d')}-decision-{decision_id}.yaml"
        file_path = year_month_dir / filename

        # Atomic write: tempfile in same dir then os.replace
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".yaml", dir=str(year_month_dir))
            try:
                with os.fdopen(fd, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                os.replace(temp_path, file_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception:
            logger.exception("Failed to write decision %s", decision_id)
            return False

        return True

    async def get(self, decision_id: str) -> dict[str, Any] | None:
        """Read a decision from its YAML file."""
        result = self._find_file(decision_id)
        if result is None:
            return None

        file_path, data = result
        # Ensure id is set (extract from filename if missing)
        if "id" not in data:
            data["id"] = decision_id
        return data

    async def delete(self, decision_id: str) -> bool:
        """Delete a decision's YAML file."""
        result = self._find_file(decision_id)
        if result is None:
            return False

        file_path, _ = result
        try:
            file_path.unlink()
            return True
        except OSError:
            logger.exception("Failed to delete %s", file_path)
            return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list(self, query: ListQuery) -> ListResult:
        """List decisions by scanning all YAML files with in-memory filtering."""
        all_decisions = self._load_all()

        # Apply filters
        filtered = _apply_filters(all_decisions, query)

        total = len(filtered)

        # Sort
        filtered = _sort_decisions(filtered, query.sort, query.order)

        # Paginate
        page = filtered[query.offset : query.offset + query.limit]

        return ListResult(
            decisions=page,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def stats(self, query: StatsQuery) -> StatsResult:
        """Compute statistics by scanning all YAML files."""
        all_decisions = self._load_all()

        # Apply stats-level filters
        filtered = _apply_stats_filters(all_decisions, query)

        return _compute_stats(filtered)

    async def update_outcome(
        self,
        decision_id: str,
        outcome: str,
        result: str | None = None,
        lessons: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Update outcome fields in the decision's YAML file."""
        found = self._find_file(decision_id)
        if found is None:
            return False

        file_path, data = found

        data["status"] = "reviewed"
        data["outcome"] = outcome
        data["reviewed_at"] = datetime.now(UTC).isoformat()
        if result is not None:
            data["actual_result"] = result
        if lessons is not None:
            data["lessons"] = lessons
        if notes is not None:
            data["review_notes"] = notes

        return self._write_atomic(file_path, data)

    async def update_fields(self, decision_id: str, **fields: Any) -> bool:
        """Update specific fields in the decision's YAML file."""
        found = self._find_file(decision_id)
        if found is None:
            return False

        file_path, data = found

        for key, value in fields.items():
            data[key] = value

        return self._write_atomic(file_path, data)

    async def count(self, **filters: Any) -> int:
        """Count decisions by scanning YAML files."""
        all_decisions = self._load_all()

        if not filters:
            return len(all_decisions)

        count = 0
        for d in all_decisions:
            if _matches_filters(d, filters):
                count += 1
        return count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_file(self, decision_id: str) -> tuple[Path, dict[str, Any]] | None:
        """Find a decision YAML file by ID."""
        if not self._base.exists():
            return None

        pattern = f"*-decision-{decision_id}.yaml"
        for yaml_file in self._base.rglob(pattern):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if data:
                    return (yaml_file, data)
            except Exception:
                logger.warning("Failed to read %s", yaml_file)
        return None

    def _load_all(self) -> list[dict[str, Any]]:
        """Load all decision YAML files from disk."""
        decisions: list[dict[str, Any]] = []

        if not self._base.exists():
            return decisions

        for yaml_file in self._base.rglob("*-decision-*.yaml"):
            try:
                with open(yaml_file) as f:
                    data = yaml.safe_load(f)
                if not data:
                    continue

                # Extract ID from filename
                filename = yaml_file.stem
                parts = filename.rsplit("-decision-", 1)
                if len(parts) == 2:
                    data["id"] = parts[1]
                else:
                    data["id"] = filename

                decisions.append(data)
            except Exception:
                continue

        return decisions

    def _write_atomic(self, file_path: Path, data: dict[str, Any]) -> bool:
        """Atomic write: tempfile in same directory then os.replace."""
        try:
            fd, temp_path = tempfile.mkstemp(
                suffix=".yaml", dir=str(file_path.parent)
            )
            try:
                with os.fdopen(fd, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)
                os.replace(temp_path, file_path)
            except Exception:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise
        except Exception:
            logger.exception("Atomic write failed for %s", file_path)
            return False
        return True


# ======================================================================
# Module-level helpers (filtering, sorting, stats)
# ======================================================================


def _extract_date(data: dict[str, Any]) -> str:
    """Extract a date string from decision data."""
    return str(data.get("date") or data.get("created_at") or "")


def _parse_date(date_str: str) -> datetime:
    """Parse a date string, falling back to now."""
    if date_str:
        try:
            return datetime.fromisoformat(date_str)
        except (ValueError, TypeError):
            pass
    return datetime.now(UTC)


def _get_date_key(data: dict[str, Any]) -> str:
    """Get a comparable date string from decision data."""
    raw = data.get("created_at") or data.get("date") or ""
    return str(raw)


def _apply_filters(
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
        date_val = _get_date_key(d)
        if query.date_from and date_val < query.date_from:
            continue
        if query.date_to and date_val > query.date_to + "T23:59:59":
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


def _sort_decisions(
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


def _apply_stats_filters(
    decisions: list[dict[str, Any]], query: StatsQuery
) -> list[dict[str, Any]]:
    """Apply StatsQuery filters (date range, project)."""
    result: list[dict[str, Any]] = []

    for d in decisions:
        if query.project and d.get("project") != query.project:
            continue

        date_val = _get_date_key(d)
        if query.date_from and date_val < query.date_from:
            continue
        if query.date_to and date_val > query.date_to + "T23:59:59":
            continue

        result.append(d)

    return result


def _compute_stats(decisions: list[dict[str, Any]]) -> StatsResult:
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
        date_str = _get_date_key(d)
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


def _matches_filters(d: dict[str, Any], filters: dict[str, Any]) -> bool:
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
