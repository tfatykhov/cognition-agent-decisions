"""Decision store abstraction layer for CSTP.

Defines the DecisionStore ABC and data classes that all
storage backends must implement.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ListQuery:
    """Query parameters for listing decisions with filters and pagination."""

    limit: int = 20
    offset: int = 0
    category: str | None = None
    stakes: str | None = None
    status: str | None = None
    agent: str | None = None
    tags: list[str] = field(default_factory=list)
    project: str | None = None
    feature: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    search: str | None = None
    sort: str = "created_at"
    order: str = "desc"


@dataclass(slots=True)
class ListResult:
    """Paginated result from a list query."""

    decisions: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


@dataclass(slots=True)
class StatsQuery:
    """Query parameters for aggregate statistics."""

    date_from: str | None = None
    date_to: str | None = None
    project: str | None = None


@dataclass(slots=True)
class StatsResult:
    """Aggregated decision statistics."""

    total: int = 0
    by_category: dict[str, int] = field(default_factory=dict)
    by_stakes: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)
    by_agent: dict[str, int] = field(default_factory=dict)
    by_day: list[dict[str, Any]] = field(default_factory=list)
    top_tags: list[dict[str, Any]] = field(default_factory=list)
    recent_activity: dict[str, int] = field(default_factory=dict)


class DecisionStore(ABC):
    """Abstract structured storage for decisions.

    All storage backends (SQLite, YAML-filesystem, in-memory)
    implement this interface. Services interact only through
    these methods.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection, create tables/schema, run migrations.

        Called once at startup or on first use. Implementations should
        create the schema if it does not exist.
        """
        ...

    @abstractmethod
    async def save(self, decision_id: str, data: dict[str, Any]) -> bool:
        """Insert or update a decision.

        Args:
            decision_id: Unique 8-char hex identifier.
            data: Full decision data dictionary including all fields
                  (decision, confidence, category, stakes, reasons, etc.).

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def get(self, decision_id: str) -> dict[str, Any] | None:
        """Get a single decision by ID.

        Args:
            decision_id: The 8-char hex decision identifier.

        Returns:
            Full decision data dictionary, or None if not found.
        """
        ...

    @abstractmethod
    async def delete(self, decision_id: str) -> bool:
        """Delete a decision by ID.

        Args:
            decision_id: The 8-char hex decision identifier.

        Returns:
            True if the decision was deleted, False if not found.
        """
        ...

    @abstractmethod
    async def list(self, query: ListQuery) -> ListResult:
        """List decisions with filters, sort, and pagination.

        Supports filtering by category, stakes, status, agent, tags,
        date range, and keyword search. Results are sorted and paginated.

        Args:
            query: Filter, sort, and pagination parameters.

        Returns:
            Paginated result with decisions and total count.
        """
        ...

    @abstractmethod
    async def stats(self, query: StatsQuery) -> StatsResult:
        """Compute aggregate statistics over decisions.

        Returns counts grouped by category, stakes, status, agent,
        day, and tags, plus recent activity summaries.

        Args:
            query: Optional date range and project filters.

        Returns:
            Aggregated statistics result.
        """
        ...

    @abstractmethod
    async def update_outcome(
        self,
        decision_id: str,
        outcome: str,
        result: str | None = None,
        lessons: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Record review outcome for a decision.

        Args:
            decision_id: The 8-char hex decision identifier.
            outcome: Outcome status (success, failure, partial, abandoned).
            result: Description of what actually happened.
            lessons: Lessons learned from this decision.
            notes: Additional review notes.

        Returns:
            True if the decision was updated, False if not found.
        """
        ...

    @abstractmethod
    async def update_fields(self, decision_id: str, **fields: Any) -> bool:
        """Update specific fields on an existing decision.

        Used for backfilling metadata (tags, pattern, confidence, etc.).

        Args:
            decision_id: The 8-char hex decision identifier.
            **fields: Field names and values to update.

        Returns:
            True if the decision was updated, False if not found.
        """
        ...

    @abstractmethod
    async def count(self, **filters: Any) -> int:
        """Count decisions matching optional filters.

        Args:
            **filters: Optional filter criteria (category, stakes, status, etc.).

        Returns:
            Number of matching decisions.
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Clean up connections. Override if the backend holds resources."""
