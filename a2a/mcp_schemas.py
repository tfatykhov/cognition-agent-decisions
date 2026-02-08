"""Pydantic input schemas for MCP tool definitions.

These models define the JSON Schema that MCP clients see when discovering tools.
They map to the existing CSTP dataclass models but use Pydantic for automatic
schema generation required by the MCP protocol.
"""

from typing import Literal

from pydantic import BaseModel, Field


class QueryFiltersInput(BaseModel):
    """Optional filters for narrowing decision queries."""

    category: str | None = Field(
        default=None,
        description="Filter by category: architecture, process, integration, tooling, security",
    )
    stakes: list[str] | None = Field(
        default=None,
        description="Filter by stakes level: low, medium, high, critical",
    )
    project: str | None = Field(
        default=None,
        description="Filter by project (owner/repo format)",
    )
    has_outcome: bool | None = Field(
        default=None,
        description="Filter to decisions with/without recorded outcomes",
    )


class QueryDecisionsInput(BaseModel):
    """Input for the query_decisions tool."""

    query: str = Field(
        ...,
        min_length=1,
        description="Natural language query to find similar past decisions",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of results to return (1-50)",
    )
    retrieval_mode: Literal["semantic", "keyword", "hybrid"] = Field(
        default="hybrid",
        description="Search mode: semantic (embedding similarity), keyword (BM25), or hybrid (both)",
    )
    filters: QueryFiltersInput | None = Field(
        default=None,
        description="Optional filters to narrow results",
    )


class CheckActionInput(BaseModel):
    """Input for the check_action tool."""

    description: str = Field(
        ...,
        min_length=1,
        description="Description of the action you intend to take",
    )
    category: str | None = Field(
        default=None,
        description="Action category: architecture, process, integration, tooling, security",
    )
    stakes: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Stakes level of the action",
    )
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Your confidence in this action (0.0 to 1.0)",
    )


# ============================================================================
# Phase 2: log_decision, review_outcome, get_stats
# ============================================================================


class ReasonInput(BaseModel):
    """A reason supporting a decision."""

    type: Literal[
        "authority", "analogy", "analysis", "pattern",
        "intuition", "empirical", "elimination", "constraint",
    ] = Field(
        ...,
        description="Type of reasoning: authority, analogy, analysis, pattern, intuition, empirical, elimination, or constraint",
    )
    text: str = Field(
        ...,
        min_length=1,
        description="Explanation of this reason",
    )


class LogDecisionInput(BaseModel):
    """Input for the log_decision tool."""

    decision: str = Field(
        ...,
        min_length=1,
        description="What you decided — state the choice, not the question",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Your confidence in this decision (0.0 to 1.0)",
    )
    category: Literal["architecture", "process", "integration", "tooling", "security"] = Field(
        ...,
        description="Decision category",
    )
    stakes: Literal["low", "medium", "high", "critical"] = Field(
        default="medium",
        description="Stakes level of the decision",
    )
    context: str | None = Field(
        default=None,
        description="Situation context — what led to this decision",
    )
    reasons: list[ReasonInput] | None = Field(
        default=None,
        description="Reasons supporting the decision (aim for 2+ different types)",
    )
    tags: list[str] | None = Field(
        default=None,
        description="Tags for categorization",
    )
    project: str | None = Field(
        default=None,
        description="Project in owner/repo format",
    )
    feature: str | None = Field(
        default=None,
        description="Feature or epic name",
    )
    pr: int | None = Field(
        default=None,
        ge=1,
        description="Pull request number",
    )


class ReviewOutcomeInput(BaseModel):
    """Input for the review_outcome tool."""

    id: str = Field(
        ...,
        min_length=1,
        description="Decision ID to review (8-char hex)",
    )
    outcome: Literal["success", "partial", "failure", "abandoned"] = Field(
        ...,
        description="Outcome of the decision",
    )
    actual_result: str | None = Field(
        default=None,
        description="What actually happened",
    )
    lessons: str | None = Field(
        default=None,
        description="Lessons learned from this decision",
    )
    notes: str | None = Field(
        default=None,
        description="Additional review notes",
    )


class GetStatsInput(BaseModel):
    """Input for the get_stats tool."""

    category: str | None = Field(
        default=None,
        description="Filter stats by category: architecture, process, integration, tooling, security",
    )
    project: str | None = Field(
        default=None,
        description="Filter stats by project (owner/repo format)",
    )
    window: Literal["30d", "60d", "90d", "all"] | None = Field(
        default=None,
        description="Rolling time window for stats calculation",
    )


class GetDecisionInput(BaseModel):
    """Input for the get_decision tool."""

    id: str = Field(
        ...,
        min_length=1,
        description="Decision ID to retrieve (8-char hex, e.g. 'b02d10ba')",
    )


class ReasonStatsFiltersInput(BaseModel):
    """Optional filters for reason-type stats."""

    category: str | None = Field(
        default=None,
        description="Filter by category: architecture, process, integration, tooling, security",
    )
    stakes: str | None = Field(
        default=None,
        description="Filter by stakes level: low, medium, high, critical",
    )
    project: str | None = Field(
        default=None,
        description="Filter by project (owner/repo format)",
    )


class GetReasonStatsInput(BaseModel):
    """Input for the get_reason_stats tool."""

    filters: ReasonStatsFiltersInput | None = Field(
        default=None,
        description="Optional filters to narrow analysis",
    )
    min_reviewed: int = Field(
        default=3,
        ge=1,
        le=50,
        description="Minimum reviewed decisions to include a reason type in stats",
    )
