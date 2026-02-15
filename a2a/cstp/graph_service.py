"""Graph service for decision relationships (F045 P1).

Provides business logic for linking decisions, querying subgraphs,
and initializing the graph from existing decision YAML data.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .graphdb import GraphEdge, GraphNode
from .graphdb.factory import get_graph_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response dataclasses
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class LinkDecisionsResponse:
    """Response from cstp.linkDecisions."""

    success: bool
    edge: GraphEdge | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase keys."""
        result: dict[str, Any] = {"success": self.success}
        if self.edge is not None:
            result["edge"] = self.edge.to_dict()
        if self.error is not None:
            result["error"] = self.error
        return result


@dataclass(slots=True)
class GetGraphResponse:
    """Response from cstp.getGraph."""

    center_id: str
    depth: int
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase keys."""
        result: dict[str, Any] = {
            "centerId": self.center_id,
            "depth": self.depth,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
        }
        if self.error is not None:
            result["error"] = self.error
        return result


# ---------------------------------------------------------------------------
# Service functions
# ---------------------------------------------------------------------------


async def link_decisions(
    source_id: str,
    target_id: str,
    edge_type: str,
    weight: float,
    context: str | None,
    agent_id: str,
) -> LinkDecisionsResponse:
    """Create a typed edge between two decisions.

    Args:
        source_id: Source decision ID.
        target_id: Target decision ID.
        edge_type: One of: relates_to, supersedes, depends_on.
        weight: Edge weight (positive float).
        context: Optional context string.
        agent_id: Authenticated agent ID.

    Returns:
        LinkDecisionsResponse with the created edge or error.
    """
    store = get_graph_store()

    edge = GraphEdge(
        source_id=source_id,
        target_id=target_id,
        edge_type=edge_type,
        weight=weight,
        created_at=datetime.now(UTC).isoformat(),
        created_by=agent_id,
        context=context,
    )

    success = await store.add_edge(edge)
    if not success:
        return LinkDecisionsResponse(success=False, error="Failed to add edge")

    logger.info(
        "Linked %s -[%s]-> %s (weight=%.2f, agent=%s)",
        source_id,
        edge_type,
        target_id,
        weight,
        agent_id,
    )
    return LinkDecisionsResponse(success=True, edge=edge)


async def get_graph(
    node_id: str,
    depth: int,
    edge_types: list[str] | None,
    direction: str,
) -> GetGraphResponse:
    """Get subgraph around a decision node.

    Args:
        node_id: Center node ID.
        depth: Max traversal hops (1-5).
        edge_types: Optional edge type filter.
        direction: Traversal direction: outgoing, incoming, or both.

    Returns:
        GetGraphResponse with nodes and edges.
    """
    store = get_graph_store()

    nodes, edges = await store.get_subgraph(
        node_id=node_id,
        depth=depth,
        edge_types=edge_types,
        direction=direction,
    )

    if not nodes:
        return GetGraphResponse(
            center_id=node_id,
            depth=depth,
            error=f"Node not found: {node_id}",
        )

    return GetGraphResponse(
        center_id=node_id,
        depth=depth,
        nodes=nodes,
        edges=edges,
    )


async def initialize_graph_from_decisions(
    decisions: list[dict[str, Any]] | None = None,
) -> int:
    """Load existing decisions and their related_to edges into the graph.

    Called at server startup to populate the graph from YAML data.
    If ``decisions`` is provided, uses those instead of loading from disk.

    Args:
        decisions: Pre-loaded decision dicts (for testing). If None,
            loads from disk via ``load_all_decisions()``.

    Returns:
        Number of edges loaded.
    """
    store = get_graph_store()

    if decisions is None:
        from .query_service import load_all_decisions

        decisions = await load_all_decisions()

    edges_loaded = 0

    for decision in decisions:
        decision_id = str(decision.get("id", ""))[:8]
        if not decision_id:
            continue

        # Add node
        node = GraphNode(
            id=decision_id,
            category=str(decision.get("category", "")),
            stakes=str(decision.get("stakes", "medium")),
            confidence=decision.get("confidence"),
            outcome=decision.get("outcome"),
            date=str(decision.get("created_at", ""))[:10],
            tags=decision.get("tags") or [],
            pattern=decision.get("pattern"),
        )
        await store.add_node(node)

        # Add relates_to edges from YAML
        related_to = decision.get("related_to") or []
        for related in related_to:
            related_id = str(related.get("id", ""))
            if not related_id:
                continue

            distance = float(related.get("distance", 0.5))
            edge = GraphEdge(
                source_id=decision_id,
                target_id=related_id,
                edge_type="relates_to",
                weight=round(max(0.01, 1.0 - distance), 3),
                created_at=str(decision.get("created_at", "")),
                created_by="system",
                context="auto-imported from related_to",
            )
            success = await store.add_edge(edge)
            if success:
                edges_loaded += 1

    logger.info(
        "Graph initialized: %d nodes, %d edges loaded from decisions",
        await store.node_count(),
        edges_loaded,
    )
    return edges_loaded
