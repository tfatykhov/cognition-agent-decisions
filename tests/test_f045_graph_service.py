"""Tests for F045: Graph service + CSTP dispatcher integration."""

from typing import Any

import pytest

from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.graph_service import (
    LinkDecisionsResponse,
    get_graph,
    initialize_graph_from_decisions,
    link_decisions,
)
from a2a.cstp.graphdb.factory import set_graph_store
from a2a.cstp.graphdb.memory import MemoryGraphStore
from a2a.cstp.models import GetGraphRequest, LinkDecisionsRequest
from a2a.models.jsonrpc import JsonRpcRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_store() -> MemoryGraphStore:
    store = MemoryGraphStore()
    set_graph_store(store)
    yield store
    set_graph_store(None)


@pytest.fixture
def dispatcher() -> CstpDispatcher:
    d = CstpDispatcher()
    register_methods(d)
    return d


# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestLinkDecisionsRequest:
    def test_from_params_camel_case(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "aaa",
            "targetId": "bbb",
            "edgeType": "depends_on",
            "weight": 0.8,
            "context": "test",
        })
        assert req.source_id == "aaa"
        assert req.target_id == "bbb"
        assert req.edge_type == "depends_on"
        assert req.weight == 0.8
        assert req.context == "test"

    def test_from_params_snake_case(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "source_id": "aaa",
            "target_id": "bbb",
            "edge_type": "relates_to",
        })
        assert req.source_id == "aaa"
        assert req.edge_type == "relates_to"

    def test_from_params_defaults(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "a",
            "targetId": "b",
            "edgeType": "relates_to",
        })
        assert req.weight == 1.0
        assert req.context is None

    def test_validate_missing_fields(self) -> None:
        req = LinkDecisionsRequest.from_params({})
        errors = req.validate()
        assert any("sourceId" in e for e in errors)
        assert any("targetId" in e for e in errors)
        assert any("edgeType" in e for e in errors)

    def test_validate_self_loop(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "aaa",
            "targetId": "aaa",
            "edgeType": "relates_to",
        })
        errors = req.validate()
        assert any("self-loop" in e for e in errors)

    def test_validate_invalid_edge_type(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "a",
            "targetId": "b",
            "edgeType": "contradicts",
        })
        errors = req.validate()
        assert any("edgeType" in e for e in errors)

    def test_validate_invalid_weight(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "a",
            "targetId": "b",
            "edgeType": "relates_to",
            "weight": -1,
        })
        errors = req.validate()
        assert any("weight" in e for e in errors)

    def test_validate_success(self) -> None:
        req = LinkDecisionsRequest.from_params({
            "sourceId": "a",
            "targetId": "b",
            "edgeType": "depends_on",
        })
        assert req.validate() == []


class TestGetGraphRequest:
    def test_from_params_camel_case(self) -> None:
        req = GetGraphRequest.from_params({
            "nodeId": "abc",
            "depth": 3,
            "edgeTypes": ["relates_to", "depends_on"],
            "direction": "outgoing",
        })
        assert req.node_id == "abc"
        assert req.depth == 3
        assert req.edge_types == ["relates_to", "depends_on"]
        assert req.direction == "outgoing"

    def test_from_params_defaults(self) -> None:
        req = GetGraphRequest.from_params({"nodeId": "abc"})
        assert req.depth == 1
        assert req.edge_types is None
        assert req.direction == "both"

    def test_from_params_clamps_depth(self) -> None:
        assert GetGraphRequest.from_params({"nodeId": "a", "depth": 99}).depth == 5
        assert GetGraphRequest.from_params({"nodeId": "a", "depth": 0}).depth == 1

    def test_validate_missing_node_id(self) -> None:
        req = GetGraphRequest.from_params({})
        errors = req.validate()
        assert any("nodeId" in e for e in errors)

    def test_validate_invalid_direction(self) -> None:
        req = GetGraphRequest.from_params({
            "nodeId": "a",
            "direction": "sideways",
        })
        errors = req.validate()
        assert any("direction" in e for e in errors)

    def test_validate_invalid_edge_types(self) -> None:
        req = GetGraphRequest.from_params({
            "nodeId": "a",
            "edgeTypes": ["relates_to", "blocks"],
        })
        errors = req.validate()
        assert any("blocks" in e for e in errors)

    def test_validate_success(self) -> None:
        req = GetGraphRequest.from_params({"nodeId": "abc"})
        assert req.validate() == []


# ---------------------------------------------------------------------------
# Service function tests
# ---------------------------------------------------------------------------


class TestLinkDecisions:
    async def test_link_success(self, memory_store: MemoryGraphStore) -> None:
        response = await link_decisions(
            source_id="aaa",
            target_id="bbb",
            edge_type="depends_on",
            weight=1.0,
            context="test link",
            agent_id="test-agent",
        )
        assert response.success
        assert response.edge is not None
        assert response.edge.source_id == "aaa"
        assert response.edge.target_id == "bbb"
        assert response.edge.edge_type == "depends_on"
        assert response.edge.created_by == "test-agent"
        assert response.edge.context == "test link"
        assert response.edge.created_at is not None

    async def test_link_creates_nodes(self, memory_store: MemoryGraphStore) -> None:
        await link_decisions("x", "y", "relates_to", 1.0, None, "agent")
        assert await memory_store.node_count() == 2

    async def test_link_response_to_dict(self, memory_store: MemoryGraphStore) -> None:
        response = await link_decisions("a", "b", "relates_to", 0.5, None, "agent")
        d = response.to_dict()
        assert d["success"] is True
        assert d["edge"]["sourceId"] == "a"
        assert d["edge"]["edgeType"] == "relates_to"

    async def test_link_error_response_to_dict(self) -> None:
        response = LinkDecisionsResponse(success=False, error="some error")
        d = response.to_dict()
        assert d["success"] is False
        assert d["error"] == "some error"


class TestGetGraph:
    async def test_get_graph_basic(self, memory_store: MemoryGraphStore) -> None:
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("b", "c", "depends_on", 1.0, None, "agent")

        response = await get_graph("a", depth=2, edge_types=None, direction="both")
        assert response.center_id == "a"
        assert response.depth == 2
        assert len(response.nodes) == 3
        assert len(response.edges) == 2
        assert response.error is None

    async def test_get_graph_nonexistent_node(
        self, memory_store: MemoryGraphStore
    ) -> None:
        response = await get_graph("missing", depth=1, edge_types=None, direction="both")
        assert response.error is not None
        assert "not found" in response.error

    async def test_get_graph_response_to_dict(
        self, memory_store: MemoryGraphStore
    ) -> None:
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        response = await get_graph("a", depth=1, edge_types=None, direction="both")
        d = response.to_dict()
        assert d["centerId"] == "a"
        assert d["depth"] == 1
        assert len(d["nodes"]) == 2
        assert len(d["edges"]) == 1
        assert d["nodes"][0]["id"] in ("a", "b")
        assert d["edges"][0]["sourceId"] == "a"

    async def test_get_graph_with_edge_filter(
        self, memory_store: MemoryGraphStore
    ) -> None:
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("a", "c", "depends_on", 1.0, None, "agent")

        response = await get_graph(
            "a", depth=1, edge_types=["depends_on"], direction="both"
        )
        node_ids = {n.id for n in response.nodes}
        assert "c" in node_ids
        assert "b" not in node_ids


# ---------------------------------------------------------------------------
# Graph initialization from decisions tests
# ---------------------------------------------------------------------------


class TestInitializeFromDecisions:
    async def test_loads_nodes_and_edges(
        self, memory_store: MemoryGraphStore
    ) -> None:
        decisions: list[dict[str, Any]] = [
            {
                "id": "aaa11111-full-uuid",
                "decision": "Decision A",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.9,
                "outcome": "success",
                "created_at": "2026-02-15T00:00:00Z",
                "tags": ["t1"],
                "related_to": [
                    {"id": "bbb22222", "summary": "Related", "distance": 0.3},
                ],
            },
            {
                "id": "bbb22222-full-uuid",
                "decision": "Decision B",
                "category": "process",
                "stakes": "low",
                "created_at": "2026-02-14T00:00:00Z",
            },
        ]

        edges_loaded = await initialize_graph_from_decisions(decisions)
        assert edges_loaded == 1

        # Check nodes were created (truncated to 8 chars)
        node_a = await memory_store.get_node("aaa11111")
        assert node_a is not None
        assert node_a.category == "architecture"

        node_b = await memory_store.get_node("bbb22222")
        assert node_b is not None

        # Check edge
        edges = await memory_store.get_edges(source_id="aaa11111")
        assert len(edges) == 1
        assert edges[0].target_id == "bbb22222"
        assert edges[0].edge_type == "relates_to"
        # Weight = 1.0 - 0.3 = 0.7
        assert abs(edges[0].weight - 0.7) < 0.01

    async def test_skips_empty_ids(self, memory_store: MemoryGraphStore) -> None:
        decisions: list[dict[str, Any]] = [
            {"id": "", "decision": "No ID"},
            {"decision": "Missing ID field"},
        ]
        edges = await initialize_graph_from_decisions(decisions)
        assert edges == 0
        assert await memory_store.node_count() == 0

    async def test_empty_decisions_list(self, memory_store: MemoryGraphStore) -> None:
        edges = await initialize_graph_from_decisions([])
        assert edges == 0

    async def test_handles_missing_related_to(
        self, memory_store: MemoryGraphStore
    ) -> None:
        decisions: list[dict[str, Any]] = [
            {"id": "aaa11111", "decision": "No relations"},
        ]
        edges = await initialize_graph_from_decisions(decisions)
        assert edges == 0
        assert await memory_store.node_count() == 1


# ---------------------------------------------------------------------------
# Dispatcher integration tests
# ---------------------------------------------------------------------------


class TestDispatcherIntegration:
    async def test_link_decisions_via_dispatcher(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.linkDecisions",
            params={
                "sourceId": "aaa",
                "targetId": "bbb",
                "edgeType": "depends_on",
                "weight": 0.9,
            },
            id="1",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None
        result = response.result
        assert result["success"] is True
        assert result["edge"]["sourceId"] == "aaa"
        assert result["edge"]["edgeType"] == "depends_on"

    async def test_link_decisions_validation_error(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.linkDecisions",
            params={"sourceId": "aaa"},  # Missing targetId, edgeType
            id="2",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is not None

    async def test_get_graph_via_dispatcher(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        # First link some decisions
        await link_decisions("a", "b", "relates_to", 1.0, None, "agent")
        await link_decisions("b", "c", "depends_on", 1.0, None, "agent")

        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getGraph",
            params={"nodeId": "a", "depth": 2},
            id="3",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None
        result = response.result
        assert result["centerId"] == "a"
        assert len(result["nodes"]) == 3
        assert len(result["edges"]) == 2

    async def test_get_graph_not_found(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getGraph",
            params={"nodeId": "missing"},
            id="4",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is None  # Not an RPC error, just empty result
        result = response.result
        assert result["error"] is not None

    async def test_get_graph_validation_error(
        self, dispatcher: CstpDispatcher, memory_store: MemoryGraphStore
    ) -> None:
        request = JsonRpcRequest(
            jsonrpc="2.0",
            method="cstp.getGraph",
            params={},  # Missing nodeId
            id="5",
        )
        response = await dispatcher.dispatch(request, "test-agent")
        assert response.error is not None
