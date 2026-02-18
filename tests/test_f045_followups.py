"""Tests for F045 follow-up features: getNeighbors, auto-linking, MCP graph tools."""

import json
import sys
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.graph_service import (
    auto_link_decision,
    get_neighbors,
    link_decisions,
)
from a2a.cstp.graphdb import GraphEdge, GraphNode
from a2a.cstp.graphdb.factory import set_graph_store
from a2a.cstp.graphdb.memory import MemoryGraphStore
from a2a.cstp.models import GetNeighborsRequest
from a2a.models.jsonrpc import JsonRpcRequest


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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_store() -> MemoryGraphStore:
    store = MemoryGraphStore()
    set_graph_store(store)
    yield store  # type: ignore[misc]
    set_graph_store(None)


@pytest.fixture
def dispatcher() -> CstpDispatcher:
    d = CstpDispatcher()
    register_methods(d)
    return d


# ===========================================================================
# A. cstp.getNeighbors tests
# ===========================================================================


class TestGetNeighborsStore:
    """Tests for MemoryGraphStore.get_neighbors method."""

    async def test_basic_both_directions(self, memory_store: MemoryGraphStore) -> None:
        """Node with outgoing and incoming edges returns both neighbors."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to"))
        await memory_store.add_edge(_edge("c", "a", "depends_on"))

        pairs = await memory_store.get_neighbors("a", direction="both")
        neighbor_ids = {p[0].id for p in pairs}
        assert neighbor_ids == {"b", "c"}
        assert len(pairs) == 2

    async def test_direction_outgoing(self, memory_store: MemoryGraphStore) -> None:
        """Only returns outgoing neighbors."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to"))
        await memory_store.add_edge(_edge("c", "a", "depends_on"))

        pairs = await memory_store.get_neighbors("a", direction="outgoing")
        neighbor_ids = {p[0].id for p in pairs}
        assert "b" in neighbor_ids
        assert "c" not in neighbor_ids

    async def test_direction_incoming(self, memory_store: MemoryGraphStore) -> None:
        """Only returns incoming neighbors."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to"))
        await memory_store.add_edge(_edge("c", "a", "depends_on"))

        pairs = await memory_store.get_neighbors("a", direction="incoming")
        neighbor_ids = {p[0].id for p in pairs}
        assert "c" in neighbor_ids
        assert "b" not in neighbor_ids

    async def test_edge_type_filter(self, memory_store: MemoryGraphStore) -> None:
        """Filters by edge_type."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to"))
        await memory_store.add_edge(_edge("a", "c", "depends_on"))

        pairs = await memory_store.get_neighbors("a", edge_type="depends_on")
        assert len(pairs) == 1
        assert pairs[0][0].id == "c"
        assert pairs[0][1].edge_type == "depends_on"

    async def test_limit_parameter(self, memory_store: MemoryGraphStore) -> None:
        """Respects limit parameter."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to", weight=0.9))
        await memory_store.add_edge(_edge("a", "c", "relates_to", weight=0.8))
        await memory_store.add_edge(_edge("a", "d", "relates_to", weight=0.7))

        pairs = await memory_store.get_neighbors("a", limit=2)
        assert len(pairs) == 2

    async def test_sorted_by_weight_desc(self, memory_store: MemoryGraphStore) -> None:
        """Returns neighbors sorted by weight descending."""
        await memory_store.add_node(_node("a"))
        await memory_store.add_edge(_edge("a", "b", "relates_to", weight=0.3))
        await memory_store.add_edge(_edge("a", "c", "relates_to", weight=0.9))
        await memory_store.add_edge(_edge("a", "d", "relates_to", weight=0.6))

        pairs = await memory_store.get_neighbors("a")
        weights = [p[1].weight for p in pairs]
        assert weights == sorted(weights, reverse=True)
        assert pairs[0][0].id == "c"  # highest weight

    async def test_nonexistent_node(self, memory_store: MemoryGraphStore) -> None:
        """Returns empty list for missing node."""
        pairs = await memory_store.get_neighbors("missing")
        assert pairs == []

    async def test_no_neighbors(self, memory_store: MemoryGraphStore) -> None:
        """Node with no edges returns empty list."""
        await memory_store.add_node(_node("a"))
        pairs = await memory_store.get_neighbors("a")
        assert pairs == []


class TestGetNeighborsService:
    """Tests for get_neighbors service function."""

    async def test_basic_response(self, memory_store: MemoryGraphStore) -> None:
        """Service returns properly formatted response."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "depends_on", 0.8, None, "agent")

        response = await get_neighbors("a", direction="both", edge_type=None, limit=20)
        assert response.node_id == "a"
        assert response.total == 2
        assert response.error is None
        assert len(response.neighbors) == 2
        # Each neighbor is a dict with "node" and "edge" keys
        assert "node" in response.neighbors[0]
        assert "edge" in response.neighbors[0]

    async def test_nonexistent_node_error(self, memory_store: MemoryGraphStore) -> None:
        """Returns error for nonexistent node."""
        response = await get_neighbors("missing", direction="both", edge_type=None, limit=20)
        assert response.error is not None
        assert "not found" in response.error
        assert response.total == 0

    async def test_node_exists_no_neighbors(self, memory_store: MemoryGraphStore) -> None:
        """Existing node with no edges returns empty list, no error."""
        await memory_store.add_node(_node("alone"))
        response = await get_neighbors("alone", direction="both", edge_type=None, limit=20)
        assert response.error is None
        assert response.total == 0
        assert response.neighbors == []

    async def test_response_to_dict(self, memory_store: MemoryGraphStore) -> None:
        """to_dict produces camelCase keys."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        response = await get_neighbors("a", direction="both", edge_type=None, limit=20)
        d = response.to_dict()
        assert d["nodeId"] == "a"
        assert d["total"] == 1
        assert "error" not in d
        assert d["neighbors"][0]["node"]["id"] in ("a", "b")
        assert d["neighbors"][0]["edge"]["edgeType"] == "relates_to"


class TestGetNeighborsRequest:
    """Tests for GetNeighborsRequest model."""

    def test_from_params_camel_case(self) -> None:
        req = GetNeighborsRequest.from_params({
            "nodeId": "abc",
            "direction": "outgoing",
            "edgeType": "depends_on",
            "limit": 10,
        })
        assert req.node_id == "abc"
        assert req.direction == "outgoing"
        assert req.edge_type == "depends_on"
        assert req.limit == 10

    def test_from_params_defaults(self) -> None:
        req = GetNeighborsRequest.from_params({"nodeId": "abc"})
        assert req.direction == "both"
        assert req.edge_type is None
        assert req.limit == 20

    def test_from_params_clamps_limit(self) -> None:
        assert GetNeighborsRequest.from_params({"nodeId": "a", "limit": 999}).limit == 100
        assert GetNeighborsRequest.from_params({"nodeId": "a", "limit": 0}).limit == 1

    def test_from_params_invalid_direction_passes_through(self) -> None:
        """Invalid direction is passed through; validate() catches it."""
        req = GetNeighborsRequest.from_params({"nodeId": "a", "direction": "sideways"})
        assert req.direction == "sideways"
        errors = req.validate()
        assert any("direction" in e for e in errors)

    def test_validate_missing_node_id(self) -> None:
        req = GetNeighborsRequest.from_params({})
        errors = req.validate()
        assert any("nodeId" in e for e in errors)

    def test_validate_invalid_edge_type(self) -> None:
        req = GetNeighborsRequest.from_params({
            "nodeId": "a",
            "edgeType": "contradicts",
        })
        errors = req.validate()
        assert any("edgeType" in e for e in errors)

    def test_validate_success(self) -> None:
        req = GetNeighborsRequest.from_params({
            "nodeId": "abc",
            "direction": "incoming",
            "edgeType": "relates_to",
        })
        assert req.validate() == []


class TestGetNeighborsDispatcher:
    """Tests for cstp.getNeighbors via dispatcher integration."""

    async def test_get_neighbors_via_dispatcher(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        """Full dispatcher integration for getNeighbors."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "depends_on", 0.8, None, "agent")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getNeighbors",
            params={"nodeId": "a", "direction": "both"},
            id="1",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None
        result = response.result
        assert result["nodeId"] == "a"
        assert result["total"] == 2

    async def test_get_neighbors_validation_error(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        """Missing nodeId returns validation error."""
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getNeighbors",
            params={},
            id="2",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is not None

    async def test_get_neighbors_with_edge_type_filter(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        """Edge type filtering via dispatcher."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "depends_on", 0.8, None, "agent")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getNeighbors",
            params={"nodeId": "a", "edgeType": "depends_on"},
            id="3",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None
        result = response.result
        assert result["total"] == 1
        assert result["neighbors"][0]["edge"]["edgeType"] == "depends_on"

    async def test_get_neighbors_with_limit(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        """Limit parameter via dispatcher."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "relates_to", 0.8, None, "agent")
        await link_decisions("a", "d", "relates_to", 0.6, None, "agent")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getNeighbors",
            params={"nodeId": "a", "limit": 2},
            id="4",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None
        assert response.result["total"] == 2


# ===========================================================================
# B. Auto-linking in recordDecision tests
# ===========================================================================


class TestAutoLinkDecision:
    """Tests for auto_link_decision service function."""

    async def test_creates_node_and_edges(self, memory_store: MemoryGraphStore) -> None:
        """Auto-linking creates a node and relates_to edges."""
        related = [
            {"id": "bbb22222", "summary": "Related decision B", "distance": 0.3},
            {"id": "ccc33333", "summary": "Related decision C", "distance": 0.5},
        ]
        edges_created = await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=["t1"],
            pattern=None,
            related_to=related,
        )
        assert edges_created == 2

        # Verify node was created
        node = await memory_store.get_node("aaa11111")
        assert node is not None
        assert node.category == "architecture"
        assert node.tags == ["t1"]

        # Verify edges
        edges = await memory_store.get_edges(source_id="aaa11111")
        assert len(edges) == 2
        target_ids = {e.target_id for e in edges}
        assert target_ids == {"bbb22222", "ccc33333"}

    async def test_weight_from_distance(self, memory_store: MemoryGraphStore) -> None:
        """Edge weight = max(0.01, 1.0 - distance)."""
        related = [
            {"id": "bbb22222", "summary": "Near", "distance": 0.2},
        ]
        await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=[],
            pattern=None,
            related_to=related,
        )
        edges = await memory_store.get_edges(source_id="aaa11111")
        assert len(edges) == 1
        assert abs(edges[0].weight - 0.8) < 0.01

    async def test_skips_self_loop(self, memory_store: MemoryGraphStore) -> None:
        """Doesn't create edge when related_id matches decision_id."""
        related = [
            {"id": "aaa11111", "summary": "Self", "distance": 0.1},
        ]
        edges_created = await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=[],
            pattern=None,
            related_to=related,
        )
        assert edges_created == 0

    async def test_no_related_to(self, memory_store: MemoryGraphStore) -> None:
        """Returns 0 when related_to is empty."""
        edges_created = await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=[],
            pattern=None,
            related_to=[],
        )
        assert edges_created == 0
        # Node should still be created
        node = await memory_store.get_node("aaa11111")
        assert node is not None

    async def test_skips_empty_related_id(self, memory_store: MemoryGraphStore) -> None:
        """Skips related entries with empty or missing IDs."""
        related = [
            {"id": "", "summary": "No ID", "distance": 0.3},
            {"summary": "Missing ID field", "distance": 0.3},
            {"id": "bbb22222", "summary": "Valid", "distance": 0.3},
        ]
        edges_created = await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=[],
            pattern=None,
            related_to=related,
        )
        assert edges_created == 1

    async def test_edge_metadata(self, memory_store: MemoryGraphStore) -> None:
        """Auto-linked edges have correct metadata."""
        related = [
            {"id": "bbb22222", "summary": "Test decision", "distance": 0.3},
        ]
        await auto_link_decision(
            decision_id="aaa11111",
            category="architecture",
            stakes="medium",
            confidence=0.9,
            tags=[],
            pattern=None,
            related_to=related,
        )
        edges = await memory_store.get_edges(source_id="aaa11111")
        assert len(edges) == 1
        edge = edges[0]
        assert edge.edge_type == "relates_to"
        assert edge.created_by == "auto-link"
        assert "Auto-linked" in (edge.context or "")
        assert edge.created_at is not None

    async def test_error_isolation_via_safe_auto_link(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """safe_auto_link swallows exceptions and returns 0."""
        from a2a.cstp.graph_service import safe_auto_link

        with patch(
            "a2a.cstp.graph_service.auto_link_decision",
            new_callable=AsyncMock,
            side_effect=RuntimeError("graph store exploded"),
        ):
            result = await safe_auto_link(
                response_id="aaa11111",
                category="architecture",
                stakes="medium",
                confidence=0.9,
                tags=[],
                pattern=None,
                related_to=[{"id": "bbb22222", "summary": "X", "distance": 0.3}],
            )
            assert result == 0  # Error swallowed, not propagated


# ===========================================================================
# C. MCP tool tests
# ===========================================================================


try:
    _has_mcp = bool(sys.modules.get("mcp") or __import__("importlib").util.find_spec("mcp"))
except (ValueError, ModuleNotFoundError):
    _has_mcp = False


@pytest.mark.skipif(not _has_mcp, reason="mcp package not installed (CI)")
class TestMcpGraphTools:
    """Tests for MCP graph tool registration and handlers."""

    async def test_tools_listed(self, memory_store: MemoryGraphStore) -> None:
        """All 3 graph tools appear in list_tools() with correct schemas."""
        from a2a.mcp_server import list_tools

        tools = await list_tools()
        tool_names = {t.name for t in tools}

        assert "link_decisions" in tool_names
        assert "get_graph" in tool_names
        assert "get_neighbors" in tool_names

    async def test_tools_have_schemas(self, memory_store: MemoryGraphStore) -> None:
        """Graph tools have non-empty input schemas."""
        from a2a.mcp_server import list_tools

        tools = await list_tools()
        graph_tools = {t.name: t for t in tools if t.name in (
            "link_decisions", "get_graph", "get_neighbors"
        )}

        for name, tool in graph_tools.items():
            assert tool.inputSchema is not None, f"{name} has no inputSchema"
            assert "properties" in tool.inputSchema, f"{name} schema missing properties"

    async def test_link_decisions_schema_fields(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """link_decisions schema has required fields."""
        from a2a.mcp_server import list_tools

        tools = await list_tools()
        link_tool = next(t for t in tools if t.name == "link_decisions")
        props = link_tool.inputSchema.get("properties", {})

        assert "source_id" in props
        assert "target_id" in props
        assert "edge_type" in props

    async def test_link_decisions_mcp_handler(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """link_decisions MCP tool call creates an edge."""
        from a2a.mcp_server import call_tool

        result = await call_tool("link_decisions", {
            "source_id": "aaa",
            "target_id": "bbb",
            "edge_type": "depends_on",
            "weight": 0.8,
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["success"] is True
        assert data["edge"]["sourceId"] == "aaa"
        assert data["edge"]["targetId"] == "bbb"
        assert data["edge"]["edgeType"] == "depends_on"

    async def test_get_graph_mcp_handler(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """get_graph MCP tool call returns subgraph."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("b", "c", "depends_on", 0.8, None, "agent")

        from a2a.mcp_server import call_tool

        result = await call_tool("get_graph", {
            "node_id": "a",
            "depth": 2,
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["centerId"] == "a"
        assert len(data["nodes"]) == 3
        assert len(data["edges"]) == 2

    async def test_get_neighbors_mcp_handler(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """get_neighbors MCP tool call returns neighbors."""
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "depends_on", 0.8, None, "agent")

        from a2a.mcp_server import call_tool

        result = await call_tool("get_neighbors", {
            "node_id": "a",
            "direction": "outgoing",
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["nodeId"] == "a"
        assert data["total"] == 2

    async def test_link_decisions_validation_error(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """link_decisions rejects missing required fields."""
        from a2a.mcp_server import call_tool

        result = await call_tool("link_decisions", {
            "source_id": "aaa",
            # missing target_id and edge_type
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert "error" in data

    async def test_get_neighbors_nonexistent_mcp(
        self, memory_store: MemoryGraphStore
    ) -> None:
        """get_neighbors MCP for missing node returns error in response."""
        from a2a.mcp_server import call_tool

        result = await call_tool("get_neighbors", {
            "node_id": "missing",
        })
        assert len(result) == 1
        data = json.loads(result[0].text)
        assert data["total"] == 0
        assert data.get("error") is not None
        assert "not found" in data["error"]
