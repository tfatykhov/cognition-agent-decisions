"""Pytest fixtures for dashboard tests."""
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

# Mock config before importing app
with patch.dict("os.environ", {
    "CSTP_URL": "http://localhost:9991",
    "CSTP_TOKEN": "test-token",
    "DASHBOARD_USER": "admin",
    "DASHBOARD_PASS": "test-pass",
    "SECRET_KEY": "test-secret",
}):
    from dashboard.app import app as flask_app


@pytest.fixture
def app() -> Generator[Flask, None, None]:
    """Create test Flask app."""
    flask_app.config.update({
        "TESTING": True,
    })
    yield flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Create test client."""
    return app.test_client()


@pytest.fixture
def auth_headers() -> dict[str, str]:
    """Return Basic Auth headers for test user."""
    import base64
    credentials = base64.b64encode(b"admin:test-pass").decode("utf-8")
    return {"Authorization": f"Basic {credentials}"}


@pytest.fixture
def mock_cstp() -> Generator[MagicMock, None, None]:
    """Mock CSTP client methods."""
    with patch("dashboard.app.cstp") as mock:
        mock.health_check = MagicMock(return_value=True)
        mock.list_decisions = MagicMock(return_value=([], 0))
        mock.get_decision = MagicMock(return_value=None)
        mock.get_calibration = MagicMock(return_value=_mock_calibration_stats())
        mock.get_neighbors = MagicMock(return_value=[])
        mock.check_drift = MagicMock(return_value=None)
        yield mock


def _mock_calibration_stats() -> Any:
    """Create mock CalibrationStats."""
    from dashboard.models import CalibrationStats, CategoryStats
    return CalibrationStats(
        total_decisions=10,
        reviewed_decisions=5,
        brier_score=0.05,
        accuracy=0.9,
        interpretation="well_calibrated",
        by_category=[
            CategoryStats(
                category="architecture",
                total=5,
                reviewed=3,
                accuracy=0.9,
                brier_score=0.04,
            ),
        ],
        recommendations=["Keep up the good calibration!"],
    )
