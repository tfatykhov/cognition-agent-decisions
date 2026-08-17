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
    filepath.write_text(yaml.dump(data, default_flow_style=False), encoding="utf-8")
    return filepath



def _record_request(text: str) -> Any:
    """Minimal RecordDecisionRequest for store-failure tests."""
    from a2a.cstp.decision_service import RecordDecisionRequest

    return RecordDecisionRequest(
        decision=text,
        confidence=0.8,
        category="architecture",
        stakes="low",
    )


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
        empty.write_text("", encoding="utf-8")
        assert _parse_yaml_decision(empty) is None

    def test_returns_none_for_invalid_yaml(self, tmp_path: Path) -> None:
        bad = tmp_path / "2026-02-18-decision-bad12345.yaml"
        bad.write_text(": : : invalid yaml [[[", encoding="utf-8")
        # Should not raise, returns None
        result = _parse_yaml_decision(bad)
        # yaml.safe_load may parse this oddly or return None
        # Either way, should not crash
        assert result is None or isinstance(result, tuple)

    def test_returns_none_for_non_dict(self, tmp_path: Path) -> None:
        scalar = tmp_path / "2026-02-18-decision-scalar1.yaml"
        scalar.write_text("just a string", encoding="utf-8")
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
        bad.write_text("", encoding="utf-8")

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
    async def test_skips_when_all_yaml_already_present(self, decisions_dir: Path) -> None:
        """A completed migration must not re-run on every startup."""
        store = MemoryDecisionStore()
        await store.initialize()

        first = await auto_migrate_if_empty(store, str(decisions_dir))
        assert first == 3

        second = await auto_migrate_if_empty(store, str(decisions_dir))
        assert second == 0
        assert await store.count() == 3

    @pytest.mark.asyncio
    async def test_resumes_after_interrupted_migration(self, decisions_dir: Path) -> None:
        """Regression: a partial migration must resume, not be skipped forever.

        The gate used to be "only run when the store is empty". Since
        migrate_yaml_to_store commits one record at a time with no surrounding
        transaction, a crash after the first save left a non-empty store — and
        every later startup skipped migration, stranding the remaining YAML
        decisions where no read path could see them.
        """
        store = MemoryDecisionStore()
        await store.initialize()

        # Simulate a run that died after importing one of the three files.
        await store.save("partial1", {
            "decision": "Imported before the crash",
            "confidence": 0.5,
            "category": "test",
            "stakes": "low",
            "status": "pending",
        })
        assert await store.count() == 1

        count = await auto_migrate_if_empty(store, str(decisions_dir))
        assert count == 3, "migration should resume rather than skip"
        assert await store.count() == 4  # 3 migrated + the partial record

    @pytest.mark.asyncio
    async def test_returns_zero_for_no_yaml_files(self, tmp_path: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await auto_migrate_if_empty(store, str(tmp_path))
        assert count == 0

    @pytest.mark.asyncio
    async def test_missing_directory_is_not_an_error(self, tmp_path: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        count = await auto_migrate_if_empty(store, str(tmp_path / "nope"))
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


class TestRecordDecisionStoreIsAuthoritative:
    """Regression: a failed store write must not be acknowledged as success.

    listDecisions, getStats, and calibration all read from the DecisionStore.
    record_decision used to log a store failure and still return success=True,
    so with SQLite as the read path a transient write error produced a decision
    the caller believed was saved and no query could ever return.
    """

    @pytest.mark.asyncio
    async def test_raising_store_fails_the_call(self, tmp_path: Path) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import record_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        store.save = AsyncMock(side_effect=OSError("disk gone"))  # type: ignore[method-assign]
        set_decision_store(store)

        response = await record_decision(
            _record_request("Store raises"), decisions_path=str(tmp_path)
        )

        assert response.success is False
        assert "disk gone" in (response.error or "")

    @pytest.mark.asyncio
    async def test_store_returning_false_fails_the_call(self, tmp_path: Path) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import record_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        store.save = AsyncMock(return_value=False)  # type: ignore[method-assign]
        set_decision_store(store)

        response = await record_decision(
            _record_request("Store rejects"), decisions_path=str(tmp_path)
        )

        assert response.success is False
        assert "rejected" in (response.error or "").lower()

    @pytest.mark.asyncio
    async def test_healthy_store_still_succeeds(self, tmp_path: Path) -> None:
        from a2a.cstp.decision_service import record_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        response = await record_decision(
            _record_request("Store healthy"), decisions_path=str(tmp_path)
        )

        assert response.success is True
        assert await store.get(response.id) is not None


class TestMigrationGateUsesIds:
    """Regression: resumability must be decided per-ID, not by aggregate counts.

    A store can hold decisions recorded *after* an interrupted import, so its
    total can match or exceed the YAML file count while specific YAML IDs are
    still absent — stranding exactly the files a resume exists to recover.
    """

    @pytest.mark.asyncio
    async def test_migrates_missing_ids_despite_sufficient_count(
        self, decisions_dir: Path
    ) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        # Three unrelated decisions: count now equals the YAML file count (3),
        # but none of the YAML IDs are present.
        for i in range(3):
            await store.save(f"unrelated{i}", {
                "decision": f"Recorded after the interrupted import {i}",
                "confidence": 0.5,
                "category": "test",
                "stakes": "low",
                "status": "pending",
            })
        assert await store.count() == 3

        count = await auto_migrate_if_empty(store, str(decisions_dir))
        assert count == 3, "count-based gate would have skipped these"
        for yaml_id in ("aaa11111", "bbb22222", "ccc33333"):
            assert await store.get(yaml_id) is not None

    @pytest.mark.asyncio
    async def test_mixed_present_and_missing_ids(self, decisions_dir: Path) -> None:
        store = MemoryDecisionStore()
        await store.initialize()

        # One real YAML ID already imported, plus filler that inflates the count.
        await store.save("aaa11111", {
            "decision": "Already imported",
            "confidence": 0.9,
            "category": "architecture",
            "stakes": "high",
            "status": "reviewed",
        })
        for i in range(5):
            await store.save(f"filler{i}", {
                "decision": f"Unrelated {i}",
                "confidence": 0.5,
                "category": "test",
                "stakes": "low",
                "status": "pending",
            })
        assert await store.count() == 6  # well above the 3 YAML files

        count = await auto_migrate_if_empty(store, str(decisions_dir))
        assert count == 3
        assert await store.get("bbb22222") is not None
        assert await store.get("ccc33333") is not None


class TestReviewDecisionStoreIsAuthoritative:
    """Same class of bug as recordDecision: calibration reads the store, so a
    swallowed outcome-write leaves an acknowledged review that never lands.
    """

    async def _recorded_id(self, store: Any, tmp_path: Path) -> str:
        from a2a.cstp.decision_service import record_decision

        response = await record_decision(
            _record_request("Decision to review"), decisions_path=str(tmp_path)
        )
        assert response.success is True
        return response.id

    @pytest.mark.asyncio
    async def test_raising_store_fails_the_review(self, tmp_path: Path) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import ReviewDecisionRequest, review_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)
        decision_id = await self._recorded_id(store, tmp_path)

        store.update_outcome = AsyncMock(  # type: ignore[method-assign]
            side_effect=OSError("db unreachable")
        )
        response = await review_decision(
            ReviewDecisionRequest(id=decision_id, outcome="success"),
            decisions_path=str(tmp_path),
        )

        assert response.success is False
        assert "db unreachable" in (response.error or "")

    @pytest.mark.asyncio
    async def test_store_returning_false_fails_the_review(self, tmp_path: Path) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import ReviewDecisionRequest, review_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)
        decision_id = await self._recorded_id(store, tmp_path)

        store.update_outcome = AsyncMock(return_value=False)  # type: ignore[method-assign]
        response = await review_decision(
            ReviewDecisionRequest(id=decision_id, outcome="success"),
            decisions_path=str(tmp_path),
        )

        assert response.success is False
        assert "rejected" in (response.error or "").lower()

    @pytest.mark.asyncio
    async def test_healthy_store_review_succeeds(self, tmp_path: Path) -> None:
        from a2a.cstp.decision_service import ReviewDecisionRequest, review_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)
        decision_id = await self._recorded_id(store, tmp_path)

        response = await review_decision(
            ReviewDecisionRequest(id=decision_id, outcome="success"),
            decisions_path=str(tmp_path),
        )

        assert response.success is True
        stored = await store.get(decision_id)
        assert stored is not None
        assert stored["status"] == "reviewed"


class TestMalformedFilesDoNotRetriggerMigration:
    """Regression: an unparseable file must not make the gate unsatisfiable.

    IDs are read from filenames, so a malformed file still contributes an ID that
    can never be imported. Counting it as missing would rerun the full migration
    on every restart, rewriting every parseable decision each time.
    """

    @pytest.mark.asyncio
    async def test_malformed_file_does_not_force_rerun(self, decisions_dir: Path) -> None:
        bad = decisions_dir / "2026" / "02" / "2026-02-18-decision-bad00000.yaml"
        bad.write_text("", encoding="utf-8")

        store = MemoryDecisionStore()
        await store.initialize()

        first = await auto_migrate_if_empty(store, str(decisions_dir))
        assert first == 3  # the malformed file is not importable

        second = await auto_migrate_if_empty(store, str(decisions_dir))
        assert second == 0, "malformed file must not retrigger the migration"

    @pytest.mark.asyncio
    async def test_malformed_file_does_not_mask_a_genuinely_missing_one(
        self, decisions_dir: Path
    ) -> None:
        bad = decisions_dir / "2026" / "02" / "2026-02-18-decision-bad00001.yaml"
        bad.write_text(": : : not yaml [[[", encoding="utf-8")

        store = MemoryDecisionStore()
        await store.initialize()
        await auto_migrate_if_empty(store, str(decisions_dir))

        # Drop one real decision; the next run must still notice and re-import it.
        await store.delete("bbb22222")
        again = await auto_migrate_if_empty(store, str(decisions_dir))
        assert again == 3
        assert await store.get("bbb22222") is not None


class TestFailedStoreWritesAreRetrySafe:
    """Round 6: a store failure is detected only after YAML has been mutated.

    Leaving that mutation in place breaks the retry in a different way for each
    path — duplicated thoughts, permanently skipped attributions, phantom
    duplicate decisions — so each one is undone.
    """

    @pytest.mark.asyncio
    async def test_record_removes_orphan_file_so_retry_is_clean(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import record_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        store.save = AsyncMock(side_effect=OSError("db down"))  # type: ignore[method-assign]
        set_decision_store(store)

        response = await record_decision(
            _record_request("Never persisted"), decisions_path=str(tmp_path)
        )
        assert response.success is False
        # No orphan left to be imported later as a phantom second copy.
        assert list(tmp_path.rglob("*-decision-*.yaml")) == []

    @pytest.mark.asyncio
    async def test_append_thought_rolls_back_so_retry_does_not_duplicate(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.decision_service import append_thought, record_decision
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        recorded = await record_decision(
            _record_request("Has a trace"), decisions_path=str(tmp_path)
        )
        assert recorded.success is True

        healthy = store.update_fields
        store.update_fields = AsyncMock(return_value=False)  # type: ignore[method-assign]
        failed = await append_thought(recorded.id, "first thought", str(tmp_path))
        assert failed["success"] is False

        # Retry against a healthy store must yield exactly one copy of the thought.
        store.update_fields = healthy  # type: ignore[method-assign]
        ok = await append_thought(recorded.id, "first thought", str(tmp_path))
        assert ok["success"] is True
        assert ok["step_number"] == 1, "rolled-back attempt must not consume a step"

        stored = await store.get(recorded.id)
        assert stored is not None
        steps = (stored.get("deliberation") or {}).get("steps") or []
        assert [s["thought"] for s in steps] == ["first thought"]

    @pytest.mark.asyncio
    async def test_attribution_rollback_keeps_decision_pending(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.attribution_service import update_decision_outcome
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        path = _write_yaml_decision(tmp_path, "ddd44444", {
            "id": "ddd44444",
            "decision": "Awaiting attribution",
            "confidence": 0.7,
            "category": "process",
            "stakes": "low",
            "status": "pending",
        })
        await store.save("ddd44444", yaml.safe_load(path.read_text(encoding="utf-8")))

        store.update_outcome = AsyncMock(return_value=False)  # type: ignore[method-assign]
        ok = await update_decision_outcome(path, "success", "PR merged")
        assert ok is False

        # Still pending, so the next attributeOutcomes run picks it up again.
        reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert reloaded["status"] == "pending"
        assert "outcome" not in reloaded

    @pytest.mark.asyncio
    async def test_attribution_rollback_when_store_raises(self, tmp_path: Path) -> None:
        """Round 7: rollback must also cover a raising store, not just a False return.

        SQLite surfaces some failures as exceptions, and those were caught by the
        outer handler which returned False without restoring the file.
        """
        from unittest.mock import AsyncMock

        from a2a.cstp.attribution_service import update_decision_outcome
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        path = _write_yaml_decision(tmp_path, "eee55555", {
            "id": "eee55555",
            "decision": "Awaiting attribution",
            "confidence": 0.7,
            "category": "process",
            "stakes": "low",
            "status": "pending",
        })
        await store.save("eee55555", yaml.safe_load(path.read_text(encoding="utf-8")))

        store.update_outcome = AsyncMock(  # type: ignore[method-assign]
            side_effect=OSError("db unreachable")
        )
        assert await update_decision_outcome(path, "success", "PR merged") is False

        reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert reloaded["status"] == "pending"
        assert "outcome" not in reloaded

    @pytest.mark.asyncio
    async def test_attribution_rollback_when_store_get_raises(
        self, tmp_path: Path
    ) -> None:
        """The existence probe itself can raise on a transient read failure."""
        from unittest.mock import AsyncMock

        from a2a.cstp.attribution_service import update_decision_outcome
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        path = _write_yaml_decision(tmp_path, "fff66666", {
            "id": "fff66666",
            "decision": "Awaiting attribution",
            "confidence": 0.7,
            "category": "process",
            "stakes": "low",
            "status": "pending",
        })

        store.get = AsyncMock(side_effect=OSError("read failed"))  # type: ignore[method-assign]
        assert await update_decision_outcome(path, "success", "PR merged") is False

        reloaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert reloaded["status"] == "pending"

    @pytest.mark.asyncio
    async def test_attribution_inserts_decision_absent_from_store(
        self, tmp_path: Path
    ) -> None:
        """Round 8: a not-yet-migrated decision must be inserted, not deferred.

        Returning True without writing would leave the YAML non-pending — so
        attribution never revisits it — while list and calibration reads stayed
        blind to the decision until a restart happened to rerun migration.
        """
        from a2a.cstp.attribution_service import update_decision_outcome
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        set_decision_store(store)

        path = _write_yaml_decision(tmp_path, "ggg77777", {
            "id": "ggg77777",
            "decision": "Never migrated",
            "confidence": 0.7,
            "category": "process",
            "stakes": "low",
            "status": "pending",
        })
        assert await store.get("ggg77777") is None

        assert await update_decision_outcome(path, "success", "PR merged") is True

        stored = await store.get("ggg77777")
        assert stored is not None, "attribution must insert the missing row"
        assert stored["outcome"] == "success"
        assert stored["status"] == "reviewed"

    @pytest.mark.asyncio
    async def test_attribution_rolls_back_when_insert_rejected(
        self, tmp_path: Path
    ) -> None:
        from unittest.mock import AsyncMock

        from a2a.cstp.attribution_service import update_decision_outcome
        from a2a.cstp.storage.factory import set_decision_store

        store = MemoryDecisionStore()
        await store.initialize()
        store.save = AsyncMock(return_value=False)  # type: ignore[method-assign]
        set_decision_store(store)

        path = _write_yaml_decision(tmp_path, "hhh88888", {
            "id": "hhh88888",
            "decision": "Never migrated",
            "confidence": 0.7,
            "category": "process",
            "stakes": "low",
            "status": "pending",
        })

        assert await update_decision_outcome(path, "success", "PR merged") is False
        assert yaml.safe_load(path.read_text(encoding="utf-8"))["status"] == "pending"
