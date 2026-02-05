"""Tests for Flask routes."""
from unittest.mock import AsyncMock

from flask.testing import FlaskClient


def test_health_check_ok(client: FlaskClient, mock_cstp: AsyncMock) -> None:
    """Test health endpoint returns 200 when CSTP is healthy."""
    mock_cstp.health_check = AsyncMock(return_value=True)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.data == b"OK"


def test_health_check_fail(client: FlaskClient, mock_cstp: AsyncMock) -> None:
    """Test health endpoint returns 503 when CSTP is down."""
    mock_cstp.health_check = AsyncMock(return_value=False)
    response = client.get("/health")
    assert response.status_code == 503


def test_index_redirects_to_decisions(client: FlaskClient, auth_headers: dict[str, str]) -> None:
    """Test root redirects to decisions list."""
    response = client.get("/", headers=auth_headers)
    assert response.status_code == 302
    assert "/decisions" in response.location


def test_decisions_requires_auth(client: FlaskClient) -> None:
    """Test decisions page requires authentication."""
    response = client.get("/decisions")
    assert response.status_code == 401


def test_decisions_list(client: FlaskClient, auth_headers: dict[str, str], mock_cstp: AsyncMock) -> None:
    """Test decisions list renders."""
    mock_cstp.list_decisions = AsyncMock(return_value=([], 0))
    response = client.get("/decisions", headers=auth_headers)
    assert response.status_code == 200
    assert b"Decisions" in response.data


def test_calibration_page(client: FlaskClient, auth_headers: dict[str, str], mock_cstp: AsyncMock) -> None:
    """Test calibration page renders with stats."""
    response = client.get("/calibration", headers=auth_headers)
    assert response.status_code == 200
    assert b"Calibration Dashboard" in response.data
    assert b"90%" in response.data  # accuracy from mock
