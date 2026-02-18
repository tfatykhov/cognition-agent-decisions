"""Tests for issue #167: calibration_service using DecisionStore instead of YAML rglob.

Verifies that _scan_decisions() and get_calibration() use the DecisionStore
fast path, and that the 'feature' filter works in ListQuery across backends.
"""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import patch

import pytest

from a2a.cstp.storage import ListQuery
from a2a.cstp.storage.factory import set_decision_store
from a2a.cstp.storage.memory import MemoryDecisionStore


def _make_decision(
    decision_id: str,
    confidence: float = 0.85,
    outcome: str | None = "success",
    category: str = "architecture",
    agent: str = "test-agent",
    project: str | None = None,
    feature: str | None = None,
    stakes: str = "medium",
    date: str = "2026-02-10T12:00:00",
) -> dict[str, Any]:
    """Create a decision dict for testing."""
    data: dict[str, Any] = {
        "id": decision_id,
        "decision": f"Test decision {decision_id}",
        "category": category,
        "confidence": confidence,
        "stakes": stakes,
        "status": "reviewed" if outcome else "pending",
        "date": date,
        "created_at": date,
        "recorded_by": agent,
    }
    if outcome:
        data["outcome"] = outcome
    if project:
        data["project"] = project
    if feature:
        data["feature"] = feature
    return data


@pytest.fixture
async def store_with_decisions() -> MemoryDecisionStore:
    """Create a MemoryDecisionStore pre-loaded with test decisions."""
    store = MemoryDecisionStore()
    await store.initialize()

    decisions = [
        _make_decision("aaa11111", 0.9, "success", "architecture"),
        _make_decision("bbb22222", 0.7, "failure", "process"),
        _make_decision("ccc33333", 0.8, "success", "architecture", feature="auth"),
        _make_decision("ddd44444", 0.6, "partial", "tooling", project="org/repo"),
        _make_decision("eee55555", 0.85, None, "architecture"),  # pending, no outcome
        _make_decision(
            "fff66666", 0.75, "success", "architecture",
            feature="auth", project="org/repo",
        ),
    ]
    for d in decisions:
        did = d["id"]
        await store.save(did, copy.deepcopy(d))

    set_decision_store(store)
    yield store
    set_decision_store(None)


class TestScanDecisionsUsesStore:
    """_scan_decisions should use DecisionStore instead of YAML rglob."""

    @pytest.mark.asyncio
    async def test_returns_all_decisions(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Store path returns all decisions when no filters applied."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions()
        assert len(results) == 6

    @pytest.mark.asyncio
    async def test_reviewed_only(self, store_with_decisions: MemoryDecisionStore) -> None:
        """reviewed_only=True filters to only reviewed decisions with outcomes."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(reviewed_only=True)
        assert len(results) == 5  # eee55555 has no outcome
        ids = {d["id"] for d in results}
        assert "eee55555" not in ids

    @pytest.mark.asyncio
    async def test_filter_by_category(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Category filter works through store."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(category="architecture")
        ids = {d["id"] for d in results}
        assert "bbb22222" not in ids  # process
        assert "ddd44444" not in ids  # tooling
        assert "aaa11111" in ids

    @pytest.mark.asyncio
    async def test_filter_by_feature(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Feature filter works through store."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(feature="auth")
        ids = {d["id"] for d in results}
        assert ids == {"ccc33333", "fff66666"}

    @pytest.mark.asyncio
    async def test_filter_by_agent(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Agent filter works through store."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(agent="nonexistent-agent")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_filter_by_project(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Project filter works through store."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(project="org/repo")
        ids = {d["id"] for d in results}
        assert ids == {"ddd44444", "fff66666"}

    @pytest.mark.asyncio
    async def test_combined_filters(self, store_with_decisions: MemoryDecisionStore) -> None:
        """Multiple filters combine correctly."""
        from a2a.cstp.calibration_service import _scan_decisions

        results = await _scan_decisions(
            category="architecture", feature="auth", reviewed_only=True
        )
        ids = {d["id"] for d in results}
        assert ids == {"ccc33333", "fff66666"}

    @pytest.mark.asyncio
    async def test_falls_back_to_yaml_when_store_unavailable(self, tmp_path) -> None:
        """Falls back to YAML scanning when store raises."""
        from a2a.cstp.calibration_service import _scan_decisions

        with patch(
            "a2a.cstp.storage.factory.get_decision_store",
            side_effect=RuntimeError("no store"),
        ):
            results = await _scan_decisions(decisions_path=str(tmp_path))
            assert results == []


class TestGetCalibrationUsesStore:
    """get_calibration should work through DecisionStore path."""

    @pytest.mark.asyncio
    async def test_returns_calibration_from_store(
        self, store_with_decisions: MemoryDecisionStore
    ) -> None:
        """get_calibration computes correct stats from store data."""
        from a2a.cstp.calibration_service import GetCalibrationRequest, get_calibration

        request = GetCalibrationRequest(min_decisions=3)
        response = await get_calibration(request)

        assert response.overall is not None
        assert response.overall.reviewed_decisions == 5
        assert response.overall.total_decisions == 6
        assert response.overall.accuracy > 0
        assert response.overall.brier_score >= 0

    @pytest.mark.asyncio
    async def test_calibration_with_category_filter(
        self, store_with_decisions: MemoryDecisionStore
    ) -> None:
        """Calibration respects category filter through store."""
        from a2a.cstp.calibration_service import GetCalibrationRequest, get_calibration

        request = GetCalibrationRequest(category="architecture", min_decisions=3)
        response = await get_calibration(request)

        assert response.overall is not None
        # architecture has 4 total (aaa, ccc, eee, fff), 3 reviewed with outcome
        assert response.overall.reviewed_decisions == 3


class TestListQueryFeatureFilter:
    """Verify feature filter works in ListQuery across backends."""

    @pytest.mark.asyncio
    async def test_memory_store_feature_filter(self) -> None:
        """MemoryDecisionStore filters by feature correctly."""
        store = MemoryDecisionStore()
        await store.initialize()

        await store.save("a1", _make_decision("a1", feature="payments"))
        await store.save("a2", _make_decision("a2", feature="auth"))
        await store.save("a3", _make_decision("a3"))  # no feature

        result = await store.list(ListQuery(feature="auth"))
        assert result.total == 1
        assert result.decisions[0]["id"] == "a2"

    @pytest.mark.asyncio
    async def test_memory_store_feature_filter_none(self) -> None:
        """No feature filter returns all decisions."""
        store = MemoryDecisionStore()
        await store.initialize()

        await store.save("a1", _make_decision("a1", feature="payments"))
        await store.save("a2", _make_decision("a2"))

        result = await store.list(ListQuery())
        assert result.total == 2
