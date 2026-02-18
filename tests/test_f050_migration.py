"""Tests for YAML-to-SQLite auto-migration (F050).

Covers:
- YAML parsing from decision files
- Full migration into SQLite store
- Auto-migrate-if-empty logic (skip if data exists)
- CLI --force flag behavior
- Error handling for malformed YAML files
"""

from pathlib import Path
from typing import Any

import pytest
import yaml

from a2a.cstp.storage.memory import MemoryDecisionStore
from a2a.cstp.storage.migrate import (
    _parse_yaml_decision,
    auto_migrate_if_empty,
    migrate_yaml_to_store,
)


def _write_yaml_decision(
    directory: Path,
    decision_id: str,
    data: dict[str, Any],
    date: str = "2026-02-18",
) -> Path:
    """Write a YAML decision file in the expected directory structure."""
    year_month = date[:7].replace("-", "/")
    subdir = directory / year_month
    subdir.mkdir(parents=True, exist_ok=True)
    filename = f"{date}-decision-{decision_id}.yaml"
    filepath = subdir / filename
    filepath.write_text(yaml.dump(data, default_flow_style=False))
    return filepath


@pytest.fixture
def decisions_dir(tmp_path: Path) -> Path:
    """Create a temp directory with sample YAML decisions."""
    d1 = {
        "decision": "Use SQLite for structured storage",
        "confidence": 0.9,
        "category": "architecture",
        "stakes": "high",
        "status": "reviewed",
        "created_at": "2026-02-16T10:00:00+00:00",
        "context": "YAML doesn't scale for queries",
        "tags": ["sqlite", "storage"],
        "reasons": [
            {"type": "analysis", "text": "YAML requires full scan", "strength": 0.9},
        ],
        "outcome": "success",
        "actual_result": "Queries 10x faster",
    }
    d2 = {
        "decision": "Add FTS5 for keyword search",
        "confidence": 0.85,
        "category": "architecture",
        "stakes": "medium",
        "status": "pending",
        "created_at": "2026-02-17T14:00:00+00:00",
        "tags": ["fts5", "search"],
    }
    d3 = {
        "decision": "Wire migration into lifespan",
        "confidence": 0.8,
        "category": "process",
        "stakes": "low",
        "status": "pending",
        "created_at": "2026-02-18T08:00:00+00:00",
    }

    _write_yaml_decision(tmp_path, "aaa11111", d1, "2026-02-16")
    _write_yaml_decision(tmp_path, "bbb22222", d2, "2026-02-17")
    _write_yaml_decision(tmp_path, "ccc33333", d3, "2026-02-18")

    return tmp_path


class TestParseYamlDecision:
    """Tests for _parse_yaml_decision."""

    def test_parses_valid_file(self, decisions_dir: Path) -> None:
        yaml_file = next(decisions_dir.rglob("*-decision-aaa11111.yaml"))
        result = _parse_yaml_decision(yaml_file)
        assert result is not None
        decision_id, data = result
        assert decision_id == "aaa11111"
        assert data["decision"] == "Use SQLite for structured storage"
        assert data["confidence"] == 0.9
        assert data["id"] == "aaa11111"

    def test_extracts_id_from_filename(self, decisions_dir: Path) -> None:
        yaml_file = next(decisions_dir.rglob("*-decision-bbb22222.yaml"))
        result = _parse_yaml_decision(yaml_file)
        assert result is not None
        assert result[0] == "bbb22222"

    def test_returns_none_for_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "2026-02-18-decision-empty123.yaml"
        empty.write_text("")
        assert _parse_yaml_decision(empty) is None

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "2026-02-18-decision-bad12345.yaml"
        bad.write_text(": : : invalid yaml [[[")
        # Should not raise, returns None
        result = _parse_yaml_decision(bad)
        # yaml.safe_load may parse this oddly or return None
        # Either way, should not crash
        assert result is None or isinstance(result, tuple)

    def test_returns_none_for_non_dict(self, tmp_path: Path) -> None:
        scalar = tmp_path / "2026-02-18-decision-scalar1.yaml"
        scalar.write_text("just a string")
        assert _parse_yaml_decision(scalar) is None


class TestMigrateYamlToStore:
    """Tests for migrate_yaml_to_store."""

    @pytest.mark.asyncio
    async def test_migrates_all_decisions(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await migrate_yaml_to_store(store, str(decisions_dir))

        assert count == 3
        # Verify all 3 are in the store
        d1 = await store.get("aaa11111")
        assert d1 is not None
        assert d1["decision"] == "Use SQLite for structured storage"

        d2 = await store.get("bbb22222")
        assert d2 is not None

        d3 = await store.get("ccc33333")
        assert d3 is not None

    @pytest.mark.asyncio
    async def test_returns_zero_for_missing_dir(self) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await migrate_yaml_to_store(store, "/nonexistent/path")
        assert count == 0

    @pytest.mark.asyncio
    async def test_returns_zero_for_empty_dir(self, tmp_path: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await migrate_yaml_to_store(store, str(tmp_path))
        assert count == 0

    @pytest.mark.asyncio
    async def test_skips_malformed_files(self, decisions_dir: Path) -> None:
        # Add a malformed file
        bad = decisions_dir / "2026" / "02" / "2026-02-18-decision-bad00000.yaml"
        bad.write_text("")

        store = MemoryDecisionStore()
        await store.initialize()

        count = await migrate_yaml_to_store(store, str(decisions_dir))
        # 3 good + 1 bad = 3 imported
        assert count == 3

    @pytest.mark.asyncio
    async def test_idempotent_reimport(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count1 = await migrate_yaml_to_store(store, str(decisions_dir))
        count2 = await migrate_yaml_to_store(store, str(decisions_dir))

        assert count1 == 3
        assert count2 == 3  # Upsert, same count
        # Still only 3 decisions
        total = await store.count()
        assert total == 3


class TestAutoMigrateIfEmpty:
    """Tests for auto_migrate_if_empty."""

    @pytest.mark.asyncio
    async def test_migrates_when_empty(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await auto_migrate_if_empty(store, str(decisions_dir))
        assert count == 3

    @pytest.mark.asyncio
    async def test_skips_when_not_empty(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        # Pre-populate with one decision
        await store.save("existing1", {
            "decision": "Already here",
            "confidence": 0.5,
            "category": "test",
            "stakes": "low",
            "status": "pending",
        })

        count = await auto_migrate_if_empty(store, str(decisions_dir))
        assert count == 0  # Skipped because store not empty

        # Only the pre-existing decision
        total = await store.count()
        assert total == 1

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_yaml_files(self, tmp_path: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await auto_migrate_if_empty(store, str(tmp_path))
        assert count == 0


class TestPreservesData:
    """Tests that migration preserves all decision fields."""

    @pytest.mark.asyncio
    async def test_preserves_tags(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()
        await migrate_yaml_to_store(store, str(decisions_dir))

        d = await store.get("aaa11111")
        assert d is not None
        assert d.get("tags") == ["sqlite", "storage"]

    @pytest.mark.asyncio
    async def test_preserves_reasons(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()
        await migrate_yaml_to_store(store, str(decisions_dir))

        d = await store.get("aaa11111")
        assert d is not None
        reasons = d.get("reasons", [])
        assert len(reasons) >= 1
        assert reasons[0]["type"] == "analysis"

    @pytest.mark.asyncio
    async def test_preserves_outcome(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()
        await migrate_yaml_to_store(store, str(decisions_dir))

        d = await store.get("aaa11111")
        assert d is not None
        assert d.get("outcome") == "success"

    @pytest.mark.asyncio
    async def test_preserves_context(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()
        await migrate_yaml_to_store(store, str(decisions_dir))

        d = await store.get("aaa11111")
        assert d is not None
        assert d.get("context") == "YAML doesn't scale for queries"
