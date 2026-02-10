"""CSTP request/response models for JSON-RPC methods."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class QueryFilters:
    """Filters for cstp.queryDecisions."""

    category: str | None = None
    min_confidence: float = 0.0
    max_confidence: float = 1.0
    date_after: datetime | None = None
    date_before: datetime | None = None
    stakes: list[str] | None = None
    status: list[str] | None = None
    # F010: Project context filters
    project: str | None = None
    feature: str | None = None
    pr: int | None = None
    has_outcome: bool | None = None
    # F027: Tag filter
    tags: list[str] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "QueryFilters":
        """Create QueryFilters from dict."""
        if not data:
            return cls()
        return cls(
            category=data.get("category"),
            min_confidence=data.get("minConfidence", 0.0),
            max_confidence=data.get("maxConfidence", 1.0),
            date_after=_parse_datetime(data.get("dateAfter")),
            date_before=_parse_datetime(data.get("dateBefore")),
            stakes=data.get("stakes"),
            status=data.get("status"),
            # F010: Project context filters
            project=data.get("project"),
            feature=data.get("feature"),
            pr=data.get("pr"),
            has_outcome=data.get("hasOutcome"),
            # F027: Tag filter
            tags=data.get("tags"),
        )


@dataclass(slots=True)
class QueryDecisionsRequest:
    """Request for cstp.queryDecisions."""

    query: str
    filters: QueryFilters = field(default_factory=QueryFilters)
    limit: int = 10
    include_reasons: bool = False
    # F017: Hybrid retrieval
    retrieval_mode: str = "semantic"  # semantic | keyword | hybrid
    hybrid_weight: float = 0.7  # semantic weight (keyword = 1 - this)
    # F024: Bridge-side search
    bridge_side: str | None = None  # structure | function | None (both)

    @property
    def effective_query(self) -> str:
        """Query text with bridge-side prefix for directional search.

        Prepends 'Structure: ' or 'Function: ' to bias semantic search
        toward the matching side of bridge-definitions.
        Use for semantic search only - keyword search should use raw query.
        """
        if self.bridge_side and self.query.strip():
            if self.bridge_side == "structure":
                return f"Structure: {self.query}"
            if self.bridge_side == "function":
                return f"Function: {self.query}"
        return self.query

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "QueryDecisionsRequest":
        """Create request from JSON-RPC params."""
        query = params.get("query", "")
        # Allow empty query for listing all decisions

        limit = params.get("limit", params.get("top_k", 10))
        # Higher limit allowed for empty queries (list-all mode)
        max_limit = 500 if not query.strip() else 50
        if not 1 <= limit <= max_limit:
            limit = max(1, min(max_limit, limit))

        # F017: Parse retrieval mode
        retrieval_mode = params.get("retrievalMode", params.get("retrieval_mode", "semantic"))
        if retrieval_mode not in ("semantic", "keyword", "hybrid"):
            retrieval_mode = "semantic"

        hybrid_weight = float(params.get("hybridWeight", params.get("hybrid_weight", 0.7)))
        hybrid_weight = max(0.0, min(1.0, hybrid_weight))

        # F024: Parse bridge_side
        bridge_side = params.get("bridgeSide", params.get("bridge_side"))
        if bridge_side and bridge_side not in ("structure", "function"):
            bridge_side = None

        return cls(
            query=query,
            filters=QueryFilters.from_dict(params.get("filters")),
            limit=limit,
            include_reasons=params.get("includeReasons", False),
            retrieval_mode=retrieval_mode,
            hybrid_weight=hybrid_weight,
            bridge_side=bridge_side,
        )


@dataclass(slots=True)
class DecisionSummary:
    """Summary of a decision in query results."""

    id: str
    title: str
    category: str
    confidence: float | None
    stakes: str | None
    status: str
    outcome: str | None
    date: str
    distance: float
    reasons: list[str] | None = None
    # F027: Tags and pattern in results
    tags: list[str] | None = None
    pattern: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "confidence": self.confidence,
            "stakes": self.stakes,
            "status": self.status,
            "date": self.date,
            "distance": self.distance,
        }
        if self.outcome:
            result["outcome"] = self.outcome
        if self.reasons:
            result["reasons"] = self.reasons
        if self.tags:
            result["tags"] = self.tags
        if self.pattern:
            result["pattern"] = self.pattern
        return result


@dataclass(slots=True)
class QueryDecisionsResponse:
    """Response for cstp.queryDecisions."""

    decisions: list[DecisionSummary]
    total: int
    query: str
    query_time_ms: int
    agent: str
    # F017: Hybrid retrieval metadata
    retrieval_mode: str = "semantic"
    scores: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        result = {
            "decisions": [d.to_dict() for d in self.decisions],
            "total": self.total,
            "query": self.query,
            "queryTimeMs": self.query_time_ms,
            "agent": self.agent,
            "retrievalMode": self.retrieval_mode,
        }
        if self.scores:
            result["scores"] = self.scores
        return result


# ============================================================================
# F003: checkGuardrails models
# ============================================================================


@dataclass(slots=True)
class ActionContext:
    """Action context for guardrail evaluation."""

    description: str
    category: str | None = None
    stakes: str = "medium"
    confidence: float | None = None
    context: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ActionContext":
        """Create ActionContext from dict."""
        description = data.get("description", "")
        if not description:
            raise ValueError("Missing required field: action.description")

        return cls(
            description=description,
            category=data.get("category"),
            stakes=data.get("stakes", "medium"),
            confidence=data.get("confidence"),
            context=data.get("context", {}),
        )


@dataclass(slots=True)
class AgentInfo:
    """Information about the requesting agent."""

    id: str | None = None
    url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AgentInfo":
        """Create AgentInfo from dict."""
        if not data:
            return cls()
        return cls(
            id=data.get("id"),
            url=data.get("url"),
        )


@dataclass(slots=True)
class CheckGuardrailsRequest:
    """Request for cstp.checkGuardrails."""

    action: ActionContext
    agent: AgentInfo = field(default_factory=AgentInfo)

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "CheckGuardrailsRequest":
        """Create request from JSON-RPC params."""
        action_data = params.get("action", {})
        if not action_data:
            raise ValueError("Missing required parameter: action")

        return cls(
            action=ActionContext.from_dict(action_data),
            agent=AgentInfo.from_dict(params.get("agent")),
        )


@dataclass(slots=True)
class GuardrailViolation:
    """A guardrail violation or warning."""

    guardrail_id: str
    name: str
    message: str
    severity: str = "block"
    suggestion: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        result: dict[str, Any] = {
            "guardrailId": self.guardrail_id,
            "name": self.name,
            "message": self.message,
            "severity": self.severity,
        }
        if self.suggestion:
            result["suggestion"] = self.suggestion
        return result


@dataclass(slots=True)
class CheckGuardrailsResponse:
    """Response for cstp.checkGuardrails."""

    allowed: bool
    violations: list[GuardrailViolation]
    warnings: list[GuardrailViolation]
    evaluated: int
    evaluated_at: datetime
    agent: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        return {
            "allowed": self.allowed,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [w.to_dict() for w in self.warnings],
            "evaluated": self.evaluated,
            "evaluatedAt": self.evaluated_at.isoformat(),
            "agent": self.agent,
        }


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse ISO datetime string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
