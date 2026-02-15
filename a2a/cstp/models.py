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


# ============================================================================
# F046: preAction models
# ============================================================================


@dataclass(slots=True)
class PreActionOptions:
    """Options for cstp.preAction."""

    query_limit: int = 5
    auto_record: bool = True
    include_patterns: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PreActionOptions":
        """Create from dict with camelCase support."""
        if not data:
            return cls()
        return cls(
            query_limit=data.get("queryLimit", data.get("query_limit", 5)),
            auto_record=data.get("autoRecord", data.get("auto_record", True)),
            include_patterns=data.get(
                "includePatterns", data.get("include_patterns", True)
            ),
        )


@dataclass(slots=True)
class PreActionRequest:
    """Request for cstp.preAction."""

    action: ActionContext
    options: PreActionOptions = field(default_factory=PreActionOptions)
    reasons: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    pattern: str | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "PreActionRequest":
        """Create from JSON-RPC params."""
        action_data = params.get("action", {})
        if not action_data:
            raise ValueError("Missing required parameter: action")
        return cls(
            action=ActionContext.from_dict(action_data),
            options=PreActionOptions.from_dict(params.get("options")),
            reasons=params.get("reasons", []),
            tags=params.get("tags", []),
            pattern=params.get("pattern"),
        )


@dataclass(slots=True)
class CalibrationContext:
    """Calibration context for a category in pre-action response."""

    brier_score: float | None = None
    accuracy: float | None = None
    calibration_gap: float | None = None
    interpretation: str | None = None
    reviewed_decisions: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        result: dict[str, Any] = {
            "reviewedDecisions": self.reviewed_decisions,
        }
        if self.brier_score is not None:
            result["brierScore"] = self.brier_score
        if self.accuracy is not None:
            result["accuracy"] = self.accuracy
        if self.calibration_gap is not None:
            result["calibrationGap"] = self.calibration_gap
        if self.interpretation:
            result["interpretation"] = self.interpretation
        return result


@dataclass(slots=True)
class PatternSummary:
    """A confirmed pattern from similar decisions."""

    pattern: str
    count: int
    example_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "pattern": self.pattern,
            "count": self.count,
            "exampleIds": self.example_ids,
        }


@dataclass(slots=True)
class PreActionResponse:
    """Response for cstp.preAction."""

    allowed: bool
    decision_id: str | None
    relevant_decisions: list[DecisionSummary]
    guardrail_results: list[GuardrailViolation]
    calibration_context: CalibrationContext
    patterns_summary: list[PatternSummary]
    block_reasons: list[str] = field(default_factory=list)
    query_time_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        result: dict[str, Any] = {
            "allowed": self.allowed,
            "decisionId": self.decision_id,
            "relevantDecisions": [d.to_dict() for d in self.relevant_decisions],
            "guardrailResults": [g.to_dict() for g in self.guardrail_results],
            "calibrationContext": self.calibration_context.to_dict(),
            "patternsSummary": [p.to_dict() for p in self.patterns_summary],
            "queryTimeMs": self.query_time_ms,
        }
        if self.block_reasons:
            result["blockReasons"] = self.block_reasons
        return result


# ============================================================================
# F047: getSessionContext models
# ============================================================================


@dataclass(slots=True)
class SessionContextRequest:
    """Request for cstp.getSessionContext."""

    task_description: str | None = None
    include: list[str] = field(default_factory=lambda: [
        "decisions", "guardrails", "calibration", "ready", "patterns",
    ])
    decisions_limit: int = 10
    ready_limit: int = 5
    format: str = "json"

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "SessionContextRequest":
        """Create from JSON-RPC params."""
        include = params.get("include", [
            "decisions", "guardrails", "calibration", "ready", "patterns",
        ])
        decisions_limit = params.get(
            "decisionsLimit", params.get("decisions_limit", 10)
        )
        decisions_limit = max(1, min(50, decisions_limit))
        ready_limit = params.get("readyLimit", params.get("ready_limit", 5))
        ready_limit = max(1, min(20, ready_limit))
        fmt = params.get("format", "json")
        if fmt not in ("json", "markdown"):
            fmt = "json"
        return cls(
            task_description=params.get(
                "taskDescription", params.get("task_description")
            ),
            include=include,
            decisions_limit=decisions_limit,
            ready_limit=ready_limit,
            format=fmt,
        )


@dataclass(slots=True)
class AgentProfile:
    """Agent cognitive profile for session context."""

    total_decisions: int = 0
    reviewed: int = 0
    overall_accuracy: float | None = None
    brier_score: float | None = None
    tendency: str | None = None
    strongest_category: str | None = None
    weakest_category: str | None = None
    active_since: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        result: dict[str, Any] = {
            "totalDecisions": self.total_decisions,
            "reviewed": self.reviewed,
        }
        if self.overall_accuracy is not None:
            result["overallAccuracy"] = self.overall_accuracy
        if self.brier_score is not None:
            result["brierScore"] = self.brier_score
        if self.tendency:
            result["tendency"] = self.tendency
        if self.strongest_category:
            result["strongestCategory"] = self.strongest_category
        if self.weakest_category:
            result["weakestCategory"] = self.weakest_category
        if self.active_since:
            result["activeSince"] = self.active_since
        return result


@dataclass(slots=True)
class ReadyQueueItem:
    """An item in the ready queue needing attention."""

    id: str
    title: str
    reason: str
    date: str
    detail: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "id": self.id,
            "title": self.title,
            "reason": self.reason,
            "date": self.date,
            "detail": self.detail,
        }


# ============================================================================
# F044: Ready (Agent Work Discovery) models
# ============================================================================


@dataclass(slots=True)
class ReadyRequest:
    """Request for cstp.ready endpoint (F044)."""

    min_priority: str = "low"  # low, medium, high
    action_types: list[str] = field(default_factory=list)  # empty = all types
    limit: int = 20
    category: str | None = None

    @classmethod
    def from_params(cls, params: dict[str, Any]) -> "ReadyRequest":
        """Create from JSON-RPC params (camelCase support)."""
        min_priority = str(params.get("minPriority", params.get("min_priority", "low")))
        if min_priority not in ("low", "medium", "high"):
            min_priority = "low"

        action_types = params.get("actionTypes", params.get("action_types", []))
        if not isinstance(action_types, list):
            action_types = []

        limit = int(params.get("limit", 20))
        limit = max(1, min(limit, 50))

        return cls(
            min_priority=min_priority,
            action_types=action_types,
            limit=limit,
            category=params.get("category"),
        )


@dataclass(slots=True)
class ReadyAction:
    """A prioritized cognitive action from cstp.ready (F044)."""

    type: str  # review_outcome, calibration_drift, stale_pending
    priority: str  # low, medium, high
    reason: str
    suggestion: str
    decision_id: str | None = None
    category: str | None = None
    date: str | None = None
    title: str | None = None
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase keys."""
        result: dict[str, Any] = {
            "type": self.type,
            "priority": self.priority,
            "reason": self.reason,
            "suggestion": self.suggestion,
        }
        if self.decision_id:
            result["decisionId"] = self.decision_id
        if self.category:
            result["category"] = self.category
        if self.date:
            result["date"] = self.date
        if self.title:
            result["title"] = self.title
        if self.detail:
            result["detail"] = self.detail
        return result


@dataclass(slots=True)
class ReadyResponse:
    """Response from cstp.ready endpoint (F044)."""

    actions: list[ReadyAction]
    total: int
    filtered: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        result: dict[str, Any] = {
            "actions": [a.to_dict() for a in self.actions],
            "total": self.total,
            "filtered": self.filtered,
        }
        if self.warnings:
            result["warnings"] = self.warnings
        return result


@dataclass(slots=True)
class ConfirmedPattern:
    """A pattern confirmed across 2+ decisions."""

    pattern: str
    count: int
    categories: list[str] = field(default_factory=list)
    example_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict."""
        return {
            "pattern": self.pattern,
            "count": self.count,
            "categories": self.categories,
            "exampleIds": self.example_ids,
        }


@dataclass(slots=True)
class SessionContextResponse:
    """Response for cstp.getSessionContext."""

    agent_profile: AgentProfile
    relevant_decisions: list[DecisionSummary] = field(default_factory=list)
    active_guardrails: list[dict[str, Any]] = field(default_factory=list)
    calibration_by_category: dict[str, Any] = field(default_factory=dict)
    ready_queue: list[ReadyQueueItem] = field(default_factory=list)
    confirmed_patterns: list[ConfirmedPattern] = field(default_factory=list)
    query_time_ms: int = 0
    markdown: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        if self.markdown is not None:
            return {"markdown": self.markdown, "queryTimeMs": self.query_time_ms}
        return {
            "agentProfile": self.agent_profile.to_dict(),
            "relevantDecisions": [d.to_dict() for d in self.relevant_decisions],
            "activeGuardrails": self.active_guardrails,
            "calibrationByCategory": self.calibration_by_category,
            "readyQueue": [r.to_dict() for r in self.ready_queue],
            "confirmedPatterns": [p.to_dict() for p in self.confirmed_patterns],
            "queryTimeMs": self.query_time_ms,
        }
