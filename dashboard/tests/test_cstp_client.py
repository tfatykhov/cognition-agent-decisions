"""Tests for CSTP client."""
from datetime import UTC, datetime
from unittest.mock import patch

from dashboard.models import CalibrationStats, Decision, GraphNeighbor, Reason


def test_decision_from_dict() -> None:
    """Test Decision.from_dict parsing."""
    data = {
        "id": "abc123",
        "summary": "Test decision",
        "category": "architecture",
        "stakes": "medium",
        "confidence": 0.85,
        "created_at": "2026-02-05T12:00:00Z",
        "context": "Some context",
        "reasons": [
            {"type": "analysis", "text": "Because reasons", "strength": 0.9}
        ],
    }
    
    decision = Decision.from_dict(data)
    
    assert decision.id == "abc123"
    assert decision.summary == "Test decision"
    assert decision.confidence == 0.85
    assert decision.confidence_pct == 85
    assert len(decision.reasons) == 1
    assert decision.reasons[0].type == "analysis"
    assert decision.outcome_icon == "⏳"


def test_decision_outcome_icons() -> None:
    """Test outcome icon mapping."""
    decision = Decision(
        id="test",
        summary="test",
        category="test",
        stakes="low",
        confidence=0.5,
        created_at=datetime.now(UTC),
    )
    
    assert decision.outcome_icon == "⏳"
    
    decision.outcome = "success"
    assert decision.outcome_icon == "✅"
    
    decision.outcome = "partial"
    assert decision.outcome_icon == "⚠️"
    
    decision.outcome = "failure"
    assert decision.outcome_icon == "❌"


def test_calibration_stats_from_dict() -> None:
    """Test CalibrationStats.from_dict parsing."""
    data = {
        "overall": {
            "total_decisions": 100,
            "reviewed_decisions": 50,
            "brier_score": 0.05,
            "accuracy": 0.9,
            "interpretation": "well_calibrated",
        },
        "by_category": [
            {
                "category": "architecture",
                "total_decisions": 30,
                "reviewed_decisions": 20,
                "accuracy": 0.95,
                "brier_score": 0.03,
            }
        ],
        "recommendations": [
            {"message": "Great work!"}
        ],
    }
    
    stats = CalibrationStats.from_dict(data)
    
    assert stats.total_decisions == 100
    assert stats.reviewed_decisions == 50
    assert stats.pending_decisions == 50
    assert stats.accuracy_pct == 90
    assert stats.calibration_icon == "✅"
    assert len(stats.by_category) == 1
    assert stats.by_category[0].category == "architecture"
    assert len(stats.recommendations) == 1


# --- Issue #150: recorded_by fallback ---


def test_decision_from_dict_recorded_by_fallback() -> None:
    """Test Decision.from_dict reads recorded_by when agent_id is absent."""
    data = {
        "id": "rec12345",
        "decision": "Some decision text",
        "category": "process",
        "stakes": "low",
        "confidence": 0.8,
        "created_at": "2026-02-16T10:00:00Z",
        "recorded_by": "my-agent",
    }

    decision = Decision.from_dict(data)

    assert decision.agent_id == "my-agent"


def test_decision_from_dict_agent_id_over_recorded_by() -> None:
    """Test Decision.from_dict prefers agent_id over recorded_by."""
    data = {
        "id": "pri12345",
        "decision": "Another decision",
        "category": "architecture",
        "stakes": "medium",
        "confidence": 0.9,
        "created_at": "2026-02-16T10:00:00Z",
        "agent_id": "primary-agent",
        "recorded_by": "fallback-agent",
    }

    decision = Decision.from_dict(data)

    assert decision.agent_id == "primary-agent"


def test_decision_from_dict_no_agent_id_no_recorded_by() -> None:
    """Test Decision.from_dict returns None when both agent_id and recorded_by are absent."""
    data = {
        "id": "none1234",
        "decision": "No agent info",
        "category": "tooling",
        "stakes": "low",
        "confidence": 0.5,
        "created_at": "2026-02-16T10:00:00Z",
    }

    decision = Decision.from_dict(data)

    assert decision.agent_id is None


# --- Issue #150: Reason strength parsing ---


def test_reason_strength_default() -> None:
    """Test Reason defaults strength to 0.8."""
    reason = Reason(type="analysis", text="Some reason")
    assert reason.strength == 0.8


def test_reason_strength_from_dict() -> None:
    """Test Decision.from_dict parses reason strength correctly."""
    data = {
        "id": "str12345",
        "decision": "Decision with reasons",
        "category": "architecture",
        "stakes": "high",
        "confidence": 0.95,
        "created_at": "2026-02-16T10:00:00Z",
        "reasons": [
            {"type": "analysis", "text": "Strong reason", "strength": 0.95},
            {"type": "pattern", "text": "Weak reason", "strength": 0.3},
            {"type": "intuition", "text": "Default reason"},
        ],
    }

    decision = Decision.from_dict(data)

    assert len(decision.reasons) == 3
    assert decision.reasons[0].strength == 0.95
    assert decision.reasons[1].strength == 0.3
    assert decision.reasons[2].strength == 0.8  # default


# --- Issue #150: GraphNeighbor model ---


def test_graph_neighbor_creation() -> None:
    """Test GraphNeighbor dataclass creation with all fields."""
    neighbor = GraphNeighbor(
        id="abc12345",
        summary="Use FastAPI for the API layer",
        category="architecture",
        stakes="high",
        date="2026-02-16",
        edge_type="depends_on",
        weight=0.85,
        direction="outgoing",
    )

    assert neighbor.id == "abc12345"
    assert neighbor.summary == "Use FastAPI for the API layer"
    assert neighbor.category == "architecture"
    assert neighbor.stakes == "high"
    assert neighbor.date == "2026-02-16"
    assert neighbor.edge_type == "depends_on"
    assert neighbor.weight == 0.85
    assert neighbor.direction == "outgoing"


def test_graph_neighbor_defaults() -> None:
    """Test GraphNeighbor defaults."""
    neighbor = GraphNeighbor(id="def12345")

    assert neighbor.summary == ""
    assert neighbor.category == ""
    assert neighbor.stakes == ""
    assert neighbor.date == ""
    assert neighbor.edge_type == ""
    assert neighbor.weight == 0.0
    assert neighbor.direction == ""


# --- Issue #150: CSTPClient.get_neighbors ---


def test_cstp_client_get_neighbors() -> None:
    """Test CSTPClient.get_neighbors parses response correctly."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")

    mock_result = {
        "neighbors": [
            {
                "node": {
                    "id": "neigh001",
                    "summary": "Use cursor pagination",
                    "category": "process",
                    "stakes": "medium",
                    "date": "2026-02-15",
                },
                "edge": {
                    "sourceId": "abcd1234",
                    "targetId": "neigh001",
                    "edgeType": "relates_to",
                    "weight": 0.7,
                },
            },
            {
                "node": {
                    "id": "neigh002",
                    "summary": "Add Redis caching",
                    "category": "architecture",
                    "stakes": "high",
                    "date": "2026-02-14",
                },
                "edge": {
                    "sourceId": "neigh002",
                    "targetId": "abcd1234",
                    "edgeType": "depends_on",
                    "weight": 0.9,
                },
            },
        ]
    }

    with patch.object(client, "_call", return_value=mock_result):
        neighbors = client.get_neighbors("abcd1234-full-id")

    assert len(neighbors) == 2

    # First neighbor: source matches decision_id[:8] -> outgoing
    assert neighbors[0].id == "neigh001"
    assert neighbors[0].summary == "Use cursor pagination"
    assert neighbors[0].direction == "outgoing"
    assert neighbors[0].edge_type == "relates_to"
    assert neighbors[0].weight == 0.7

    # Second neighbor: source != decision_id[:8] -> incoming
    assert neighbors[1].id == "neigh002"
    assert neighbors[1].summary == "Add Redis caching"
    assert neighbors[1].direction == "incoming"
    assert neighbors[1].edge_type == "depends_on"
    assert neighbors[1].weight == 0.9


def test_cstp_client_get_neighbors_empty() -> None:
    """Test CSTPClient.get_neighbors with no neighbors."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")

    with patch.object(client, "_call", return_value={"neighbors": []}):
        neighbors = client.get_neighbors("empty123")

    assert neighbors == []


def test_cstp_client_get_neighbors_calls_correct_method() -> None:
    """Test CSTPClient.get_neighbors sends correct params to _call."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")

    with patch.object(client, "_call", return_value={"neighbors": []}) as mock_call:
        client.get_neighbors("abcd1234-full-id", limit=10)

    mock_call.assert_called_once_with("cstp.getNeighbors", {
        "nodeId": "abcd1234",
        "direction": "both",
        "limit": 10,
    })


# --- Issue #177: list_decisions via cstp.listDecisions ---


def test_list_decisions_calls_list_decisions_method() -> None:
    """Test list_decisions calls cstp.listDecisions (not queryDecisions)."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0, "limit": 20, "offset": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.list_decisions()

    mock_call.assert_called_once()
    assert mock_call.call_args[0][0] == "cstp.listDecisions"


def test_list_decisions_default_params() -> None:
    """Test list_decisions sends correct default params."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.list_decisions()

    params = mock_call.call_args[0][1]
    assert params["limit"] == 50
    assert params["offset"] == 0
    # sort and order are omitted when default (created_at, desc)
    assert "sort" not in params
    assert "order" not in params
    # Optional params should not be present when not specified
    assert "category" not in params
    assert "stakes" not in params
    assert "status" not in params
    assert "dateFrom" not in params
    assert "dateTo" not in params
    assert "search" not in params


def test_list_decisions_all_params() -> None:
    """Test list_decisions sends all params when specified."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.list_decisions(
            limit=30, offset=10,
            category="architecture", stakes="high",
            status="pending",
            date_from="2026-01-01", date_to="2026-02-01",
            search="keyword", sort="confidence", order="asc",
        )

    params = mock_call.call_args[0][1]
    assert params["limit"] == 30
    assert params["offset"] == 10
    assert params["category"] == "architecture"
    assert params["stakes"] == "high"
    assert params["status"] == "pending"
    assert params["dateFrom"] == "2026-01-01"
    assert params["dateTo"] == "2026-02-01"
    assert params["search"] == "keyword"
    assert params["sort"] == "confidence"
    assert params["order"] == "asc"


def test_list_decisions_parses_response() -> None:
    """Test list_decisions parses decision list and total from response."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {
        "decisions": [
            {
                "id": "dec00001",
                "decision": "Use SQLite for storage",
                "category": "architecture",
                "stakes": "high",
                "confidence": 0.9,
                "created_at": "2026-02-18T10:00:00Z",
            },
            {
                "id": "dec00002",
                "decision": "Add date filters",
                "category": "tooling",
                "stakes": "medium",
                "confidence": 0.75,
                "created_at": "2026-02-17T10:00:00Z",
            },
        ],
        "total": 42,
    }

    with patch.object(client, "_call", return_value=mock_result):
        decisions, total = client.list_decisions()

    assert total == 42
    assert len(decisions) == 2
    assert decisions[0].id == "dec00001"
    assert decisions[0].summary == "Use SQLite for storage"
    assert decisions[1].id == "dec00002"


def test_list_decisions_omits_falsy_optional_params() -> None:
    """Test list_decisions omits None/empty optional params."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.list_decisions(
            category=None, stakes=None, status=None,
            date_from=None, date_to=None, search=None,
        )

    params = mock_call.call_args[0][1]
    # Only limit and offset should be present (sort/order omitted when default)
    assert set(params.keys()) == {"limit", "offset"}


# --- Issue #177: search_decisions via cstp.queryDecisions ---


def test_search_decisions_calls_query_decisions_method() -> None:
    """Test search_decisions calls cstp.queryDecisions for semantic search."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.search_decisions(query="architecture patterns")

    mock_call.assert_called_once()
    assert mock_call.call_args[0][0] == "cstp.queryDecisions"


def test_search_decisions_params() -> None:
    """Test search_decisions sends correct params."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.search_decisions(query="test query", limit=10, category="process")

    params = mock_call.call_args[0][1]
    assert params["query"] == "test query"
    assert params["limit"] == 10
    assert params["category"] == "process"


def test_search_decisions_parses_response() -> None:
    """Test search_decisions returns parsed decisions and total."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {
        "decisions": [
            {
                "id": "srch0001",
                "decision": "Found via semantic search",
                "category": "architecture",
                "stakes": "medium",
                "confidence": 0.85,
                "created_at": "2026-02-18T10:00:00Z",
            },
        ],
        "total": 1,
    }

    with patch.object(client, "_call", return_value=mock_result):
        decisions, total = client.search_decisions(query="search test")

    assert total == 1
    assert len(decisions) == 1
    assert decisions[0].id == "srch0001"


def test_search_decisions_without_category() -> None:
    """Test search_decisions omits category when None."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"decisions": [], "total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.search_decisions(query="test")

    params = mock_call.call_args[0][1]
    assert "category" not in params


# --- Issue #177: get_stats via cstp.getStats ---


def test_get_stats_calls_correct_method() -> None:
    """Test get_stats calls cstp.getStats."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"total": 0, "byCategory": {}}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.get_stats()

    mock_call.assert_called_once_with("cstp.getStats", {})


def test_get_stats_with_filters() -> None:
    """Test get_stats passes date range and project filters."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"total": 10}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.get_stats(
            date_from="2026-01-01", date_to="2026-02-01", project="owner/repo",
        )

    params = mock_call.call_args[0][1]
    assert params["dateFrom"] == "2026-01-01"
    assert params["dateTo"] == "2026-02-01"
    assert params["project"] == "owner/repo"


def test_get_stats_returns_raw_dict() -> None:
    """Test get_stats returns the raw stats dict from server."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {
        "total": 25,
        "byCategory": {"architecture": 10},
        "byStakes": {"high": 5},
        "byStatus": {"pending": 20},
        "byAgent": {"agent-1": 12},
        "byDay": [{"date": "2026-02-18", "count": 5}],
        "topTags": [{"tag": "testing", "count": 8}],
        "recentActivity": {"last_24h": 3},
    }

    with patch.object(client, "_call", return_value=mock_result):
        result = client.get_stats()

    assert result["total"] == 25
    assert result["byCategory"]["architecture"] == 10
    assert result["byStakes"]["high"] == 5
    assert len(result["topTags"]) == 1


def test_get_stats_omits_none_params() -> None:
    """Test get_stats omits None params."""
    from dashboard.cstp_client import CSTPClient

    client = CSTPClient("http://localhost:9991", "test-token")
    mock_result = {"total": 0}

    with patch.object(client, "_call", return_value=mock_result) as mock_call:
        client.get_stats(date_from=None, date_to=None, project=None)

    params = mock_call.call_args[0][1]
    assert params == {}
