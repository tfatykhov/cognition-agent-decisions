"""Tests for F045: Graph Store backends (MemoryGraphStore + NetworkXGraphStore)."""

from pathlib import Path
from typing import Any

import pytest

from a2a.cstp.graphdb import GraphEdge, GraphNode, VALID_EDGE_TYPES
from a2a.cstp.graphdb.factory import create_graph_store, get_graph_store, set_graph_store
from a2a.cstp.graphdb.memory import MemoryGraphStore
from a2a.cstp.graphdb.networkx_store import NetworkXGraphStore
from a2a.cstp.graphdb.persistence import load_edges_from_jsonl, save_edges_to_jsonl


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node(nid: str, **kwargs: Any) -> GraphNode:
    """Build a GraphNode with defaults."""
    return GraphNode(
        id=nid,
        category=kwargs.get("category", "architecture"),
        stakes=kwargs.get("stakes", "medium"),
        confidence=kwargs.get("confidence", 0.9),
        outcome=kwargs.get("outcome"),
        date=kwargs.get("date", "2026-02-15"),
        tags=kwargs.get("tags", []),
        pattern=kwargs.get("pattern"),
    )


def _edge(src: str, tgt: str, etype: str = "relates_to", **kwargs: Any) -> GraphEdge:
    """Build a GraphEdge with defaults."""
    return GraphEdge(
        source_id=src,
        target_id=tgt,
        edge_type=etype,
        weight=kwargs.get("weight", 1.0),
        created_at=kwargs.get("created_at", "2026-02-15T00:00:00Z"),
        created_by=kwargs.get("created_by", "test-agent"),
        context=kwargs.get("context"),
    )


# ---------------------------------------------------------------------------
# GraphNode / GraphEdge dataclass tests
# ---------------------------------------------------------------------------


class TestDataModels:
    def test_valid_edge_types(self) -> None:
        assert "relates_to" in VALID_EDGE_TYPES
        assert "supersedes" in VALID_EDGE_TYPES
        assert "depends_on" in VALID_EDGE_TYPES
        assert "contradicts" not in VALID_EDGE_TYPES  # P3

    def test_node_to_dict(self) -> None:
        node = _node("abc", confidence=0.9, outcome="success", tags=["t1"])
        d = node.to_dict()
        assert d["id"] == "abc"
        assert d["category"] == "architecture"
        assert d["confidence"] == 0.9
        assert d["outcome"] == "success"
        assert d["tags"] == ["t1"]
        assert "inDegree" in d
        assert "outDegree" in d

    def test_node_to_dict_omits_none(self) -> None:
        node = _node("abc", confidence=None, outcome=None)
        d = node.to_dict()
        assert "confidence" not in d
        assert "outcome" not in d

    def test_edge_to_dict(self) -> None:
        edge = _edge("a", "b", "depends_on", context="test")
        d = edge.to_dict()
        assert d["sourceId"] == "a"
        assert d["targetId"] == "b"
        assert d["edgeType"] == "depends_on"
        assert d["weight"] == 1.0
        assert d["context"] == "test"


# ---------------------------------------------------------------------------
# JSONL Persistence tests
# ---------------------------------------------------------------------------


class TestJsonlPersistence:
    def test_save_and_load_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "edges.jsonl"
        edges = [
            _edge("a", "b", "relates_to", weight=0.8),
            _edge("b", "c", "depends_on", context="test context"),
            _edge("c", "a", "supersedes"),
        ]
        save_edges_to_jsonl(edges, path)

        loaded = load_edges_from_jsonl(path)
        assert len(loaded) == 3
        assert loaded[0].source_id == "a"
        assert loaded[0].target_id == "b"
        assert loaded[0].edge_type == "relates_to"
        assert loaded[0].weight == 0.8
        assert loaded[1].context == "test context"
        assert loaded[2].edge_type == "supersedes"

    def test_load_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.jsonl"
        path.write_text("")
        loaded = load_edges_from_jsonl(path)
        assert loaded == []

    def test_load_skips_invalid_lines(self, tmp_path: Path) -> None:
        path = tmp_path / "partial.jsonl"
        path.write_text(
            '{"source_id": "a", "target_id": "b", "edge_type": "relates_to"}\n'
            "not json\n"
            '{"source_id": "c", "target_id": "d", "edge_type": "depends_on"}\n'
        )
        loaded = load_edges_from_jsonl(path)
        assert len(loaded) == 2

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "dir" / "edges.jsonl"
        save_edges_to_jsonl([_edge("a", "b")], path)
        assert path.exists()


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestFactory:
    def test_set_and_get(self) -> None:
        store = MemoryGraphStore()
        set_graph_store(store)
        assert get_graph_store() is store
        set_graph_store(None)

    def test_create_memory_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GRAPH_BACKEND", "memory")
        set_graph_store(None)
        store = create_graph_store()
        assert isinstance(store, MemoryGraphStore)
        set_graph_store(None)

    def test_create_networkx_backend(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GRAPH_BACKEND", "networkx")
        set_graph_store(None)
        store = create_graph_store()
        assert isinstance(store, NetworkXGraphStore)
        set_graph_store(None)

    def test_create_unknown_backend_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("GRAPH_BACKEND", "neo4j")
        set_graph_store(None)
        with pytest.raises(ValueError, match="Unknown graph backend"):
            create_graph_store()
        set_graph_store(None)


# ---------------------------------------------------------------------------
# MemoryGraphStore tests
# ---------------------------------------------------------------------------


class TestMemoryGraphStore:
    @pytest.fixture
    def store(self) -> MemoryGraphStore:
        return MemoryGraphStore()

    async def test_add_and_get_node(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        node = _node("abc")
        await store.add_node(node)
        result = await store.get_node("abc")
        assert result is not None
        assert result.id == "abc"
        assert result.category == "architecture"

    async def test_get_nonexistent_node(self, store: MemoryGraphStore) -> None:
        assert await store.get_node("missing") is None

    async def test_add_edge(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_node(_node("a"))
        await store.add_node(_node("b"))
        assert await store.add_edge(_edge("a", "b"))
        assert await store.edge_count() == 1

    async def test_self_loop_blocked(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_node(_node("a"))
        assert not await store.add_edge(_edge("a", "a"))
        assert await store.edge_count() == 0

    async def test_add_edge_creates_stub_nodes(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("x", "y"))
        assert await store.node_count() == 2
        node = await store.get_node("x")
        assert node is not None

    async def test_remove_edge_by_type(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "b", "depends_on"))
        assert await store.edge_count() == 2

        assert await store.remove_edge("a", "b", "relates_to")
        assert await store.edge_count() == 1
        edges = await store.get_edges(source_id="a")
        assert edges[0].edge_type == "depends_on"

    async def test_remove_all_edges_between_nodes(
        self, store: MemoryGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "b", "depends_on"))
        assert await store.remove_edge("a", "b")
        assert await store.edge_count() == 0

    async def test_remove_nonexistent_returns_false(
        self, store: MemoryGraphStore
    ) -> None:
        await store.initialize()
        assert not await store.remove_edge("x", "y")

    async def test_get_edges_filtered(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "c", "depends_on"))
        await store.add_edge(_edge("b", "c", "relates_to"))

        # Filter by source
        edges = await store.get_edges(source_id="a")
        assert len(edges) == 2

        # Filter by target
        edges = await store.get_edges(target_id="c")
        assert len(edges) == 2

        # Filter by type
        edges = await store.get_edges(edge_type="relates_to")
        assert len(edges) == 2

        # Filter by source + type
        edges = await store.get_edges(source_id="a", edge_type="depends_on")
        assert len(edges) == 1

    async def test_get_subgraph_depth_1(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("b", "c"))
        await store.add_edge(_edge("c", "d"))

        nodes, edges = await store.get_subgraph("a", depth=1)
        node_ids = {n.id for n in nodes}
        assert node_ids == {"a", "b"}
        assert len(edges) == 1

    async def test_get_subgraph_depth_2(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("b", "c"))
        await store.add_edge(_edge("c", "d"))

        nodes, edges = await store.get_subgraph("a", depth=2)
        node_ids = {n.id for n in nodes}
        assert node_ids == {"a", "b", "c"}
        assert len(edges) == 2

    async def test_get_subgraph_direction_outgoing(
        self, store: MemoryGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("c", "a"))

        nodes, edges = await store.get_subgraph("a", depth=1, direction="outgoing")
        node_ids = {n.id for n in nodes}
        assert "b" in node_ids
        assert "c" not in node_ids

    async def test_get_subgraph_direction_incoming(
        self, store: MemoryGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("c", "a"))

        nodes, edges = await store.get_subgraph("a", depth=1, direction="incoming")
        node_ids = {n.id for n in nodes}
        assert "c" in node_ids
        assert "b" not in node_ids

    async def test_get_subgraph_edge_type_filter(
        self, store: MemoryGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "c", "depends_on"))

        nodes, edges = await store.get_subgraph(
            "a", depth=1, edge_types=["depends_on"]
        )
        node_ids = {n.id for n in nodes}
        assert "c" in node_ids
        assert "b" not in node_ids

    async def test_get_subgraph_nonexistent_node(
        self, store: MemoryGraphStore
    ) -> None:
        nodes, edges = await store.get_subgraph("missing", depth=1)
        assert nodes == []
        assert edges == []

    async def test_node_degrees(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("a", "c"))
        await store.add_edge(_edge("d", "a"))

        node = await store.get_node("a")
        assert node is not None
        assert node.out_degree == 2
        assert node.in_degree == 1

    async def test_reset(self, store: MemoryGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        assert await store.node_count() > 0
        await store.reset()
        assert await store.node_count() == 0
        assert await store.edge_count() == 0


# ---------------------------------------------------------------------------
# NetworkXGraphStore tests
# ---------------------------------------------------------------------------


class TestNetworkXGraphStore:
    @pytest.fixture
    def store(self, tmp_path: Path) -> NetworkXGraphStore:
        path = str(tmp_path / "graph_edges.jsonl")
        return NetworkXGraphStore(persistence_path=path)

    async def test_add_and_get_node(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_node(_node("abc", tags=["t1"]))
        result = await store.get_node("abc")
        assert result is not None
        assert result.id == "abc"
        assert result.tags == ["t1"]

    async def test_get_nonexistent_node(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        assert await store.get_node("missing") is None

    async def test_add_edge_persists(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        assert await store.edge_count() == 1

        # Verify JSONL was written
        path = store._persistence_path
        assert path.exists()
        loaded = load_edges_from_jsonl(path)
        assert len(loaded) == 1
        assert loaded[0].source_id == "a"

    async def test_self_loop_blocked(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        assert not await store.add_edge(_edge("a", "a"))

    async def test_multiple_edge_types(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "b", "depends_on"))
        assert await store.edge_count() == 2

        edges = await store.get_edges(source_id="a", target_id="b")
        types = {e.edge_type for e in edges}
        assert types == {"relates_to", "depends_on"}

    async def test_remove_edge_by_type(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "b", "depends_on"))

        assert await store.remove_edge("a", "b", "relates_to")
        assert await store.edge_count() == 1
        edges = await store.get_edges()
        assert edges[0].edge_type == "depends_on"

    async def test_remove_all_edges(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "b", "depends_on"))
        assert await store.remove_edge("a", "b")
        assert await store.edge_count() == 0

    async def test_get_subgraph_both(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("b", "c"))
        await store.add_edge(_edge("d", "a"))

        nodes, edges = await store.get_subgraph("a", depth=1, direction="both")
        node_ids = {n.id for n in nodes}
        assert node_ids == {"a", "b", "d"}

    async def test_get_subgraph_outgoing_only(
        self, store: NetworkXGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("c", "a"))

        nodes, edges = await store.get_subgraph("a", depth=1, direction="outgoing")
        node_ids = {n.id for n in nodes}
        assert "b" in node_ids
        assert "c" not in node_ids

    async def test_get_subgraph_incoming_only(
        self, store: NetworkXGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("c", "a"))

        nodes, edges = await store.get_subgraph("a", depth=1, direction="incoming")
        node_ids = {n.id for n in nodes}
        assert "c" in node_ids
        assert "b" not in node_ids

    async def test_get_subgraph_edge_type_filter(
        self, store: NetworkXGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b", "relates_to"))
        await store.add_edge(_edge("a", "c", "depends_on"))

        nodes, edges = await store.get_subgraph(
            "a", depth=1, edge_types=["depends_on"]
        )
        node_ids = {n.id for n in nodes}
        assert "c" in node_ids
        assert "b" not in node_ids

    async def test_persistence_round_trip(self, tmp_path: Path) -> None:
        """Test that a new store instance loads persisted data."""
        path = str(tmp_path / "graph_edges.jsonl")

        # First store: add data
        store1 = NetworkXGraphStore(persistence_path=path)
        await store1.initialize()
        await store1.add_node(_node("a"))
        await store1.add_edge(_edge("a", "b", "depends_on"))
        await store1.add_edge(_edge("b", "c", "relates_to"))
        assert await store1.edge_count() == 2

        # Second store: load from same JSONL
        store2 = NetworkXGraphStore(persistence_path=path)
        await store2.initialize()
        assert await store2.edge_count() == 2

        edges = await store2.get_edges(source_id="a")
        assert len(edges) == 1
        assert edges[0].edge_type == "depends_on"

    async def test_node_degrees(self, store: NetworkXGraphStore) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        await store.add_edge(_edge("a", "c"))
        await store.add_edge(_edge("d", "a"))

        node = await store.get_node("a")
        assert node is not None
        assert node.out_degree == 2
        assert node.in_degree == 1

    async def test_reset_clears_graph_and_file(
        self, store: NetworkXGraphStore
    ) -> None:
        await store.initialize()
        await store.add_edge(_edge("a", "b"))
        assert store._persistence_path.exists()

        await store.reset()
        assert await store.node_count() == 0
        assert await store.edge_count() == 0
        assert not store._persistence_path.exists()

    async def test_get_subgraph_nonexistent_node(
        self, store: NetworkXGraphStore
    ) -> None:
        await store.initialize()
        nodes, edges = await store.get_subgraph("missing", depth=1)
        assert nodes == []
        assert edges == []
