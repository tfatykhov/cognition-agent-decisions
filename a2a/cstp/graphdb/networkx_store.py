"""NetworkX-based graph store with JSONL persistence.

Production graph backend using NetworkX MultiDiGraph for
in-process graph operations and JSONL for edge persistence.
"""

import asyncio
import logging
import os
from collections import deque
from pathlib import Path

import networkx as nx

from . import VALID_EDGE_TYPES, GraphEdge, GraphNode, GraphStore
from .persistence import append_edge_to_jsonl, load_edges_from_jsonl, save_edges_to_jsonl

logger = logging.getLogger(__name__)

GRAPH_DATA_PATH = os.getenv("GRAPH_DATA_PATH", "data/graph_edges.jsonl")


class NetworkXGraphStore(GraphStore):
    """NetworkX-backed graph store with JSONL persistence.

    Uses a MultiDiGraph to support multiple typed edges between
    the same node pair. Persists edges to JSONL on every mutation.
    """

    def __init__(self, persistence_path: str | None = None) -> None:
        self._graph: nx.MultiDiGraph = nx.MultiDiGraph()
        self._persistence_path = Path(persistence_path or GRAPH_DATA_PATH)
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Load edges from JSONL if the file exists."""
        if self._persistence_path.exists():
            edges = load_edges_from_jsonl(self._persistence_path)
            for edge in edges:
                self._graph.add_edge(
                    edge.source_id,
                    edge.target_id,
                    key=edge.edge_type,
                    edge_type=edge.edge_type,
                    weight=edge.weight,
                    created_at=edge.created_at,
                    created_by=edge.created_by,
                    context=edge.context,
                )
            logger.info(
                "Loaded %d edges from %s", len(edges), self._persistence_path
            )
        self._initialized = True

    async def add_node(self, node: GraphNode) -> bool:
        self._graph.add_node(
            node.id,
            category=node.category,
            stakes=node.stakes,
            confidence=node.confidence,
            outcome=node.outcome,
            date=node.date,
            tags=list(node.tags),
            pattern=node.pattern,
        )
        return True

    async def add_edge(self, edge: GraphEdge) -> bool:
        if edge.source_id == edge.target_id:
            return False
        if edge.edge_type not in VALID_EDGE_TYPES:
            return False

        async with self._lock:
            self._graph.add_edge(
                edge.source_id,
                edge.target_id,
                key=edge.edge_type,
                edge_type=edge.edge_type,
                weight=edge.weight,
                created_at=edge.created_at,
                created_by=edge.created_by,
                context=edge.context,
            )
            await self._persist_append(edge)
        return True

    async def remove_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str | None = None,
    ) -> bool:
        async with self._lock:
            if not self._graph.has_node(source_id) or not self._graph.has_node(target_id):
                return False

            removed = False
            if edge_type is not None:
                if self._graph.has_edge(source_id, target_id, key=edge_type):
                    self._graph.remove_edge(source_id, target_id, key=edge_type)
                    removed = True
            else:
                # Remove all edges between the two nodes
                while self._graph.has_edge(source_id, target_id):
                    keys = list(self._graph[source_id][target_id].keys())
                    if not keys:
                        break
                    self._graph.remove_edge(source_id, target_id, key=keys[0])
                    removed = True

            if removed:
                await self._persist()
            return removed

    async def get_node(self, node_id: str) -> GraphNode | None:
        if node_id not in self._graph:
            return None
        attrs = self._graph.nodes[node_id]
        return GraphNode(
            id=node_id,
            category=attrs.get("category", ""),
            stakes=attrs.get("stakes", ""),
            confidence=attrs.get("confidence"),
            outcome=attrs.get("outcome"),
            date=attrs.get("date", ""),
            tags=attrs.get("tags", []),
            pattern=attrs.get("pattern"),
            in_degree=self._graph.in_degree(node_id),
            out_degree=self._graph.out_degree(node_id),
        )

    async def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: str | None = None,
    ) -> list[GraphEdge]:
        edges: list[GraphEdge] = []

        for u, v, _key, attrs in self._graph.edges(keys=True, data=True):
            if source_id is not None and u != source_id:
                continue
            if target_id is not None and v != target_id:
                continue
            if edge_type is not None and attrs.get("edge_type") != edge_type:
                continue
            edges.append(self._edge_from_attrs(u, v, attrs))

        return edges

    async def get_subgraph(
        self,
        node_id: str,
        depth: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        if node_id not in self._graph:
            return ([], [])

        visited_nodes: set[str] = {node_id}
        collected_edges: list[GraphEdge] = []
        seen_edge_keys: set[tuple[str, str, str]] = set()
        queue: deque[tuple[str, int]] = deque([(node_id, 0)])

        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue

            # Outgoing edges
            if direction in ("outgoing", "both"):
                for _u, v, _key, attrs in self._graph.out_edges(
                    current, keys=True, data=True
                ):
                    etype = attrs.get("edge_type", "")
                    if edge_types and etype not in edge_types:
                        continue
                    ekey = (current, v, etype)
                    if ekey not in seen_edge_keys:
                        seen_edge_keys.add(ekey)
                        collected_edges.append(
                            self._edge_from_attrs(current, v, attrs)
                        )
                    if v not in visited_nodes:
                        visited_nodes.add(v)
                        queue.append((v, current_depth + 1))

            # Incoming edges
            if direction in ("incoming", "both"):
                for u, _v, _key, attrs in self._graph.in_edges(
                    current, keys=True, data=True
                ):
                    etype = attrs.get("edge_type", "")
                    if edge_types and etype not in edge_types:
                        continue
                    ekey = (u, current, etype)
                    if ekey not in seen_edge_keys:
                        seen_edge_keys.add(ekey)
                        collected_edges.append(
                            self._edge_from_attrs(u, current, attrs)
                        )
                    if u not in visited_nodes:
                        visited_nodes.add(u)
                        queue.append((u, current_depth + 1))

        nodes: list[GraphNode] = []
        for nid in visited_nodes:
            node = await self.get_node(nid)
            if node is not None:
                nodes.append(node)

        return (nodes, collected_edges)

    async def node_count(self) -> int:
        return int(self._graph.number_of_nodes())

    async def edge_count(self) -> int:
        return int(self._graph.number_of_edges())

    async def reset(self) -> bool:
        async with self._lock:
            self._graph.clear()
            if self._persistence_path.exists():
                self._persistence_path.unlink()
        return True

    def _edge_from_attrs(
        self, source: str, target: str, attrs: dict[str, object]
    ) -> GraphEdge:
        """Convert NetworkX edge attributes to a GraphEdge."""
        return GraphEdge(
            source_id=source,
            target_id=target,
            edge_type=str(attrs.get("edge_type", "")),
            weight=float(attrs.get("weight", 1.0)),  # type: ignore[arg-type]
            created_at=attrs.get("created_at"),  # type: ignore[arg-type]
            created_by=attrs.get("created_by"),  # type: ignore[arg-type]
            context=attrs.get("context"),  # type: ignore[arg-type]
        )

    async def _persist(self) -> None:
        """Write all edges to JSONL (full rewrite). Used by remove_edge."""
        edges = await self.get_edges()
        save_edges_to_jsonl(edges, self._persistence_path)

    async def _persist_append(self, edge: GraphEdge) -> None:
        """Append a single edge to JSONL. Used by add_edge."""
        append_edge_to_jsonl(edge, self._persistence_path)
