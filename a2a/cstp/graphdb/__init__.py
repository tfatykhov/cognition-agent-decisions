"""Graph store abstraction layer for CSTP.

Defines the GraphStore ABC and data models that all
graph database backends must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

# Valid edge types for F045 P1
VALID_EDGE_TYPES = frozenset({"relates_to", "supersedes", "depends_on"})


@dataclass(slots=True)
class GraphNode:
    """Decision node in the graph."""

    id: str
    category: str = ""
    stakes: str = ""
    confidence: float | None = None
    outcome: str | None = None
    date: str = ""
    tags: list[str] = field(default_factory=list)
    pattern: str | None = None
    summary: str = ""
    in_degree: int = 0
    out_degree: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase keys."""
        result: dict[str, Any] = {
            "id": self.id,
            "category": self.category,
            "stakes": self.stakes,
            "date": self.date,
            "inDegree": self.in_degree,
            "outDegree": self.out_degree,
        }
        if self.summary:
            result["summary"] = self.summary
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.outcome is not None:
            result["outcome"] = self.outcome
        if self.tags:
            result["tags"] = self.tags
        if self.pattern is not None:
            result["pattern"] = self.pattern
        return result


@dataclass(slots=True)
class GraphEdge:
    """Typed, directed edge between decision nodes."""

    source_id: str
    target_id: str
    edge_type: str
    weight: float = 1.0
    created_at: str | None = None
    created_by: str | None = None
    context: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict with camelCase keys."""
        result: dict[str, Any] = {
            "sourceId": self.source_id,
            "targetId": self.target_id,
            "edgeType": self.edge_type,
            "weight": self.weight,
        }
        if self.created_at is not None:
            result["createdAt"] = self.created_at
        if self.created_by is not None:
            result["createdBy"] = self.created_by
        if self.context is not None:
            result["context"] = self.context
        return result


class GraphStore(ABC):
    """Abstract graph store for decision relationships.

    All graph database backends (NetworkX, in-memory) implement this
    interface. Services interact only through these methods.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the graph and load persisted data.

        Called once at startup. Implementations should load existing
        edges from persistence if available.
        """
        ...

    @abstractmethod
    async def add_node(self, node: GraphNode) -> bool:
        """Add or update a node in the graph.

        Args:
            node: Node to add or update.

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def add_edge(self, edge: GraphEdge) -> bool:
        """Add a typed edge between two nodes.

        Creates source/target nodes if they don't exist.
        Blocks self-loops (source_id == target_id).

        Args:
            edge: Edge to add.

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str | None = None,
    ) -> bool:
        """Remove edge(s) between two nodes.

        Args:
            source_id: Source node ID.
            target_id: Target node ID.
            edge_type: If given, remove only this edge type.
                If None, remove all edges between the nodes.

        Returns:
            True if at least one edge was removed.
        """
        ...

    @abstractmethod
    async def get_node(self, node_id: str) -> GraphNode | None:
        """Get a node by ID.

        Returns:
            GraphNode if found, None otherwise.
        """
        ...

    @abstractmethod
    async def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[GraphEdge]:
        """Get edges matching optional filters.

        All parameters are optional. With no filters, returns all edges.

        Args:
            source_id: Filter by source node.
            target_id: Filter by target node.
            edge_type: Filter by edge type.

        Returns:
            List of matching edges.
        """
        ...

    @abstractmethod
    async def get_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Get subgraph around a node via BFS traversal.

        Args:
            node_id: Center node to start traversal from.
            depth: Maximum number of hops (1-5).
            edge_types: Only traverse these edge types. None = all.
            direction: Traversal direction: "outgoing", "incoming", or "both".

        Returns:
            Tuple of (nodes, edges) in the subgraph.
        """
        ...

    @abstractmethod
    async def get_neighbors(
        self,
        node_id: str,
        direction: str = "both",
        edge_type: str | None = None,
        limit: int = 20,
    ) -> list[tuple[GraphNode, GraphEdge]]:
        """Get immediate neighbors of a node with their connecting edges.

        Lighter-weight than get_subgraph(depth=1) -- returns a flat list
        of (neighbor_node, connecting_edge) pairs.

        Args:
            node_id: Node to find neighbors of.
            direction: "outgoing", "incoming", or "both".
            edge_type: Filter to specific edge type. None = all.
            limit: Maximum neighbors to return (1-100).

        Returns:
            List of (neighbor_node, edge) tuples, sorted by edge weight
            descending. Empty list if node_id not found.
        """
        ...

    @abstractmethod
    async def node_count(self) -> int:
        """Return total number of nodes in the graph."""
        ...

    @abstractmethod
    async def edge_count(self) -> int:
        """Return total number of edges in the graph."""
        ...

    @abstractmethod
    async def reset(self) -> bool:
        """Clear all nodes and edges.

        Returns:
            True if the operation succeeded.
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Clean up resources. Override if the backend holds resources."""
