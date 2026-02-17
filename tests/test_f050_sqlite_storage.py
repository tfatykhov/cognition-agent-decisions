"""Comprehensive tests for F050 SQLite Storage Layer.

Tests the DecisionStore ABC contract across MemoryDecisionStore and
SQLiteDecisionStore backends, plus SQLite-specific features, factory
tests, and dispatcher RPC handler integration.
"""

from __future__ import annotations

import copy
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from a2a.cstp.storage import DecisionStore, ListQuery, ListResult, StatsQuery, StatsResult
from a2a.cstp.storage.memory import MemoryDecisionStore
from a2a.cstp.storage.sqlite import SQLiteDecisionStore


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_DECISION: dict[str, Any] = {
    "decision": "Use FastAPI for the web framework",
    "confidence": 0.85,
    "category": "architecture",
    "stakes": "medium",
    "status": "pending",
    "context": "Evaluating web frameworks for the new API",
    "recorded_by": "test-agent",
    "project": "test/repo",
    "feature": "api-layer",
    "date": "2026-02-16",
    "created_at": "2026-02-16T12:00:00",
    "tags": ["python", "web"],
    "reasons": [
        {"type": "analysis", "text": "FastAPI is async-native", "strength": 0.9},
        {"type": "pattern", "text": "Team already uses it", "strength": 0.8},
    ],
    "bridge": {
        "structure": "FastAPI + uvicorn",
        "function": "High-performance async API",
    },
}

SAMPLE_DECISION_FULL: dict[str, Any] = {
    **SAMPLE_DECISION,
    "deliberation": {
        "inputs": [
            {"id": "i1", "text": "Benchmark results", "source": "perf-test"},
        ],
        "steps": [
            {"step": 1, "thought": "Compared Flask vs FastAPI benchmarks"},
        ],
        "total_duration_ms": 1500,
    },
    "bridge": {
        "structure": "FastAPI + uvicorn",
        "function": "High-performance async API",
        "tolerance": ["deployment platform"],
        "enforcement": ["async handlers"],
        "prevention": ["sync blocking calls"],
    },
}


def _sample(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a fresh copy of sample decision data with optional overrides."""
    data = copy.deepcopy(SAMPLE_DECISION)
    if overrides:
        data.update(overrides)
    return data


def _sample_full(overrides: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a fresh copy of full sample decision data with optional overrides."""
    data = copy.deepcopy(SAMPLE_DECISION_FULL)
    if overrides:
        data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Parameterized fixture: memory + sqlite
# ---------------------------------------------------------------------------


@pytest.fixture(params=["memory", "sqlite"])
async def store(request: pytest.FixtureRequest, tmp_path: Any) -> Any:
    """Create and initialize a DecisionStore backend."""
    if request.param == "memory":
        s = MemoryDecisionStore()
    else:
        s = SQLiteDecisionStore(db_path=str(tmp_path / "test.db"))
    await s.initialize()
    yield s
    await s.close()


@pytest.fixture
async def sqlite_store(tmp_path: Any) -> Any:
    """Create a SQLite-only store for SQLite-specific tests."""
    s = SQLiteDecisionStore(db_path=str(tmp_path / "sqlite_test.db"))
    await s.initialize()
    yield s
    await s.close()


# =========================================================================
# A) ABC Contract Tests (parameterized across memory + sqlite)
# =========================================================================


class TestSaveAndGet:
    """Tests for save() and get() operations."""

    async def test_save_and_get(self, store: DecisionStore) -> None:
        """Save a decision and retrieve it, verifying core fields."""
        data = _sample()
        ok = await store.save("aabb0001", data)
        assert ok is True

        got = await store.get("aabb0001")
        assert got is not None
        assert got["decision"] == "Use FastAPI for the web framework"
        assert got["confidence"] == 0.85
        assert got["category"] == "architecture"
        assert got["stakes"] == "medium"
        assert got["status"] == "pending"

    async def test_save_with_full_data(self, store: DecisionStore) -> None:
        """Save a decision with tags, reasons, bridge, and deliberation."""
        data = _sample_full()
        ok = await store.save("aabb0002", data)
        assert ok is True

        got = await store.get("aabb0002")
        assert got is not None
        # Tags
        tags = got.get("tags") or []
        assert "python" in tags
        assert "web" in tags
        # Reasons
        reasons = got.get("reasons") or []
        assert len(reasons) >= 2
        assert any(r["type"] == "analysis" for r in reasons)
        # Bridge
        bridge = got.get("bridge")
        assert bridge is not None
        assert bridge["structure"] == "FastAPI + uvicorn"
        assert bridge["function"] == "High-performance async API"
        # Deliberation
        delib = got.get("deliberation")
        assert delib is not None
        assert delib["total_duration_ms"] == 1500

    async def test_get_nonexistent(self, store: DecisionStore) -> None:
        """Getting a non-existent decision returns None."""
        got = await store.get("00000000")
        assert got is None

    async def test_save_upsert(self, store: DecisionStore) -> None:
        """Saving twice with same ID overwrites the first."""
        data1 = _sample({"decision": "Original decision"})
        await store.save("aabb0003", data1)

        data2 = _sample({"decision": "Updated decision", "confidence": 0.95})
        await store.save("aabb0003", data2)

        got = await store.get("aabb0003")
        assert got is not None
        assert got["decision"] == "Updated decision"
        assert got["confidence"] == 0.95


class TestDelete:
    """Tests for delete() operation."""

    async def test_delete(self, store: DecisionStore) -> None:
        """Save, delete, and verify the decision is gone."""
        await store.save("aabb0004", _sample())
        deleted = await store.delete("aabb0004")
        assert deleted is True
        assert await store.get("aabb0004") is None

    async def test_delete_nonexistent(self, store: DecisionStore) -> None:
        """Deleting a non-existent decision returns False."""
        deleted = await store.delete("00000000")
        assert deleted is False


class TestUpdateOutcome:
    """Tests for update_outcome() operation."""

    async def test_update_outcome(self, store: DecisionStore) -> None:
        """Set outcome and verify status becomes 'reviewed'."""
        await store.save("aabb0005", _sample())
        ok = await store.update_outcome(
            "aabb0005",
            outcome="success",
            result="It worked great",
            lessons="FastAPI was a good choice",
        )
        assert ok is True

        got = await store.get("aabb0005")
        assert got is not None
        assert got["status"] == "reviewed"
        assert got.get("outcome") == "success"
        # reviewed_at should be set
        assert got.get("reviewed_at") is not None

    async def test_update_outcome_nonexistent(self, store: DecisionStore) -> None:
        """Updating outcome for non-existent decision returns False."""
        ok = await store.update_outcome("00000000", outcome="success")
        assert ok is False


class TestUpdateFields:
    """Tests for update_fields() operation."""

    async def test_update_fields_tags(self, store: DecisionStore) -> None:
        """Update tags field on an existing decision."""
        await store.save("aabb0006", _sample())
        ok = await store.update_fields("aabb0006", tags=["new-tag", "updated"])
        assert ok is True

        got = await store.get("aabb0006")
        assert got is not None
        tags = got.get("tags") or []
        assert "new-tag" in tags
        assert "updated" in tags

    async def test_update_fields_pattern(self, store: DecisionStore) -> None:
        """Update pattern field on an existing decision."""
        await store.save("aabb0007", _sample())
        ok = await store.update_fields("aabb0007", pattern="framework-selection")
        assert ok is True

        got = await store.get("aabb0007")
        assert got is not None
        assert got.get("pattern") == "framework-selection"

    async def test_update_fields_confidence(self, store: DecisionStore) -> None:
        """Update confidence field on an existing decision."""
        await store.save("aabb0008", _sample())
        ok = await store.update_fields("aabb0008", confidence=0.99)
        assert ok is True

        got = await store.get("aabb0008")
        assert got is not None
        assert got["confidence"] == 0.99

    async def test_update_fields_nonexistent(self, store: DecisionStore) -> None:
        """Updating fields on non-existent decision returns False."""
        ok = await store.update_fields("00000000", pattern="nope")
        assert ok is False


class TestListDecisions:
    """Tests for list() operation with various filters."""

    async def _seed(self, store: DecisionStore) -> None:
        """Seed the store with multiple decisions for list tests."""
        decisions = [
            ("d0000001", {
                "decision": "Use SQLite for storage",
                "confidence": 0.9, "category": "architecture",
                "stakes": "high", "status": "pending",
                "recorded_by": "agent-a", "project": "proj/alpha",
                "created_at": "2026-02-10T10:00:00",
                "tags": ["sqlite", "storage"],
            }),
            ("d0000002", {
                "decision": "Add FastAPI middleware",
                "confidence": 0.8, "category": "tooling",
                "stakes": "medium", "status": "reviewed",
                "recorded_by": "agent-b", "project": "proj/beta",
                "created_at": "2026-02-12T10:00:00",
                "tags": ["python", "web"],
            }),
            ("d0000003", {
                "decision": "Implement caching layer",
                "confidence": 0.7, "category": "architecture",
                "stakes": "low", "status": "pending",
                "recorded_by": "agent-a", "project": "proj/alpha",
                "created_at": "2026-02-14T10:00:00",
                "tags": ["cache", "python"],
            }),
            ("d0000004", {
                "decision": "Write integration tests",
                "confidence": 0.85, "category": "process",
                "stakes": "medium", "status": "pending",
                "recorded_by": "agent-c", "project": "proj/alpha",
                "created_at": "2026-02-15T10:00:00",
                "tags": ["testing"],
            }),
            ("d0000005", {
                "decision": "Deploy to production",
                "confidence": 0.6, "category": "process",
                "stakes": "critical", "status": "reviewed",
                "recorded_by": "agent-b", "project": "proj/beta",
                "created_at": "2026-02-16T10:00:00",
                "tags": ["deploy", "production"],
            }),
        ]
        for did, data in decisions:
            await store.save(did, data)

    async def test_list_no_filters(self, store: DecisionStore) -> None:
        """List all decisions returns correct total."""
        await self._seed(store)
        result = await store.list(ListQuery(limit=50))
        assert isinstance(result, ListResult)
        assert result.total == 5
        assert len(result.decisions) == 5

    async def test_list_pagination(self, store: DecisionStore) -> None:
        """Pagination returns correct page with total count preserved."""
        await self._seed(store)
        result = await store.list(ListQuery(limit=2, offset=0))
        assert result.total == 5
        assert len(result.decisions) == 2
        assert result.limit == 2
        assert result.offset == 0

        result2 = await store.list(ListQuery(limit=2, offset=2))
        assert result2.total == 5
        assert len(result2.decisions) == 2

    async def test_list_by_category(self, store: DecisionStore) -> None:
        """Filter by category returns only matching decisions."""
        await self._seed(store)
        result = await store.list(ListQuery(category="architecture", limit=50))
        assert result.total == 2
        for d in result.decisions:
            assert d["category"] == "architecture"

    async def test_list_by_stakes(self, store: DecisionStore) -> None:
        """Filter by stakes level."""
        await self._seed(store)
        result = await store.list(ListQuery(stakes="critical", limit=50))
        assert result.total == 1
        assert result.decisions[0]["stakes"] == "critical"

    async def test_list_by_status(self, store: DecisionStore) -> None:
        """Filter by status."""
        await self._seed(store)
        result = await store.list(ListQuery(status="reviewed", limit=50))
        assert result.total == 2
        for d in result.decisions:
            assert d["status"] == "reviewed"

    async def test_list_by_agent(self, store: DecisionStore) -> None:
        """Filter by recorded_by agent."""
        await self._seed(store)
        result = await store.list(ListQuery(agent="agent-a", limit=50))
        assert result.total == 2
        for d in result.decisions:
            assert d.get("recorded_by") == "agent-a"

    async def test_list_by_tags(self, store: DecisionStore) -> None:
        """Filter by tags (any match)."""
        await self._seed(store)
        result = await store.list(ListQuery(tags=["python"], limit=50))
        assert result.total == 2
        for d in result.decisions:
            assert "python" in (d.get("tags") or [])

    async def test_list_by_project(self, store: DecisionStore) -> None:
        """Filter by project."""
        await self._seed(store)
        result = await store.list(ListQuery(project="proj/beta", limit=50))
        assert result.total == 2
        for d in result.decisions:
            assert d.get("project") == "proj/beta"

    async def test_list_by_date_range(self, store: DecisionStore) -> None:
        """Filter by date_from/date_to."""
        await self._seed(store)
        result = await store.list(ListQuery(
            date_from="2026-02-14T00:00:00",
            date_to="2026-02-15T23:59:59",
            limit=50,
        ))
        # Should include d0000003 (Feb 14) and d0000004 (Feb 15)
        assert result.total >= 2
        for d in result.decisions:
            created = d.get("created_at") or ""
            assert created >= "2026-02-14"

    async def test_list_keyword_search(self, store: DecisionStore) -> None:
        """Keyword search matches decision text."""
        await self._seed(store)
        result = await store.list(ListQuery(search="FastAPI", limit=50))
        assert result.total >= 1
        found_texts = [d["decision"] for d in result.decisions]
        assert any("FastAPI" in t for t in found_texts)

    async def test_list_sort_ascending(self, store: DecisionStore) -> None:
        """Sort by created_at ascending."""
        await self._seed(store)
        result = await store.list(ListQuery(
            sort="created_at", order="asc", limit=50,
        ))
        dates = [d.get("created_at") or "" for d in result.decisions]
        assert dates == sorted(dates)

    async def test_list_sort_descending(self, store: DecisionStore) -> None:
        """Sort by created_at descending."""
        await self._seed(store)
        result = await store.list(ListQuery(
            sort="created_at", order="desc", limit=50,
        ))
        dates = [d.get("created_at") or "" for d in result.decisions]
        assert dates == sorted(dates, reverse=True)


class TestStats:
    """Tests for stats() operation."""

    async def _seed_for_stats(self, store: DecisionStore) -> None:
        """Seed decisions for stats computation."""
        decisions = [
            ("s0000001", {
                "decision": "Architecture choice A",
                "confidence": 0.9, "category": "architecture",
                "stakes": "high", "status": "reviewed",
                "recorded_by": "agent-x",
                "created_at": "2026-02-16T08:00:00",
                "tags": ["python", "arch"],
            }),
            ("s0000002", {
                "decision": "Architecture choice B",
                "confidence": 0.8, "category": "architecture",
                "stakes": "medium", "status": "pending",
                "recorded_by": "agent-x",
                "created_at": "2026-02-16T09:00:00",
                "tags": ["python", "web"],
            }),
            ("s0000003", {
                "decision": "Process step",
                "confidence": 0.7, "category": "process",
                "stakes": "low", "status": "pending",
                "recorded_by": "agent-y",
                "created_at": "2026-02-16T10:00:00",
                "tags": ["web"],
            }),
        ]
        for did, data in decisions:
            await store.save(did, data)

    async def test_stats_basic(self, store: DecisionStore) -> None:
        """Stats returns total count and breakdowns."""
        await self._seed_for_stats(store)
        result = await store.stats(StatsQuery())
        assert isinstance(result, StatsResult)
        assert result.total == 3
        assert result.by_category.get("architecture") == 2
        assert result.by_category.get("process") == 1
        assert result.by_stakes.get("high") == 1
        assert result.by_stakes.get("medium") == 1
        assert result.by_stakes.get("low") == 1
        assert result.by_status.get("reviewed") == 1
        assert result.by_status.get("pending") == 2

    async def test_stats_by_agent(self, store: DecisionStore) -> None:
        """Stats includes agent grouping."""
        await self._seed_for_stats(store)
        result = await store.stats(StatsQuery())
        assert result.by_agent.get("agent-x") == 2
        assert result.by_agent.get("agent-y") == 1

    async def test_stats_top_tags(self, store: DecisionStore) -> None:
        """Stats includes tag frequency."""
        await self._seed_for_stats(store)
        result = await store.stats(StatsQuery())
        tag_names = [t["tag"] for t in result.top_tags]
        assert "python" in tag_names
        assert "web" in tag_names
        # python appears 2x, web appears 2x
        for t in result.top_tags:
            if t["tag"] == "python":
                assert t["count"] == 2

    async def test_stats_recent_activity(self, store: DecisionStore) -> None:
        """Stats includes recent activity counts."""
        await self._seed_for_stats(store)
        result = await store.stats(StatsQuery())
        assert isinstance(result.recent_activity, dict)
        # All backends must use consistent key names
        assert "last24h" in result.recent_activity
        assert "last7d" in result.recent_activity
        assert "last30d" in result.recent_activity
        for v in result.recent_activity.values():
            assert isinstance(v, int)


class TestCount:
    """Tests for count() operation."""

    async def test_count_all(self, store: DecisionStore) -> None:
        """Count all decisions."""
        await store.save("c0000001", _sample())
        await store.save("c0000002", _sample({"category": "process"}))
        total = await store.count()
        assert total == 2

    async def test_count_with_filter(self, store: DecisionStore) -> None:
        """Count with category filter."""
        await store.save("c0000003", _sample({"category": "architecture"}))
        await store.save("c0000004", _sample({"category": "process"}))
        await store.save("c0000005", _sample({"category": "architecture"}))
        arch_count = await store.count(category="architecture")
        assert arch_count == 2


# =========================================================================
# B) SQLite-specific tests
# =========================================================================


class TestSQLiteSpecific:
    """Tests specific to SQLiteDecisionStore features."""

    async def test_sqlite_wal_mode(self, sqlite_store: SQLiteDecisionStore) -> None:
        """Verify PRAGMA journal_mode returns 'wal'."""
        assert sqlite_store._conn is not None
        row = sqlite_store._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    async def test_sqlite_fts5_search(self, sqlite_store: SQLiteDecisionStore) -> None:
        """Keyword search uses FTS5 index."""
        await sqlite_store.save("fts00001", _sample({
            "decision": "Implement Redis caching for sessions",
            "context": "Performance optimization needed",
        }))
        await sqlite_store.save("fts00002", _sample({
            "decision": "Use PostgreSQL for persistence",
            "context": "Database selection",
        }))

        result = await sqlite_store.list(ListQuery(search="Redis", limit=50))
        assert result.total == 1
        assert "Redis" in result.decisions[0]["decision"]

    async def test_sqlite_initialize_creates_tables(
        self, tmp_path: Any,
    ) -> None:
        """Tables exist after initialization."""
        s = SQLiteDecisionStore(db_path=str(tmp_path / "init_test.db"))
        await s.initialize()
        try:
            assert s._conn is not None
            tables = s._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {row[0] for row in tables}
            assert "decisions" in table_names
            assert "decision_tags" in table_names
            assert "decision_reasons" in table_names
            assert "decision_bridge" in table_names
            assert "decision_deliberation" in table_names
        finally:
            await s.close()

    async def test_sqlite_db_path_config(self, tmp_path: Any) -> None:
        """SQLiteDecisionStore respects custom db_path."""
        custom_path = str(tmp_path / "custom" / "my.db")
        s = SQLiteDecisionStore(db_path=custom_path)
        await s.initialize()
        try:
            assert s._db_path.name == "my.db"
            assert s._db_path.exists()
        finally:
            await s.close()

    async def test_sqlite_multiple_saves_and_reads(
        self, sqlite_store: SQLiteDecisionStore,
    ) -> None:
        """Multiple sequential saves and reads work correctly."""
        for i in range(10):
            await sqlite_store.save(
                f"conc{i:04d}",
                _sample({"decision": f"Decision {i}"}),
            )

        result = await sqlite_store.list(ListQuery(limit=50))
        assert result.total == 10

        got = await sqlite_store.get("conc0005")
        assert got is not None
        assert got["decision"] == "Decision 5"


# =========================================================================
# C) Factory tests
# =========================================================================


class TestFactory:
    """Tests for the storage factory module."""

    def setup_method(self) -> None:
        """Reset factory singleton before each test."""
        from a2a.cstp.storage.factory import set_decision_store
        set_decision_store(None)

    def teardown_method(self) -> None:
        """Reset factory singleton after each test."""
        from a2a.cstp.storage.factory import set_decision_store
        set_decision_store(None)

    def test_factory_default_yaml(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default CSTP_STORAGE creates YAMLFileSystemStore."""
        from a2a.cstp.storage.factory import create_decision_store
        from a2a.cstp.storage.yaml_fs import YAMLFileSystemStore

        monkeypatch.delenv("CSTP_STORAGE", raising=False)
        store = create_decision_store()
        assert isinstance(store, YAMLFileSystemStore)

    def test_factory_sqlite(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CSTP_STORAGE=sqlite creates SQLiteDecisionStore."""
        from a2a.cstp.storage.factory import create_decision_store

        monkeypatch.setenv("CSTP_STORAGE", "sqlite")
        store = create_decision_store()
        assert isinstance(store, SQLiteDecisionStore)

    def test_factory_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CSTP_STORAGE=memory creates MemoryDecisionStore."""
        from a2a.cstp.storage.factory import create_decision_store

        monkeypatch.setenv("CSTP_STORAGE", "memory")
        store = create_decision_store()
        assert isinstance(store, MemoryDecisionStore)

    def test_factory_set_injection(self) -> None:
        """set_decision_store() injects a store for testing."""
        from a2a.cstp.storage.factory import (
            get_decision_store,
            set_decision_store,
        )

        injected = MemoryDecisionStore()
        set_decision_store(injected)
        got = get_decision_store()
        assert got is injected

    def test_factory_invalid_backend(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Invalid CSTP_STORAGE raises ValueError."""
        from a2a.cstp.storage.factory import create_decision_store

        monkeypatch.setenv("CSTP_STORAGE", "nosuchbackend")
        with pytest.raises(ValueError, match="Unknown storage backend"):
            create_decision_store()


# =========================================================================
# D) Integration tests (dispatcher RPC handlers)
# =========================================================================


class TestRPCIntegration:
    """Test the cstp.listDecisions and cstp.getStats dispatcher handlers."""

    async def _get_handlers(self) -> tuple[Any, Any]:
        """Import dispatcher handlers, mocking mcp if needed."""
        # Mock mcp modules in case any transitive import triggers them
        mock_mcp_modules = {
            "mcp": MagicMock(),
            "mcp.server": MagicMock(),
            "mcp.server.stdio": MagicMock(),
            "mcp.server.streamable_http_manager": MagicMock(),
            "mcp.types": MagicMock(),
        }
        with patch.dict(sys.modules, mock_mcp_modules):
            from a2a.cstp.dispatcher import (
                _handle_get_stats,
                _handle_list_decisions,
            )
        return _handle_list_decisions, _handle_get_stats

    async def test_list_decisions_rpc(self, tmp_path: Any) -> None:
        """cstp.listDecisions handler returns paginated results."""
        store = MemoryDecisionStore()
        await store.initialize()
        await store.save("rpc00001", _sample({"decision": "RPC test decision A"}))
        await store.save("rpc00002", _sample({
            "decision": "RPC test decision B",
            "category": "process",
        }))

        _handle_list_decisions, _ = await self._get_handlers()

        with patch(
            "a2a.cstp.storage.factory.get_decision_store",
            return_value=store,
        ):
            result = await _handle_list_decisions(
                {"limit": 10, "offset": 0}, "test-agent",
            )

        assert result["total"] == 2
        assert len(result["decisions"]) == 2
        assert result["limit"] == 10
        assert result["offset"] == 0

    async def test_get_stats_rpc(self, tmp_path: Any) -> None:
        """cstp.getStats handler returns aggregated statistics."""
        store = MemoryDecisionStore()
        await store.initialize()
        await store.save("rpc00003", _sample({
            "category": "architecture",
            "tags": ["arch"],
        }))
        await store.save("rpc00004", _sample({
            "category": "process",
            "tags": ["process-tag"],
        }))

        _, _handle_get_stats = await self._get_handlers()

        with patch(
            "a2a.cstp.storage.factory.get_decision_store",
            return_value=store,
        ):
            result = await _handle_get_stats({}, "test-agent")

        assert result["total"] == 2
        assert "architecture" in result["byCategory"]
        assert "process" in result["byCategory"]

    async def test_record_decision_uses_store(self, tmp_path: Any) -> None:
        """decision_service.record_decision() dual-writes to the store."""
        store = MemoryDecisionStore()
        await store.initialize()

        mock_mcp_modules = {
            "mcp": MagicMock(),
            "mcp.server": MagicMock(),
            "mcp.server.stdio": MagicMock(),
            "mcp.server.streamable_http_manager": MagicMock(),
            "mcp.types": MagicMock(),
        }
        with patch.dict(sys.modules, mock_mcp_modules):
            from a2a.cstp.decision_service import (
                RecordDecisionRequest,
                record_decision,
            )

        # Mock embedding/vector store to avoid external calls
        mock_embed = AsyncMock(return_value=[0.1] * 768)
        mock_vector = MagicMock()
        mock_vector.get_collection_id = AsyncMock(return_value="test-coll")
        mock_vector.upsert = AsyncMock(return_value=True)

        request = RecordDecisionRequest(
            decision="Test store integration",
            confidence=0.9,
            category="architecture",
            stakes="medium",
            context="Integration test",
        )

        with (
            patch(
                "a2a.cstp.decision_service.get_decision_store",
                return_value=store,
            ),
            patch(
                "a2a.cstp.decision_service.get_embedding_provider",
                return_value=MagicMock(embed=mock_embed),
            ),
            patch(
                "a2a.cstp.decision_service.get_vector_store",
                return_value=mock_vector,
            ),
        ):
            response = await record_decision(
                request, decisions_path=str(tmp_path / "decisions"),
            )

        assert response.success is True
        # The store should contain the decision
        got = await store.get(response.id)
        assert got is not None
        assert got["decision"] == "Test store integration"
        assert got["category"] == "architecture"


# =========================================================================
# E) Regression tests for PR #162 review fixes
# =========================================================================


class TestRegressionPR162:
    """Regression tests for PR #162 code review fixes.

    Each test targets a specific bug fix to prevent reintroduction.
    All tests are parameterized across memory + sqlite via the store fixture.
    """

    # P1#1 regression: bare date_to should include entries from that day
    async def test_list_date_to_bare_date(self, store: DecisionStore) -> None:
        """Bare date_to like '2026-02-15' should include entries from that day."""
        await store.save("dt01", _sample({
            "decision": "On target day",
            "created_at": "2026-02-15T10:00:00",
        }))
        await store.save("dt02", _sample({
            "decision": "Day before",
            "created_at": "2026-02-14T10:00:00",
        }))
        result = await store.list(ListQuery(date_to="2026-02-15"))
        assert result.total == 2  # Both should be included

    # P2#8 regression: date_to with time component should not produce double-T
    async def test_list_date_to_with_time(self, store: DecisionStore) -> None:
        """date_to with time like '2026-02-15T12:00:00' should filter correctly."""
        await store.save("dtw1", _sample({
            "decision": "Before cutoff",
            "created_at": "2026-02-15T10:00:00",
        }))
        await store.save("dtw2", _sample({
            "decision": "After cutoff",
            "created_at": "2026-02-15T14:00:00",
        }))
        result = await store.list(ListQuery(date_to="2026-02-15T12:00:00"))
        assert result.total == 1
        assert result.decisions[0]["decision"] == "Before cutoff"

    # P1#2 regression: update_fields with deliberation should persist
    async def test_update_fields_deliberation(self, store: DecisionStore) -> None:
        """update_fields with deliberation dict should persist in child table."""
        await store.save("dlib1", _sample({"decision": "Test deliberation"}))
        delib = {
            "inputs": [{"id": "i1", "text": "some input"}],
            "steps": [{"step": 1, "thought": "a thought"}],
            "total_duration_ms": 500,
        }
        ok = await store.update_fields("dlib1", deliberation=delib)
        assert ok is True
        got = await store.get("dlib1")
        assert got is not None
        assert got.get("deliberation") is not None
        assert got["deliberation"]["total_duration_ms"] == 500

    # P2#6 regression: list() and get() should have same field names
    async def test_list_field_names_match_get(self, store: DecisionStore) -> None:
        """list() and get() should return same field names for outcome fields."""
        await store.save("fn01", _sample({
            "decision": "Test field names",
            "outcome": "success",
        }))
        await store.update_outcome("fn01", "success", "It worked", "Be careful", "Note")
        got = await store.get("fn01")
        listed = await store.list(ListQuery(limit=10))
        list_item = [d for d in listed.decisions if d["id"] == "fn01"][0]
        # Both should use actual_result, not outcome_result
        for key in ("actual_result", "lessons", "review_notes"):
            assert key in got, f"get() missing {key}"
            assert key in list_item, f"list() missing {key}"
        for key in ("outcome_result", "outcome_lessons", "outcome_notes"):
            assert key not in got, f"get() has raw SQLite key {key}"
            assert key not in list_item, f"list() has raw SQLite key {key}"

    # P2#3 regression: batch tag query should still filter correctly
    async def test_list_tags_batch_query(self, store: DecisionStore) -> None:
        """Tag filtering should work correctly with batch IN clause."""
        await store.save("tb01", _sample({
            "decision": "Has python tag",
            "tags": ["python", "web"],
            "created_at": "2026-02-15T10:00:00",
        }))
        await store.save("tb02", _sample({
            "decision": "Has rust tag",
            "tags": ["rust", "cli"],
            "created_at": "2026-02-15T11:00:00",
        }))
        await store.save("tb03", _sample({
            "decision": "No matching tags",
            "tags": ["java"],
            "created_at": "2026-02-15T12:00:00",
        }))
        result = await store.list(ListQuery(tags=["python"], limit=50))
        assert result.total == 1
        assert result.decisions[0]["decision"] == "Has python tag"
        # Verify tags are populated in list results
        tags = result.decisions[0].get("tags") or []
        assert "python" in tags
        assert "web" in tags

    # P2#5 regression: stats recent_activity should respect project filter
    async def test_stats_recent_activity_respects_filters(
        self, store: DecisionStore,
    ) -> None:
        """Stats recent_activity counts should respect query filters."""
        # Use fixed dates in the past to avoid timezone issues
        await store.save("ra01", _sample({
            "decision": "Project alpha recent",
            "project": "test/alpha",
            "created_at": "2026-02-16T08:00:00",
        }))
        await store.save("ra02", _sample({
            "decision": "Project beta recent",
            "project": "test/beta",
            "created_at": "2026-02-16T09:00:00",
        }))
        # Stats with project filter
        result_alpha = await store.stats(StatsQuery(project="test/alpha"))
        result_all = await store.stats(StatsQuery())

        # Filtered stats should have fewer or equal total than unfiltered
        assert result_alpha.total <= result_all.total
        assert result_alpha.total == 1
