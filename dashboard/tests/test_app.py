"""Tests for Flask routes."""
from datetime import UTC, datetime
from unittest.mock import MagicMock

from flask.testing import FlaskClient

from dashboard.models import Decision, GraphNeighbor, Reason


def test_health_check_ok(client: FlaskClient, mock_cstp: MagicMock) -> None:
    """Test health endpoint returns 200 when CSTP is healthy."""
    mock_cstp.health_check = MagicMock(return_value=True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"OK"


def test_health_check_fail(client: FlaskClient, mock_cstp: MagicMock) -> None:
    """Test health endpoint returns 503 when CSTP is down."""
    mock_cstp.health_check = MagicMock(return_value=False)
    response = client.get("/health")
    assert response.status_code == 503


def test_index_renders_overview(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test root renders overview dashboard."""
    response = client.get("/", headers=auth_headers)
    assert response.status_code == 200


def test_decisions_requires_auth(client: FlaskClient) -> None:
    """Test decisions page requires authentication."""
    response = client.get("/decisions")
    assert response.status_code == 401


def test_decisions_list(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test decisions list renders."""
    mock_cstp.list_decisions = MagicMock(return_value=([], 0))
    response = client.get("/decisions", headers=auth_headers)
    assert response.status_code == 200
    assert b"Decisions" in response.data


def test_calibration_page(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test calibration page renders with stats."""
    response = client.get("/calibration", headers=auth_headers)
    assert response.status_code == 200
    assert b"Calibration" in response.data
    assert b"90%" in response.data  # accuracy from mock


# --- Issue #150: decision_detail route with graph_neighbors ---


def _make_decision(
    summary: str = "Short summary",
    agent_id: str | None = None,
    reasons: list[Reason] | None = None,
) -> Decision:
    """Helper to create a test Decision."""
    return Decision(
        id="abcd1234",
        summary=summary,
        category="architecture",
        stakes="medium",
        confidence=0.85,
        created_at=datetime(2026, 2, 16, 12, 0, 0, tzinfo=UTC),
        agent_id=agent_id,
        reasons=reasons or [],
    )


def test_decision_detail_with_graph_neighbors(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test decision_detail route passes graph_neighbors to template."""
    decision = _make_decision()
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[
        GraphNeighbor(
            id="neigh001",
            summary="Use cursor pagination for lists",
            category="process",
            edge_type="relates_to",
            weight=0.7,
            direction="outgoing",
        ),
    ])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"Graph Neighbors" in response.data
    assert b"neigh001" in response.data
    assert b"relates to" in response.data  # edge_type rendered with replace('_', ' ')
    assert b"Use cursor pagination" in response.data  # summary text shown


def test_decision_detail_graph_neighbors_error_isolation(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test decision_detail still renders when get_neighbors raises."""
    decision = _make_decision()
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(side_effect=Exception("Network error"))

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    # Page renders without graph neighbors section
    assert b"Graph Neighbors" not in response.data


def test_decision_detail_no_neighbors(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test decision_detail with empty graph_neighbors."""
    decision = _make_decision()
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"Graph Neighbors" not in response.data


# --- Issue #150: Full decision text card rendering ---


def test_decision_detail_shows_full_text_long_summary(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test full decision text card is shown when summary > 80 chars."""
    long_summary = "A" * 100  # 100 chars > 80 threshold
    decision = _make_decision(summary=long_summary)
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"decision-full-text" in response.data


def test_decision_detail_hides_full_text_short_summary(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test full decision text card is hidden when summary <= 80 chars."""
    short_summary = "B" * 60  # 60 chars <= 80 threshold
    decision = _make_decision(summary=short_summary)
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"decision-full-text" not in response.data


# --- Issue #150: Reason strength bars rendering ---


def test_decision_detail_shows_reason_strength_bars(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test reason strength bars render in template."""
    decision = _make_decision(reasons=[
        Reason(type="analysis", text="Strong analysis", strength=0.95),
        Reason(type="pattern", text="Weak pattern", strength=0.3),
    ])
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"reason-strength" in response.data
    assert b"95%" in response.data  # high strength percentage
    assert b"30%" in response.data  # low strength percentage
    # Check color coding: high gets --high, low gets --low
    assert b"confidence-bar-fill--high" in response.data
    assert b"confidence-bar-fill--low" in response.data


# --- Issue #150: recorded_by shown as Agent badge ---


def test_decision_detail_shows_agent_from_recorded_by(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test agent badge renders when agent_id is set (from recorded_by)."""
    decision = _make_decision(agent_id="test-agent")
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    assert b"test-agent" in response.data
    assert b"Agent" in response.data


# --- Issue #150: Graph neighbor direction arrows ---


def test_decision_detail_graph_neighbor_directions(
    client: FlaskClient, auth_headers: dict[str, str], mock_cstp: MagicMock
) -> None:
    """Test graph neighbor cards show correct direction arrows."""
    decision = _make_decision()
    mock_cstp.get_decision = MagicMock(return_value=decision)
    mock_cstp.get_neighbors = MagicMock(return_value=[
        GraphNeighbor(
            id="out00001",
            edge_type="depends_on",
            weight=0.8,
            direction="outgoing",
        ),
        GraphNeighbor(
            id="inc00001",
            edge_type="supersedes",
            weight=0.6,
            direction="incoming",
        ),
    ])

    response = client.get("/decisions/abcd1234", headers=auth_headers)

    assert response.status_code == 200
    html = response.data.decode()
    # Outgoing arrow: right arrow entity &#8594;
    assert "&#8594;" in html
    # Incoming arrow: left arrow entity &#8592;
    assert "&#8592;" in html
    # Edge type badges
    assert "depends on" in html
    assert "supersedes" in html
