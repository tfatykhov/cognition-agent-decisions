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
