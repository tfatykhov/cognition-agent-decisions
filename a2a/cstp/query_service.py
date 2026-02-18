"""Query service for semantic decision search.

Uses VectorStore and EmbeddingProvider abstractions for backend-agnostic
querying. The where-clause building and result parsing remain here.
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .embeddings.factory import get_embedding_provider
from .vectordb.factory import get_vector_store

logger = logging.getLogger(__name__)

# Configuration (only decisions path remains — vector/embedding config moved to backends)
DECISIONS_PATH = os.getenv("DECISIONS_PATH", "decisions")


@dataclass(slots=True)
class QueryResult:
    """Single query result from vector search."""

    id: str
    title: str
    category: str
    confidence: float | None
    stakes: str | None
    status: str
    outcome: str | None
    date: str
    distance: float
    reason_types: list[str] | None = None
    # F027: Tags and pattern
    tags: list[str] | None = None
    pattern: str | None = None
    # F163: Enrichment fields for pre_action consumers
    lessons: str | None = None
    actual_result: str | None = None
    reasons: list[dict[str, str]] | None = None
    # F169: Bridge (structure/function) in search results
    bridge: dict[str, str] | None = None


@dataclass(slots=True)
class QueryResponse:
    """Response from query operation."""

    results: list[QueryResult]
    query: str
    query_time_ms: int
    error: str | None = None


async def query_decisions(
    query: str,
    n_results: int = 10,
    category: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    stakes: list[str] | None = None,
    status_filter: list[str] | None = None,
    # F010: Project context filters
    project: str | None = None,
    feature: str | None = None,
    pr: int | None = None,
    has_outcome: bool | None = None,
    # F027: Tag filter
    tags: list[str] | None = None,
) -> QueryResponse:
    """Query similar decisions using vector similarity search.

    Args:
        query: Search query text.
        n_results: Maximum results to return.
        category: Filter by category.
        min_confidence: Minimum confidence threshold.
        max_confidence: Maximum confidence threshold.
        stakes: Filter by stakes levels.
        status_filter: Filter by status values.
        project: Filter by project (owner/repo).
        feature: Filter by feature name.
        pr: Filter by PR number.
        has_outcome: Filter to only reviewed decisions (True) or pending (False).
        tags: Filter by tag values.

    Returns:
        QueryResponse with results or error.
    """
    start_time = time.time()

    store = get_vector_store()
    provider = get_embedding_provider()

    # Check collection exists
    coll_id = await store.get_collection_id()
    if not coll_id:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=0,
            error="Collection not found. Index decisions first.",
        )

    # Generate embedding
    try:
        embedding = await provider.embed(query)
    except Exception as e:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=int((time.time() - start_time) * 1000),
            error=f"Embedding generation failed: {e}",
        )

    # Build where clause
    where: dict[str, Any] = {}
    if category:
        where["category"] = category
    if min_confidence is not None:
        where["confidence"] = {"$gte": min_confidence}
    if stakes:
        # Ensure stakes is a list for $in operator
        stakes_list = [stakes] if isinstance(stakes, str) else stakes
        where["stakes"] = {"$in": stakes_list}
    if status_filter:
        # Ensure status is a list for $in operator
        status_list = [status_filter] if isinstance(status_filter, str) else status_filter
        where["status"] = {"$in": status_list}

    # F010: Project context filters
    if project:
        where["project"] = project
    if feature:
        where["feature"] = feature
    if pr is not None:
        where["pr"] = pr
    # F027: Tag filter (tags stored as comma-separated string)
    if tags:
        if len(tags) == 1:
            where["tags"] = {"$contains": tags[0]}
        else:
            # Match any tag - OR across tags using $contains on each
            where["$or"] = [{"tags": {"$contains": t}} for t in tags]
    if has_outcome is True:
        where["status"] = "reviewed"
    elif has_outcome is False:
        where["status"] = "pending"

    # Query via VectorStore
    vector_results = await store.query(
        embedding=embedding,
        n_results=n_results,
        where=where if where else None,
    )

    # Parse VectorResult into QueryResult
    results: list[QueryResult] = []
    for vr in vector_results:
        meta = vr.metadata

        # Parse reason types if present
        reason_types = None
        if meta.get("reason_types"):
            reason_types = meta["reason_types"].split(",")

        # F027: Parse tags from comma-separated metadata
        result_tags = None
        if meta.get("tags"):
            result_tags = meta["tags"].split(",")

        # F163: Parse full reasons from JSON metadata
        reasons_list: list[dict[str, str]] | None = None
        if meta.get("reasons_json"):
            try:
                reasons_list = json.loads(meta["reasons_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        # F169: Parse bridge from JSON metadata
        bridge_dict: dict[str, str] | None = None
        if meta.get("bridge_json"):
            try:
                bridge_dict = json.loads(meta["bridge_json"])
            except (json.JSONDecodeError, TypeError):
                pass

        results.append(
            QueryResult(
                id=vr.id[:8] if len(vr.id) > 8 else vr.id,
                title=meta.get("title", "Untitled"),
                category=meta.get("category", ""),
                confidence=meta.get("confidence"),
                stakes=meta.get("stakes"),
                status=meta.get("status", ""),
                outcome=meta.get("outcome"),
                date=meta.get("date", ""),
                distance=round(vr.distance, 4) if vr.distance else 0.0,
                reason_types=reason_types,
                tags=result_tags,
                pattern=meta.get("pattern"),
                lessons=meta.get("lessons"),
                actual_result=meta.get("actual_result"),
                reasons=reasons_list,
                bridge=bridge_dict,
            )
        )

    return QueryResponse(
        results=results,
        query=query,
        query_time_ms=int((time.time() - start_time) * 1000),
    )


async def load_all_decisions(
    decisions_path: str | None = None,
    category: str | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """Load all decisions, preferring DecisionStore over YAML rglob.

    Tries DecisionStore.list() first for efficient querying.
    Falls back to YAML rglob if store is unavailable or raises.

    Args:
        decisions_path: Override for decisions directory.
        category: Optional category filter.
        project: Optional project filter.

    Returns:
        List of decision dictionaries with id and content.
    """
    # F050: Try DecisionStore first
    try:
        from .storage import ListQuery
        from .storage.factory import get_decision_store

        store = get_decision_store()
        query = ListQuery(
            limit=10_000,
            offset=0,
            category=category,
            project=project,
            sort="created_at",
            order="desc",
        )
        result = await store.list(query)
        return result.decisions
    except Exception:
        logger.debug("Store list() failed, falling back to YAML", exc_info=True)

    base = Path(decisions_path or DECISIONS_PATH)
    decisions: list[dict[str, Any]] = []

    if not base.exists():
        return decisions

    for yaml_file in base.rglob("*-decision-*.yaml"):
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

            # Apply filters
            if category and data.get("category") != category:
                continue
            if project and data.get("project") != project:
                continue

            decisions.append(data)

        except Exception:
            continue

    return decisions
