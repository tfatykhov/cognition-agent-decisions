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
