"""Tests for F041: Memory Compaction service + CSTP dispatcher integration."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from a2a.cstp.compaction_service import (
    OUTCOME_CONFIDENCE,
    build_wisdom,
    compact_decision,
    determine_compaction_level,
    get_compacted_decisions,
    get_wisdom,
    run_compaction,
    set_preserve,
)
from a2a.cstp.dispatcher import CstpDispatcher, register_methods
from a2a.cstp.models import (
    COMPACTION_LEVELS,
    COMPACTION_THRESHOLDS,
    CompactedDecision,
    CompactLevelCount,
    CompactRequest,
    CompactResponse,
    GetCompactedRequest,
    GetCompactedResponse,
    GetWisdomRequest,
    GetWisdomResponse,
    SetPreserveRequest,
    SetPreserveResponse,
    WisdomEntry,
    WisdomPrinciple,
)
from a2a.models.jsonrpc import JsonRpcRequest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime(2026, 2, 15, 12, 0, 0, tzinfo=UTC)


def _make_decision(
    *,
    decision_id: str = "aabbccdd",
    age_days: int = 0,
    status: str = "reviewed",
    outcome: str = "success",
    category: str = "architecture",
    confidence: float = 0.9,
    stakes: str = "medium",
    preserve: bool = False,
    pattern: str | None = None,
    context: str | None = "some context",
    reasons: list[dict[str, Any]] | None = None,
    tags: list[str] | None = None,
    bridge: dict[str, Any] | None = None,
    deliberation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Helper to create a decision dict at a specific age."""
    decision_date = NOW - timedelta(days=age_days)
    d: dict[str, Any] = {
        "id": decision_id,
        "summary": f"Test decision {decision_id}",
        "decision": f"Test decision {decision_id}",
        "category": category,
        "confidence": confidence,
        "stakes": stakes,
        "status": status,
        "outcome": outcome if status == "reviewed" else None,
        "date": decision_date.isoformat(),
    }
    if preserve:
        d["preserve"] = True
    if pattern:
        d["pattern"] = pattern
    if context:
        d["context"] = context
    if reasons:
        d["reasons"] = reasons
    if tags:
        d["tags"] = tags
    if bridge:
        d["bridge"] = bridge
    if deliberation:
        d["deliberation"] = deliberation
    return d


def _sample_decisions() -> list[dict[str, Any]]:
    """Create a set of decisions at various ages."""
    return [
        # Full level (< 7 days)
        _make_decision(decision_id="full0001", age_days=0),
        _make_decision(decision_id="full0002", age_days=3),
        _make_decision(decision_id="full0003", age_days=6),
        # Summary level (7-30 days)
        _make_decision(decision_id="summ0001", age_days=7),
        _make_decision(decision_id="summ0002", age_days=15),
        _make_decision(decision_id="summ0003", age_days=29),
        # Digest level (30-90 days)
        _make_decision(decision_id="dige0001", age_days=30),
        _make_decision(decision_id="dige0002", age_days=60),
        _make_decision(decision_id="dige0003", age_days=89),
        # Wisdom level (90+ days)
        _make_decision(decision_id="wisd0001", age_days=90),
        _make_decision(decision_id="wisd0002", age_days=180),
        _make_decision(decision_id="wisd0003", age_days=365),
    ]


@pytest.fixture
def dispatcher() -> CstpDispatcher:
    d = CstpDispatcher()
    register_methods(d)
    return d


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestCompactionModels:
    def test_compaction_levels_constant(self) -> None:
        assert COMPACTION_LEVELS == ("full", "summary", "digest", "wisdom")

    def test_compaction_thresholds(self) -> None:
        assert COMPACTION_THRESHOLDS["full"] == 7
        assert COMPACTION_THRESHOLDS["summary"] == 30
        assert COMPACTION_THRESHOLDS["digest"] == 90
        assert COMPACTION_THRESHOLDS["wisdom"] is None

    def test_compact_request_from_params_defaults(self) -> None:
        req = CompactRequest.from_params({})
        assert req.category is None
        assert req.dry_run is False

    def test_compact_request_from_params_camel_case(self) -> None:
        req = CompactRequest.from_params({"category": "architecture", "dryRun": True})
        assert req.category == "architecture"
        assert req.dry_run is True

    def test_compact_request_from_params_snake_case(self) -> None:
        req = CompactRequest.from_params({"dry_run": True})
        assert req.dry_run is True

    def test_compact_level_count_to_dict(self) -> None:
        lc = CompactLevelCount(full=3, summary=2, digest=1, wisdom=4)
        assert lc.to_dict() == {"full": 3, "summary": 2, "digest": 1, "wisdom": 4}

    def test_compact_response_to_dict(self) -> None:
        resp = CompactResponse(
            compacted=10, preserved=2,
            levels=CompactLevelCount(full=3, summary=2, digest=1, wisdom=4),
            dry_run=True, errors=["err1"],
        )
        d = resp.to_dict()
        assert d["compacted"] == 10
        assert d["preserved"] == 2
        assert d["dryRun"] is True
        assert d["errors"] == ["err1"]

    def test_compact_response_no_errors(self) -> None:
        resp = CompactResponse(
            compacted=5, preserved=0,
            levels=CompactLevelCount(),
        )
        d = resp.to_dict()
        assert "errors" not in d

    def test_get_compacted_request_defaults(self) -> None:
        req = GetCompactedRequest.from_params({})
        assert req.category is None
        assert req.level is None
        assert req.limit == 50
        assert req.include_preserved is True

    def test_get_compacted_request_camel_case(self) -> None:
        req = GetCompactedRequest.from_params({
            "category": "process",
            "level": "summary",
            "limit": 10,
            "includePreserved": False,
        })
        assert req.category == "process"
        assert req.level == "summary"
        assert req.limit == 10
        assert req.include_preserved is False

    def test_get_compacted_request_invalid_level(self) -> None:
        req = GetCompactedRequest.from_params({"level": "invalid"})
        assert req.level is None

    def test_get_compacted_request_limit_clamped(self) -> None:
        req = GetCompactedRequest.from_params({"limit": 9999})
        assert req.limit == 500
        req2 = GetCompactedRequest.from_params({"limit": -1})
        assert req2.limit == 1

    def test_set_preserve_request_camel_case(self) -> None:
        req = SetPreserveRequest.from_params({"decisionId": "abc123"})
        assert req.decision_id == "abc123"
        assert req.preserve is True

    def test_set_preserve_request_snake_case(self) -> None:
        req = SetPreserveRequest.from_params({
            "decision_id": "abc", "preserve": False,
        })
        assert req.decision_id == "abc"
        assert req.preserve is False

    def test_set_preserve_request_id_alias(self) -> None:
        req = SetPreserveRequest.from_params({"id": "xyz"})
        assert req.decision_id == "xyz"

    def test_set_preserve_validate_missing_id(self) -> None:
        req = SetPreserveRequest.from_params({})
        errors = req.validate()
        assert any("decisionId" in e for e in errors)

    def test_set_preserve_response_to_dict(self) -> None:
        resp = SetPreserveResponse(
            success=True, decision_id="abc", preserve=True,
        )
        d = resp.to_dict()
        assert d == {"success": True, "decisionId": "abc", "preserve": True}

    def test_set_preserve_response_error(self) -> None:
        resp = SetPreserveResponse(
            success=False, decision_id="abc", preserve=True, error="not found",
        )
        assert resp.to_dict()["error"] == "not found"

    def test_get_wisdom_request_defaults(self) -> None:
        req = GetWisdomRequest.from_params({})
        assert req.category is None
        assert req.min_decisions == 5

    def test_get_wisdom_request_camel_case(self) -> None:
        req = GetWisdomRequest.from_params({
            "category": "architecture", "minDecisions": 10,
        })
        assert req.category == "architecture"
        assert req.min_decisions == 10

    def test_get_wisdom_request_clamped(self) -> None:
        req = GetWisdomRequest.from_params({"minDecisions": 999})
        assert req.min_decisions == 100
        req2 = GetWisdomRequest.from_params({"minDecisions": -1})
        assert req2.min_decisions == 1

    def test_wisdom_principle_to_dict(self) -> None:
        p = WisdomPrinciple(text="test", confirmations=3, example_ids=["a", "b"])
        d = p.to_dict()
        assert d == {"text": "test", "confirmations": 3, "exampleIds": ["a", "b"]}

    def test_wisdom_entry_to_dict_minimal(self) -> None:
        w = WisdomEntry(category="arch", decisions=10)
        d = w.to_dict()
        assert d == {"category": "arch", "decisions": 10}

    def test_wisdom_entry_to_dict_full(self) -> None:
        w = WisdomEntry(
            category="arch", decisions=10, success_rate=0.9,
            key_principles=[WisdomPrinciple(text="p1", confirmations=3)],
            common_failure_mode="bad pattern",
            avg_confidence=0.85, brier_score=0.03,
        )
        d = w.to_dict()
        assert d["successRate"] == 0.9
        assert d["keyPrinciples"][0]["text"] == "p1"
        assert d["commonFailureMode"] == "bad pattern"
        assert d["avgConfidence"] == 0.85
        assert d["brierScore"] == 0.03

    def test_get_wisdom_response_to_dict(self) -> None:
        resp = GetWisdomResponse(
            wisdom=[WisdomEntry(category="arch", decisions=5)],
            total_decisions=5, categories_analyzed=1,
        )
        d = resp.to_dict()
        assert d["totalDecisions"] == 5
        assert d["categoriesAnalyzed"] == 1
        assert len(d["wisdom"]) == 1

    def test_get_compacted_response_to_dict(self) -> None:
        resp = GetCompactedResponse(
            decisions=[], total=0, levels=CompactLevelCount(),
        )
        d = resp.to_dict()
        assert d["total"] == 0
        assert d["decisions"] == []


# ---------------------------------------------------------------------------
# CompactedDecision to_dict shaping tests
# ---------------------------------------------------------------------------


class TestCompactedDecisionShaping:
    def test_full_level_includes_all_fields(self) -> None:
        cd = CompactedDecision(
            id="abc", level="full", decision="Test", category="arch",
            date="2026-01-01", outcome="success", confidence=0.9,
            actual_confidence=1.0, pattern="pattern", stakes="medium",
            context="ctx", reasons=[{"type": "analysis", "text": "r"}],
            tags=["t1"], bridge={"structure": "s"}, deliberation={"steps": []},
        )
        d = cd.to_dict()
        assert d["context"] == "ctx"
        assert d["reasons"] == [{"type": "analysis", "text": "r"}]
        assert d["tags"] == ["t1"]
        assert d["bridge"] == {"structure": "s"}
        assert d["deliberation"] == {"steps": []}
        assert d["outcome"] == "success"
        assert d["confidence"] == 0.9

    def test_summary_level_excludes_full_fields(self) -> None:
        cd = CompactedDecision(
            id="abc", level="summary", decision="Test", category="arch",
            date="2026-01-01", outcome="success", confidence=0.9,
            actual_confidence=1.0, pattern="p", stakes="medium",
            context="should not appear",
            reasons=[{"type": "analysis", "text": "r"}],
        )
        d = cd.to_dict()
        assert "context" not in d
        assert "reasons" not in d
        assert "tags" not in d
        assert "bridge" not in d
        assert "deliberation" not in d
        assert d["outcome"] == "success"
        assert d["confidence"] == 0.9
        assert d["pattern"] == "p"

    def test_digest_level_only_one_line(self) -> None:
        cd = CompactedDecision(
            id="abc", level="digest", decision="Test", category="arch",
            date="2026-01-01", one_line="Test",
            outcome="success", confidence=0.9,
        )
        d = cd.to_dict()
        assert d["oneLine"] == "Test"
        assert "outcome" not in d
        assert "confidence" not in d
        assert "context" not in d

    def test_preserved_flag_in_output(self) -> None:
        cd = CompactedDecision(
            id="abc", level="full", decision="Test", category="arch",
            date="2026-01-01", preserved=True,
        )
        assert cd.to_dict()["preserved"] is True

    def test_preserved_false_not_in_output(self) -> None:
        cd = CompactedDecision(
            id="abc", level="full", decision="Test", category="arch",
            date="2026-01-01", preserved=False,
        )
        assert "preserved" not in cd.to_dict()


# ---------------------------------------------------------------------------
# determine_compaction_level tests
# ---------------------------------------------------------------------------


class TestDetermineCompactionLevel:
    def test_full_level_day_0(self) -> None:
        d = _make_decision(age_days=0)
        assert determine_compaction_level(d, now=NOW) == "full"

    def test_full_level_day_6(self) -> None:
        d = _make_decision(age_days=6)
        assert determine_compaction_level(d, now=NOW) == "full"

    def test_summary_level_day_7(self) -> None:
        d = _make_decision(age_days=7)
        assert determine_compaction_level(d, now=NOW) == "summary"

    def test_summary_level_day_8(self) -> None:
        d = _make_decision(age_days=8)
        assert determine_compaction_level(d, now=NOW) == "summary"

    def test_summary_level_day_29(self) -> None:
        d = _make_decision(age_days=29)
        assert determine_compaction_level(d, now=NOW) == "summary"

    def test_digest_level_day_30(self) -> None:
        d = _make_decision(age_days=30)
        assert determine_compaction_level(d, now=NOW) == "digest"

    def test_digest_level_day_31(self) -> None:
        d = _make_decision(age_days=31)
        assert determine_compaction_level(d, now=NOW) == "digest"

    def test_digest_level_day_89(self) -> None:
        d = _make_decision(age_days=89)
        assert determine_compaction_level(d, now=NOW) == "digest"

    def test_wisdom_level_day_90(self) -> None:
        d = _make_decision(age_days=90)
        assert determine_compaction_level(d, now=NOW) == "wisdom"

    def test_wisdom_level_day_91(self) -> None:
        d = _make_decision(age_days=91)
        assert determine_compaction_level(d, now=NOW) == "wisdom"

    def test_wisdom_level_day_365(self) -> None:
        d = _make_decision(age_days=365)
        assert determine_compaction_level(d, now=NOW) == "wisdom"

    def test_preserved_always_full(self) -> None:
        d = _make_decision(age_days=365, preserve=True)
        assert determine_compaction_level(d, now=NOW) == "full"

    def test_pending_always_full(self) -> None:
        d = _make_decision(age_days=365, status="pending")
        assert determine_compaction_level(d, now=NOW) == "full"

    def test_no_date_returns_full(self) -> None:
        d = _make_decision(age_days=100)
        d["date"] = ""
        assert determine_compaction_level(d, now=NOW) == "full"

    def test_date_only_format(self) -> None:
        """Supports date-only strings like '2025-01-01'."""
        d = _make_decision(age_days=100)
        d["date"] = "2025-01-01"
        assert determine_compaction_level(d, now=NOW) in COMPACTION_LEVELS

    def test_iso_datetime_format(self) -> None:
        """Supports full ISO datetime strings."""
        d = _make_decision(age_days=10)
        assert determine_compaction_level(d, now=NOW) == "summary"

    def test_created_at_fallback(self) -> None:
        """Falls back to created_at if date is missing."""
        d = _make_decision(age_days=50)
        d["created_at"] = d.pop("date")
        assert determine_compaction_level(d, now=NOW) == "digest"


# ---------------------------------------------------------------------------
# compact_decision tests
# ---------------------------------------------------------------------------


class TestCompactDecision:
    def test_full_includes_all(self) -> None:
        d = _make_decision(
            context="ctx", reasons=[{"type": "analysis", "text": "r"}],
            tags=["t1"], bridge={"structure": "s"},
            deliberation={"steps": []},
        )
        cd = compact_decision(d, "full")
        assert cd.level == "full"
        assert cd.context == "ctx"
        assert cd.reasons == [{"type": "analysis", "text": "r"}]
        assert cd.tags == ["t1"]
        assert cd.bridge == {"structure": "s"}
        assert cd.deliberation == {"steps": []}

    def test_summary_strips_detail(self) -> None:
        d = _make_decision(
            context="ctx", reasons=[{"type": "a", "text": "r"}],
            pattern="test pattern",
        )
        cd = compact_decision(d, "summary")
        assert cd.level == "summary"
        assert cd.outcome == "success"
        assert cd.pattern == "test pattern"
        assert cd.confidence == 0.9
        assert cd.actual_confidence == 1.0  # success -> 1.0
        assert cd.context is None
        assert cd.reasons is None

    def test_digest_has_one_line(self) -> None:
        d = _make_decision()
        cd = compact_decision(d, "digest")
        assert cd.level == "digest"
        assert cd.one_line is not None
        assert len(cd.one_line) <= 80

    def test_digest_truncates_long_text(self) -> None:
        d = _make_decision()
        d["summary"] = "A" * 100
        cd = compact_decision(d, "digest")
        assert cd.one_line is not None
        assert len(cd.one_line) <= 80
        assert cd.one_line.endswith("...")

    def test_actual_confidence_mapping(self) -> None:
        for outcome, expected in OUTCOME_CONFIDENCE.items():
            d = _make_decision(outcome=outcome)
            cd = compact_decision(d, "summary")
            assert cd.actual_confidence == expected

    def test_actual_confidence_none_for_pending(self) -> None:
        d = _make_decision(status="pending")
        cd = compact_decision(d, "full")
        assert cd.actual_confidence is None

    def test_id_truncated_to_8(self) -> None:
        d = _make_decision(decision_id="abcdefghijklmnop")
        cd = compact_decision(d, "full")
        assert len(cd.id) == 8

    def test_tags_string_to_list(self) -> None:
        d = _make_decision()
        d["tags"] = "tag1,tag2,tag3"
        cd = compact_decision(d, "full")
        assert cd.tags == ["tag1", "tag2", "tag3"]

    def test_preserved_flag_carried(self) -> None:
        d = _make_decision(preserve=True)
        cd = compact_decision(d, "full")
        assert cd.preserved is True


# ---------------------------------------------------------------------------
# run_compaction tests
# ---------------------------------------------------------------------------


class TestRunCompaction:
    @pytest.mark.asyncio
    async def test_counts_levels_correctly(self) -> None:
        decisions = _sample_decisions()
        req = CompactRequest()
        resp = await run_compaction(req, preloaded_decisions=decisions, now=NOW)
        assert resp.compacted == 12
        assert resp.levels.full == 3
        assert resp.levels.summary == 3
        assert resp.levels.digest == 3
        assert resp.levels.wisdom == 3

    @pytest.mark.asyncio
    async def test_counts_preserved(self) -> None:
        decisions = [
            _make_decision(decision_id="a", age_days=100, preserve=True),
            _make_decision(decision_id="b", age_days=100, preserve=True),
            _make_decision(decision_id="c", age_days=100),
        ]
        req = CompactRequest()
        resp = await run_compaction(req, preloaded_decisions=decisions, now=NOW)
        assert resp.preserved == 2
        # Preserved decisions are counted as full
        assert resp.levels.full == 2
        assert resp.levels.wisdom == 1

    @pytest.mark.asyncio
    async def test_dry_run_flag(self) -> None:
        req = CompactRequest(dry_run=True)
        resp = await run_compaction(req, preloaded_decisions=[], now=NOW)
        assert resp.dry_run is True

    @pytest.mark.asyncio
    async def test_empty_decisions(self) -> None:
        req = CompactRequest()
        resp = await run_compaction(req, preloaded_decisions=[], now=NOW)
        assert resp.compacted == 0
        assert resp.levels.full == 0

    @pytest.mark.asyncio
    async def test_pending_counted_as_full(self) -> None:
        decisions = [_make_decision(status="pending", age_days=100)]
        req = CompactRequest()
        resp = await run_compaction(req, preloaded_decisions=decisions, now=NOW)
        assert resp.levels.full == 1


# ---------------------------------------------------------------------------
# get_compacted_decisions tests
# ---------------------------------------------------------------------------


class TestGetCompactedDecisions:
    @pytest.mark.asyncio
    async def test_returns_shaped_decisions(self) -> None:
        decisions = _sample_decisions()
        req = GetCompactedRequest()
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        assert resp.total > 0
        for cd in resp.decisions:
            assert cd.level in ("full", "summary", "digest")

    @pytest.mark.asyncio
    async def test_wisdom_excluded_by_default(self) -> None:
        """Wisdom-level decisions not returned individually."""
        decisions = _sample_decisions()
        req = GetCompactedRequest()
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        levels_returned = {cd.level for cd in resp.decisions}
        assert "wisdom" not in levels_returned

    @pytest.mark.asyncio
    async def test_forced_level_filter(self) -> None:
        decisions = _sample_decisions()
        req = GetCompactedRequest(level="summary")
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        assert all(cd.level == "summary" for cd in resp.decisions)

    @pytest.mark.asyncio
    async def test_limit_respected(self) -> None:
        decisions = _sample_decisions()
        req = GetCompactedRequest(limit=2)
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        assert len(resp.decisions) <= 2

    @pytest.mark.asyncio
    async def test_exclude_preserved(self) -> None:
        decisions = [
            _make_decision(decision_id="a", preserve=True),
            _make_decision(decision_id="b"),
        ]
        req = GetCompactedRequest(include_preserved=False)
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        ids = [cd.id for cd in resp.decisions]
        assert "a" not in [i[:1] for i in ids] or not any(
            cd.preserved for cd in resp.decisions
        )

    @pytest.mark.asyncio
    async def test_sorted_by_date_descending(self) -> None:
        decisions = _sample_decisions()
        req = GetCompactedRequest()
        resp = await get_compacted_decisions(req, preloaded_decisions=decisions, now=NOW)
        dates = [cd.date for cd in resp.decisions]
        assert dates == sorted(dates, reverse=True)

    @pytest.mark.asyncio
    async def test_empty_decisions(self) -> None:
        req = GetCompactedRequest()
        resp = await get_compacted_decisions(req, preloaded_decisions=[], now=NOW)
        assert resp.total == 0
        assert resp.decisions == []


# ---------------------------------------------------------------------------
# set_preserve tests (uses temp files)
# ---------------------------------------------------------------------------


class TestSetPreserve:
    @pytest.mark.asyncio
    async def test_set_preserve_on_existing(self, tmp_path: Any) -> None:
        """Test setting preserve flag on an existing decision."""
        import os
        import yaml

        # Create a temp decision file
        year_dir = tmp_path / "2026" / "02"
        year_dir.mkdir(parents=True)
        decision_file = year_dir / "2026-02-15-decision-testpres.yaml"
        data = {
            "id": "testpres",
            "summary": "Test",
            "category": "architecture",
            "status": "reviewed",
        }
        with open(decision_file, "w") as f:
            yaml.dump(data, f)

        # Patch DECISIONS_PATH
        original = os.environ.get("DECISIONS_PATH")
        os.environ["DECISIONS_PATH"] = str(tmp_path)

        # Also need to patch the decision_service module's DECISIONS_PATH
        import a2a.cstp.decision_service as ds
        old_path = ds.DECISIONS_PATH
        ds.DECISIONS_PATH = str(tmp_path)

        try:
            req = SetPreserveRequest(decision_id="testpres", preserve=True)
            resp = await set_preserve(req)
            assert resp.success is True
            assert resp.preserve is True

            # Verify file updated
            with open(decision_file) as f:
                updated = yaml.safe_load(f)
            assert updated["preserve"] is True
        finally:
            ds.DECISIONS_PATH = old_path
            if original is not None:
                os.environ["DECISIONS_PATH"] = original
            else:
                os.environ.pop("DECISIONS_PATH", None)

    @pytest.mark.asyncio
    async def test_set_preserve_not_found(self) -> None:
        import a2a.cstp.decision_service as ds
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            old_path = ds.DECISIONS_PATH
            ds.DECISIONS_PATH = tmp
            try:
                req = SetPreserveRequest(decision_id="nonexist", preserve=True)
                resp = await set_preserve(req)
                assert resp.success is False
                assert "not found" in (resp.error or "").lower()
            finally:
                ds.DECISIONS_PATH = old_path

    @pytest.mark.asyncio
    async def test_unset_preserve(self, tmp_path: Any) -> None:
        """Test removing preserve flag."""
        import yaml
        import a2a.cstp.decision_service as ds

        year_dir = tmp_path / "2026" / "02"
        year_dir.mkdir(parents=True)
        decision_file = year_dir / "2026-02-15-decision-unsetpr.yaml"
        data = {
            "id": "unsetpr",
            "summary": "Test",
            "preserve": True,
        }
        with open(decision_file, "w") as f:
            yaml.dump(data, f)

        old_path = ds.DECISIONS_PATH
        ds.DECISIONS_PATH = str(tmp_path)
        try:
            req = SetPreserveRequest(decision_id="unsetpr", preserve=False)
            resp = await set_preserve(req)
            assert resp.success is True
            assert resp.preserve is False

            with open(decision_file) as f:
                updated = yaml.safe_load(f)
            assert "preserve" not in updated
        finally:
            ds.DECISIONS_PATH = old_path


# ---------------------------------------------------------------------------
# build_wisdom tests
# ---------------------------------------------------------------------------


class TestBuildWisdom:
    def _wisdom_decisions(
        self, count: int = 10, category: str = "architecture",
    ) -> list[dict[str, Any]]:
        """Create a set of reviewed wisdom-age decisions."""
        decisions = []
        for i in range(count):
            outcome = "success" if i % 3 != 0 else "failure"
            pattern = f"Pattern {i % 3}" if i < 6 else None
            decisions.append(_make_decision(
                decision_id=f"w{i:06d}",
                age_days=100 + i,
                category=category,
                outcome=outcome,
                confidence=0.8 + (i % 3) * 0.05,
                pattern=pattern,
            ))
        return decisions

    def test_basic_wisdom_extraction(self) -> None:
        decisions = self._wisdom_decisions(count=10)
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert len(wisdom) == 1
        assert wisdom[0].category == "architecture"
        assert wisdom[0].decisions == 10

    def test_success_rate_calculated(self) -> None:
        decisions = self._wisdom_decisions(count=9)
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert wisdom[0].success_rate is not None
        assert 0 <= wisdom[0].success_rate <= 1

    def test_min_decisions_threshold(self) -> None:
        decisions = self._wisdom_decisions(count=3)
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert len(wisdom) == 0

    def test_category_filter(self) -> None:
        decisions = (
            self._wisdom_decisions(count=10, category="architecture")
            + self._wisdom_decisions(count=10, category="process")
        )
        wisdom = build_wisdom(decisions, min_decisions=5, category_filter="process")
        assert len(wisdom) == 1
        assert wisdom[0].category == "process"

    def test_principles_from_patterns(self) -> None:
        decisions = []
        for i in range(10):
            decisions.append(_make_decision(
                decision_id=f"p{i:06d}",
                age_days=100 + i,
                pattern="Search before deciding",
            ))
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert len(wisdom[0].key_principles) > 0
        assert wisdom[0].key_principles[0].text == "Search before deciding"

    def test_common_failure_mode(self) -> None:
        decisions = []
        for i in range(10):
            outcome = "failure" if i < 5 else "success"
            decisions.append(_make_decision(
                decision_id=f"f{i:06d}",
                age_days=100 + i,
                outcome=outcome,
                pattern="Skip pre-check" if i < 5 else "Do pre-check",
            ))
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert wisdom[0].common_failure_mode == "Skip pre-check"

    def test_brier_score_calculated(self) -> None:
        decisions = self._wisdom_decisions(count=10)
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert wisdom[0].brier_score is not None
        assert wisdom[0].brier_score >= 0

    def test_avg_confidence_calculated(self) -> None:
        decisions = self._wisdom_decisions(count=10)
        wisdom = build_wisdom(decisions, min_decisions=5)
        assert wisdom[0].avg_confidence is not None

    def test_pending_excluded(self) -> None:
        decisions = [
            _make_decision(decision_id=f"pe{i}", age_days=100, status="pending")
            for i in range(10)
        ]
        wisdom = build_wisdom(decisions, min_decisions=1)
        assert len(wisdom) == 0

    def test_recent_decisions_excluded(self) -> None:
        """Only wisdom-age (90+ day) decisions count."""
        decisions = self._wisdom_decisions(count=10)
        # Override to recent dates
        for d in decisions:
            d["date"] = (NOW - timedelta(days=5)).isoformat()
        wisdom = build_wisdom(decisions, min_decisions=1)
        assert len(wisdom) == 0

    def test_multiple_categories(self) -> None:
        decisions = (
            self._wisdom_decisions(count=10, category="architecture")
            + self._wisdom_decisions(count=10, category="tooling")
        )
        wisdom = build_wisdom(decisions, min_decisions=5)
        categories = [w.category for w in wisdom]
        assert "architecture" in categories
        assert "tooling" in categories

    def test_empty_decisions(self) -> None:
        wisdom = build_wisdom([], min_decisions=1)
        assert wisdom == []


# ---------------------------------------------------------------------------
# get_wisdom async wrapper tests
# ---------------------------------------------------------------------------


class TestGetWisdom:
    @pytest.mark.asyncio
    async def test_basic(self) -> None:
        decisions = [
            _make_decision(decision_id=f"gw{i}", age_days=100 + i)
            for i in range(10)
        ]
        req = GetWisdomRequest(min_decisions=5)
        resp = await get_wisdom(req, preloaded_decisions=decisions)
        assert resp.categories_analyzed == 1
        assert resp.total_decisions == 10

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        req = GetWisdomRequest()
        resp = await get_wisdom(req, preloaded_decisions=[])
        assert resp.categories_analyzed == 0
        assert resp.total_decisions == 0


# ---------------------------------------------------------------------------
# Dispatcher integration tests
# ---------------------------------------------------------------------------


class TestDispatcherIntegration:
    @pytest.mark.asyncio
    async def test_compact_registered(self, dispatcher: CstpDispatcher) -> None:
        req = JsonRpcRequest(
            jsonrpc="2.0", id="1", method="cstp.compact",
            params={},
        )
        resp = await dispatcher.dispatch(req, "test-agent")
        assert resp.result is not None
        assert "compacted" in resp.result

    @pytest.mark.asyncio
    async def test_get_compacted_registered(
        self, dispatcher: CstpDispatcher,
    ) -> None:
        req = JsonRpcRequest(
            jsonrpc="2.0", id="2", method="cstp.getCompacted",
            params={},
        )
        resp = await dispatcher.dispatch(req, "test-agent")
        assert resp.result is not None
        assert "decisions" in resp.result

    @pytest.mark.asyncio
    async def test_set_preserve_validation(
        self, dispatcher: CstpDispatcher,
    ) -> None:
        req = JsonRpcRequest(
            jsonrpc="2.0", id="3", method="cstp.setPreserve",
            params={},
        )
        resp = await dispatcher.dispatch(req, "test-agent")
        # Should fail validation (missing decisionId)
        assert resp.error is not None

    @pytest.mark.asyncio
    async def test_get_wisdom_registered(
        self, dispatcher: CstpDispatcher,
    ) -> None:
        req = JsonRpcRequest(
            jsonrpc="2.0", id="4", method="cstp.getWisdom",
            params={},
        )
        resp = await dispatcher.dispatch(req, "test-agent")
        assert resp.result is not None
        assert "wisdom" in resp.result
