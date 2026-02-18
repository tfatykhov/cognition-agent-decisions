"""In-memory storage backend for decisions.

Provides a fast, ephemeral store for testing and development.
All data is lost when the process exits.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from . import DecisionStore, ListQuery, ListResult, StatsQuery, StatsResult
from ._helpers import apply_filters, apply_stats_filters, compute_stats, matches_filters, sort_decisions

logger = logging.getLogger(__name__)


class MemoryDecisionStore(DecisionStore):
    """In-memory decision storage for testing and development.

    Stores decisions in a plain dict. Supports all query operations
    via in-memory filtering and aggregation. No persistence.
    """

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize the in-memory data structures."""
        self._data.clear()

    async def close(self) -> None:
        """No-op for in-memory storage."""

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, decision_id: str, data: dict[str, Any]) -> bool:
        """Store a decision in memory."""
        now = datetime.now(UTC).isoformat()
        # Set timestamps if not present; prefer created_at, fallback to date
        if "created_at" not in data:
            data["created_at"] = data.get("date") or now
        data["updated_at"] = now
        data["id"] = decision_id
        self._data[decision_id] = data
        return True

    async def get(self, decision_id: str) -> dict[str, Any] | None:
        """Retrieve a decision from memory."""
        return self._data.get(decision_id)

    async def delete(self, decision_id: str) -> bool:
        """Remove a decision from memory."""
        if decision_id in self._data:
            del self._data[decision_id]
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def list(self, query: ListQuery) -> ListResult:
        """List decisions with in-memory filtering and pagination."""
        all_decisions = list(self._data.values())

        # Apply filters
        filtered = apply_filters(all_decisions, query)

        total = len(filtered)

        # Sort
        filtered = sort_decisions(filtered, query.sort, query.order)

        # Paginate
        page = filtered[query.offset : query.offset + query.limit]

        return ListResult(
            decisions=page,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    async def stats(self, query: StatsQuery) -> StatsResult:
        """Compute statistics over in-memory decisions."""
        all_decisions = list(self._data.values())

        # Apply stats-level filters
        filtered = apply_stats_filters(all_decisions, query)

        return compute_stats(filtered)

    async def update_outcome(
        self,
        decision_id: str,
        outcome: str,
        result: str | None = None,
        lessons: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Update outcome fields on an in-memory decision."""
        data = self._data.get(decision_id)
        if data is None:
            return False

        data["status"] = "reviewed"
        data["outcome"] = outcome
        data["reviewed_at"] = datetime.now(UTC).isoformat()
        if result is not None:
            data["actual_result"] = result
        if lessons is not None:
            data["lessons"] = lessons
        if notes is not None:
            data["review_notes"] = notes
        data["updated_at"] = datetime.now(UTC).isoformat()
        return True

    async def update_fields(self, decision_id: str, **fields: Any) -> bool:
        """Update specific fields on an in-memory decision."""
        data = self._data.get(decision_id)
        if data is None:
            return False

        for key, value in fields.items():
            data[key] = value
        data["updated_at"] = datetime.now(UTC).isoformat()
        return True

    async def count(self, **filters: Any) -> int:
        """Count decisions in memory matching filters."""
        if not filters:
            return len(self._data)

        count = 0
        for d in self._data.values():
            if matches_filters(d, filters):
                count += 1
        return count
