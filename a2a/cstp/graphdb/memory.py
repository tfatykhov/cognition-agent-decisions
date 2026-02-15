"""In-memory graph store for testing and development.

Provides a GraphStore implementation backed by Python dicts.
No external dependencies required.
"""

from collections import deque

from . import VALID_EDGE_TYPES, GraphEdge, GraphNode, GraphStore


class MemoryGraphStore(GraphStore):
    """In-memory graph store backed by Python dicts.

    Suitable for tests and development without NetworkX.
    """

    def __init__(self) -> None:
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []

    async def initialize(self) -> None:
        pass

    async def add_node(self, node: GraphNode) -> bool:
        self._nodes[node.id] = node
        return True

    async def add_edge(self, edge: GraphEdge) -> bool:
        if edge.source_id == edge.target_id:
            return False
        if edge.edge_type not in VALID_EDGE_TYPES:
            return False

        # Ensure source and target nodes exist (create minimal stubs)
        if edge.source_id not in self._nodes:
            self._nodes[edge.source_id] = GraphNode(id=edge.source_id)
        if edge.target_id not in self._nodes:
            self._nodes[edge.target_id] = GraphNode(id=edge.target_id)

        self._edges.append(edge)
        return True

    async def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str | None = None,
    ) -> bool:
        before = len(self._edges)
        self._edges = [
            e
            for e in self._edges
            if not (
                e.source_id == source_id
                and e.target_id == target_id
                and (edge_type is None or e.edge_type == edge_type)
            )
        ]
        return len(self._edges) < before

    async def get_node(self, node_id: str) -> GraphNode | None:
        node = self._nodes.get(node_id)
        if node is None:
            return None
        # Compute degrees
        in_deg = sum(1 for e in self._edges if e.target_id == node_id)
        out_deg = sum(1 for e in self._edges if e.source_id == node_id)
        node.in_degree = in_deg
        node.out_degree = out_deg
        return node

    async def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[GraphEdge]:
        result: list[GraphEdge] = []
        for e in self._edges:
            if source_id is not None and e.source_id != source_id:
                continue
            if target_id is not None and e.target_id != target_id:
                continue
            if edge_type is not None and e.edge_type != edge_type:
                continue
            result.append(e)
        return result

    async def get_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        if node_id not in self._nodes:
            return ([], [])

        visited_nodes: set[str] = {node_id}
        collected_edges: list[GraphEdge] = []
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            for e in self._edges:
                # Filter by edge type
                if edge_types and e.edge_type not in edge_types:
                    continue

                neighbor: str | None = None
                if direction in ("outgoing", "both") and e.source_id == current:
                    neighbor = e.target_id
                    if e not in collected_edges:
                        collected_edges.append(e)
                if direction in ("incoming", "both") and e.target_id == current:
                    neighbor = e.source_id
                    if e not in collected_edges:
                        collected_edges.append(e)

                if neighbor is not None and neighbor not in visited_nodes:
                    visited_nodes.add(neighbor)
                    queue.append((neighbor, current_depth + 1))

        nodes = []
        for nid in visited_nodes:
            node = await self.get_node(nid)
            if node is not None:
                nodes.append(node)

        return (nodes, collected_edges)

    async def node_count(self) -> int:
        return len(self._nodes)

    async def edge_count(self) -> int:
        return len(self._edges)

    async def reset(self) -> bool:
        self._nodes.clear()
        self._edges.clear()
        return True
