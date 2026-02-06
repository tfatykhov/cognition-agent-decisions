"""Tests for calibration service."""
from datetime import datetime, UTC


# Import from parent package
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from a2a.cstp.calibration_service import window_to_dates


class TestWindowToDates:
    """Tests for window_to_dates function."""

    def test_window_30d(self) -> None:
        """Test 30-day window returns correct date range."""
        since, until = window_to_dates("30d")
        assert since is not None
        assert until is not None

        # Verify format
        datetime.strptime(since, "%Y-%m-%d")
        datetime.strptime(until, "%Y-%m-%d")

        # Verify range is approximately 30 days
        since_dt = datetime.strptime(since, "%Y-%m-%d")
        until_dt = datetime.strptime(until, "%Y-%m-%d")
        delta = until_dt - since_dt
        assert 29 <= delta.days <= 31

    def test_window_60d(self) -> None:
        """Test 60-day window."""
        since, until = window_to_dates("60d")
        assert since is not None
        assert until is not None

        since_dt = datetime.strptime(since, "%Y-%m-%d")
        until_dt = datetime.strptime(until, "%Y-%m-%d")
        delta = until_dt - since_dt
        assert 59 <= delta.days <= 61

    def test_window_90d(self) -> None:
        """Test 90-day window."""
        since, until = window_to_dates("90d")
        assert since is not None
        assert until is not None

        since_dt = datetime.strptime(since, "%Y-%m-%d")
        until_dt = datetime.strptime(until, "%Y-%m-%d")
        delta = until_dt - since_dt
        assert 89 <= delta.days <= 91

    def test_window_all(self) -> None:
        """Test 'all' window returns None for both dates."""
        since, until = window_to_dates("all")
        assert since is None
        assert until is None

    def test_window_none(self) -> None:
        """Test None window returns None for both dates."""
        since, until = window_to_dates(None)
        assert since is None
        assert until is None

    def test_window_unknown(self) -> None:
        """Test unknown window value returns None."""
        since, until = window_to_dates("7d")  # Not supported
        assert since is None
        assert until is None

    def test_until_is_today(self) -> None:
        """Test that until date is today."""
        since, until = window_to_dates("30d")
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        assert until == today
