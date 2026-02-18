"""Tests for F163: Enrich pre_action relevant decisions with outcome, reasons, lessons.

Covers:
1. DecisionSummary serialization (lessons, actualResult in to_dict)
2. QueryDecisionsRequest parsing (includeDetail / include_detail)
3. QueryResult enrichment fields (lessons, actual_result, reasons)
4. ChromaDB metadata enrichment (reindex_decision + record_decision)
5. Metadata parsing in query_decisions
6. Backward compatibility (old metadata without enrichment fields)
7. pre_action enrichment (lessons from query results)
8. Dispatcher wiring (all 4 paths: semantic, list-all, keyword, hybrid)
9. DecisionSummary reasons type change (list[str] -> list[dict])
"""

import importlib.util
import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock MCP modules before any a2a imports (CI doesn't have mcp installed)
_mcp_available = False
try:
    _mcp_available = importlib.util.find_spec("mcp") is not None
except (ValueError, ModuleNotFoundError):
    pass
if not _mcp_available:
    mock_mcp = MagicMock()
    sys.modules["mcp"] = mock_mcp
    sys.modules["mcp.server"] = mock_mcp
    sys.modules["mcp.server.stdio"] = mock_mcp
    sys.modules["mcp.server.streamable_http_manager"] = mock_mcp
    sys.modules["mcp.types"] = mock_mcp

import pytest

from a2a.cstp.models import DecisionSummary, QueryDecisionsRequest
from a2a.cstp.query_service import QueryResult


# ---------------------------------------------------------------------------
# 1. DecisionSummary serialization
# ---------------------------------------------------------------------------


class TestDecisionSummarySerialization:
    """Verify to_dict() includes F163 fields when set, omits when None."""

    def test_to_dict_includes_lessons_when_set(self) -> None:
        ds = DecisionSummary(
            id="abc12345", title="Test decision", category="architecture",
            confidence=0.9, stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.15,
            lessons="Always validate inputs before processing",
        )
        assert ds.to_dict()["lessons"] == "Always validate inputs before processing"

    def test_to_dict_includes_actual_result_as_camel_case(self) -> None:
        ds = DecisionSummary(
            id="abc12345", title="Test decision", category="architecture",
            confidence=0.9, stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.15,
            actual_result="Deployed successfully with zero downtime",
        )
        result = ds.to_dict()
        assert result["actualResult"] == "Deployed successfully with zero downtime"
        assert "actual_result" not in result

    def test_to_dict_includes_reasons_as_dicts(self) -> None:
        reasons = [
            {"type": "analysis", "text": "Analyzed performance"},
            {"type": "empirical", "text": "Benchmarked alternatives"},
        ]
        ds = DecisionSummary(
            id="abc12345", title="Test decision", category="architecture",
            confidence=0.9, stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.15, reasons=reasons,
        )
        assert ds.to_dict()["reasons"] == reasons

    def test_to_dict_omits_f163_fields_when_none(self) -> None:
        ds = DecisionSummary(
            id="abc12345", title="Test decision", category="architecture",
            confidence=0.9, stakes="medium", status="pending", outcome=None,
            date="2026-02-17", distance=0.15,
            lessons=None, actual_result=None, reasons=None,
        )
        result = ds.to_dict()
        assert "lessons" not in result
        assert "actualResult" not in result
        assert "reasons" not in result

    def test_to_dict_all_f163_fields_together(self) -> None:
        reasons = [{"type": "pattern", "text": "Matches known pattern"}]
        ds = DecisionSummary(
            id="abc12345", title="Test", category="tooling",
            confidence=0.85, stakes="low", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.1,
            lessons="Use caching", actual_result="95% cache hit", reasons=reasons,
        )
        result = ds.to_dict()
        assert result["lessons"] == "Use caching"
        assert result["actualResult"] == "95% cache hit"
        assert result["reasons"] == reasons

    def test_default_f163_fields_are_none(self) -> None:
        ds = DecisionSummary(
            id="abc12345", title="Test", category="process",
            confidence=0.8, stakes="low", status="pending", outcome=None,
            date="2025-01-01", distance=0.3,
        )
        assert ds.lessons is None
        assert ds.actual_result is None
        assert ds.reasons is None
        d = ds.to_dict()
        assert "lessons" not in d
        assert "actualResult" not in d
        assert "reasons" not in d


# ---------------------------------------------------------------------------
# 2. QueryDecisionsRequest include_detail parsing
# ---------------------------------------------------------------------------


class TestIncludeDetailParsing:
    """Verify from_params() parses include_detail on QueryDecisionsRequest."""

    def test_defaults_to_false(self) -> None:
        assert QueryDecisionsRequest.from_params({"query": "t"}).include_detail is False

    def test_parses_camel_case(self) -> None:
        req = QueryDecisionsRequest.from_params({"query": "t", "includeDetail": True})
        assert req.include_detail is True

    def test_parses_snake_case(self) -> None:
        req = QueryDecisionsRequest.from_params({"query": "t", "include_detail": True})
        assert req.include_detail is True

    def test_false_preserved(self) -> None:
        req = QueryDecisionsRequest.from_params({"query": "t", "includeDetail": False})
        assert req.include_detail is False

    def test_truthy_int_coerced(self) -> None:
        req = QueryDecisionsRequest.from_params({"query": "t", "includeDetail": 1})
        assert req.include_detail is True

    def test_other_fields_unaffected(self) -> None:
        req = QueryDecisionsRequest.from_params(
            {"query": "t", "limit": 20, "includeDetail": True}
        )
        assert req.limit == 20
        assert req.include_detail is True


# ---------------------------------------------------------------------------
# 3. QueryResult fields
# ---------------------------------------------------------------------------


class TestQueryResultFields:
    """Verify QueryResult dataclass has F163 fields with correct defaults."""

    def test_default_values_are_none(self) -> None:
        qr = QueryResult(
            id="abc12345", title="Test", category="architecture",
            confidence=0.9, stakes="medium", status="pending", outcome=None,
            date="2026-02-17", distance=0.2,
        )
        assert qr.lessons is None
        assert qr.actual_result is None
        assert qr.reasons is None

    def test_fields_can_be_set(self) -> None:
        qr = QueryResult(
            id="abc12345", title="Test", category="architecture",
            confidence=0.9, stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.2,
            lessons="Lesson", actual_result="Worked",
            reasons=[{"type": "analysis", "text": "Detail"}],
        )
        assert qr.lessons == "Lesson"
        assert qr.actual_result == "Worked"
        assert qr.reasons == [{"type": "analysis", "text": "Detail"}]


# ---------------------------------------------------------------------------
# 4. ChromaDB metadata enrichment (reindex_decision)
# ---------------------------------------------------------------------------


class TestReindexDecisionMetadata:
    """Verify reindex_decision writes lessons, actual_result, reason_types."""

    @pytest.mark.asyncio
    async def test_reindex_writes_lessons_to_metadata(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        with (
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.decision_service import reindex_decision

            data = {
                "summary": "Test decision", "category": "architecture",
                "confidence": 0.9, "stakes": "medium", "status": "reviewed",
                "outcome": "success", "date": "2026-02-17",
                "lessons": "Always validate inputs",
                "actual_result": "Deployed successfully",
                "reasons": [
                    {"type": "analysis", "text": "Analyzed perf"},
                    {"type": "empirical", "text": "Benchmarked"},
                ],
            }
            assert await reindex_decision("test1234", data, "/fake/path.yaml") is True

            meta = store._docs["test1234"]["metadata"]
            assert meta["lessons"] == "Always validate inputs"
            assert meta["actual_result"] == "Deployed successfully"
            assert "analysis" in meta["reason_types"]
            assert "empirical" in meta["reason_types"]
            reasons_parsed = json.loads(meta["reasons_json"])
            assert len(reasons_parsed) == 2

    @pytest.mark.asyncio
    async def test_reindex_caps_lessons_at_500_chars(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        with (
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.decision_service import reindex_decision

            await reindex_decision("t1", {"summary": "T", "category": "architecture",
                                          "date": "2026-02-17", "lessons": "x" * 1000},
                                   "/fake.yaml")
            assert len(store._docs["t1"]["metadata"]["lessons"]) == 500

    @pytest.mark.asyncio
    async def test_reindex_omits_empty_lessons(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        with (
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.decision_service import reindex_decision

            await reindex_decision("t1", {"summary": "T", "category": "architecture",
                                          "date": "2026-02-17"}, "/fake.yaml")
            meta = store._docs["t1"]["metadata"]
            assert "lessons" not in meta
            assert "actual_result" not in meta


# ---------------------------------------------------------------------------
# 4b. record_decision writes reason_types and reasons_json
# ---------------------------------------------------------------------------


class TestRecordDecisionMetadata:
    """Verify record_decision writes reason_types and reasons_json."""

    @pytest.mark.asyncio
    async def test_record_writes_reason_types_and_json(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)
        mock_ds = AsyncMock()
        mock_ds.save = AsyncMock()

        with (
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=mock_provider),
            patch("a2a.cstp.decision_service.get_decision_store", return_value=mock_ds),
            patch("a2a.cstp.decision_service.write_decision_file", return_value="/fake.yaml"),
        ):
            from a2a.cstp.decision_service import Reason, RecordDecisionRequest, record_decision

            req = RecordDecisionRequest(
                decision="Use Redis", confidence=0.85, category="architecture",
                stakes="medium", reasons=[
                    Reason(type="analysis", text="Perf requirements"),
                    Reason(type="empirical", text="Benchmarked Redis"),
                ],
            )
            resp = await record_decision(req)
            assert resp.success is True
            meta = store._docs[resp.id]["metadata"]
            assert "analysis" in meta["reason_types"]
            assert "empirical" in meta["reason_types"]
            assert len(json.loads(meta["reasons_json"])) == 2


# ---------------------------------------------------------------------------
# 5. Metadata parsing in query_decisions
# ---------------------------------------------------------------------------


class TestQueryDecisionsParsing:
    """Verify query_decisions extracts lessons, actual_result, reasons."""

    @pytest.mark.asyncio
    async def test_extracts_lessons_and_actual_result(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        await store.upsert("t1", "Decision: T", [0.1] * 768, {
            "title": "T", "category": "architecture", "confidence": 0.9,
            "stakes": "medium", "status": "reviewed", "outcome": "success",
            "date": "2026-02-17",
            "lessons": "Cache invalidation is hard",
            "actual_result": "Hit rate improved 40%",
            "reason_types": "analysis,empirical",
            "reasons_json": json.dumps([
                {"type": "analysis", "text": "Perf analysis"},
                {"type": "empirical", "text": "Load test results"},
            ]),
        })

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            resp = await query_decisions("test query", n_results=5)
            assert not resp.error and len(resp.results) == 1
            r = resp.results[0]
            assert r.lessons == "Cache invalidation is hard"
            assert r.actual_result == "Hit rate improved 40%"
            assert r.reason_types == ["analysis", "empirical"]
            assert r.reasons is not None and len(r.reasons) == 2

    @pytest.mark.asyncio
    async def test_invalid_reasons_json_parses_as_none(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        await store.upsert("bad1", "D: Bad", [0.1] * 768, {
            "title": "Bad", "category": "process", "status": "pending",
            "date": "2026-02-17", "reasons_json": "not-valid{{{",
        })

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            resp = await query_decisions("bad", n_results=5)
            assert resp.results[0].reasons is None


# ---------------------------------------------------------------------------
# 6. Backward compatibility
# ---------------------------------------------------------------------------


class TestBackwardCompatibility:
    """Verify old metadata without F163 fields parses as None."""

    @pytest.mark.asyncio
    async def test_old_metadata_parses_as_none(self) -> None:
        from a2a.cstp.vectordb.memory import MemoryStore

        store = MemoryStore()
        await store.initialize()
        mock_provider = AsyncMock()
        mock_provider.embed = AsyncMock(return_value=[0.1] * 768)

        await store.upsert("old1", "D: Old", [0.1] * 768, {
            "title": "Old", "category": "process", "confidence": 0.8,
            "stakes": "low", "status": "pending", "date": "2025-01-01",
        })

        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=mock_provider),
        ):
            from a2a.cstp.query_service import query_decisions

            resp = await query_decisions("old", n_results=5)
            r = resp.results[0]
            assert r.lessons is None
            assert r.actual_result is None
            assert r.reasons is None
            assert r.reason_types is None


# ---------------------------------------------------------------------------
# 7. pre_action enrichment
# ---------------------------------------------------------------------------


def _mock_guardrails_and_calibration():
    """Build standard mock guardrail + calibration results."""
    gr = MagicMock()
    gr.allowed = True
    gr.violations = []
    gr.warnings = []
    gr.evaluated = 0
    cal = MagicMock()
    cal.overall = None
    return gr, cal


class TestPreActionEnrichment:
    """Verify pre_action passes lessons from query results."""

    @pytest.mark.asyncio
    async def test_lessons_passed(self) -> None:
        from a2a.cstp.query_service import QueryResponse

        qr = QueryResponse(results=[QueryResult(
            id="a1", title="Past", category="architecture", confidence=0.9,
            stakes="medium", status="reviewed", outcome="success",
            date="2026-02-15", distance=0.2, lessons="Always cache",
        )], query="t", query_time_ms=10)
        gr, cal = _mock_guardrails_and_calibration()

        with (
            patch("a2a.cstp.preaction_service.query_decisions", AsyncMock(return_value=qr)),
            patch("a2a.cstp.preaction_service.evaluate_guardrails", AsyncMock(return_value=gr)),
            patch("a2a.cstp.preaction_service.get_calibration", AsyncMock(return_value=cal)),
            patch("a2a.cstp.preaction_service.record_decision", AsyncMock()),
            patch("a2a.cstp.preaction_service.log_guardrail_check"),
            patch("a2a.cstp.deliberation_tracker.track_query"),
            patch("a2a.cstp.deliberation_tracker.track_guardrail"),
        ):
            from a2a.cstp.models import ActionContext, PreActionOptions, PreActionRequest
            from a2a.cstp.preaction_service import pre_action

            resp = await pre_action(PreActionRequest(
                action=ActionContext(description="Test", category="architecture"),
                options=PreActionOptions(auto_record=False),
            ), agent_id="test")
            assert resp.relevant_decisions[0].lessons == "Always cache"

    @pytest.mark.asyncio
    async def test_lessons_none_when_absent(self) -> None:
        from a2a.cstp.query_service import QueryResponse

        qr = QueryResponse(results=[QueryResult(
            id="a1", title="Past", category="architecture", confidence=0.9,
            stakes="medium", status="pending", outcome=None,
            date="2026-02-15", distance=0.2,
        )], query="t", query_time_ms=10)
        gr, cal = _mock_guardrails_and_calibration()

        with (
            patch("a2a.cstp.preaction_service.query_decisions", AsyncMock(return_value=qr)),
            patch("a2a.cstp.preaction_service.evaluate_guardrails", AsyncMock(return_value=gr)),
            patch("a2a.cstp.preaction_service.get_calibration", AsyncMock(return_value=cal)),
            patch("a2a.cstp.preaction_service.record_decision", AsyncMock()),
            patch("a2a.cstp.preaction_service.log_guardrail_check"),
            patch("a2a.cstp.deliberation_tracker.track_query"),
            patch("a2a.cstp.deliberation_tracker.track_guardrail"),
        ):
            from a2a.cstp.models import ActionContext, PreActionOptions, PreActionRequest
            from a2a.cstp.preaction_service import pre_action

            resp = await pre_action(PreActionRequest(
                action=ActionContext(description="Test", category="architecture"),
                options=PreActionOptions(auto_record=False),
            ), agent_id="test")
            assert resp.relevant_decisions[0].lessons is None

    @pytest.mark.asyncio
    async def test_reasons_passed(self) -> None:
        from a2a.cstp.query_service import QueryResponse

        reasons = [{"type": "analysis", "text": "Perf"}, {"type": "empirical", "text": "Load"}]
        qr = QueryResponse(results=[QueryResult(
            id="a1", title="Past", category="architecture", confidence=0.9,
            stakes="medium", status="reviewed", outcome="success",
            date="2026-02-15", distance=0.2, reasons=reasons,
        )], query="t", query_time_ms=10)
        gr, cal = _mock_guardrails_and_calibration()

        with (
            patch("a2a.cstp.preaction_service.query_decisions", AsyncMock(return_value=qr)),
            patch("a2a.cstp.preaction_service.evaluate_guardrails", AsyncMock(return_value=gr)),
            patch("a2a.cstp.preaction_service.get_calibration", AsyncMock(return_value=cal)),
            patch("a2a.cstp.preaction_service.record_decision", AsyncMock()),
            patch("a2a.cstp.preaction_service.log_guardrail_check"),
            patch("a2a.cstp.deliberation_tracker.track_query"),
            patch("a2a.cstp.deliberation_tracker.track_guardrail"),
        ):
            from a2a.cstp.models import ActionContext, PreActionOptions, PreActionRequest
            from a2a.cstp.preaction_service import pre_action

            resp = await pre_action(PreActionRequest(
                action=ActionContext(description="Test", category="architecture"),
                options=PreActionOptions(auto_record=False),
            ), agent_id="test")
            ds = resp.relevant_decisions[0]
            assert ds.reasons is not None and len(ds.reasons) == 2


# ---------------------------------------------------------------------------
# 8. Dispatcher wiring
# ---------------------------------------------------------------------------


class TestDispatcherWiring:
    """Verify dispatcher wires lessons/actual_result through all query paths."""

    @pytest.mark.asyncio
    async def test_semantic_path_includes_lessons(self) -> None:
        from a2a.cstp.query_service import QueryResponse

        qr = QueryResponse(results=[QueryResult(
            id="a1", title="T", category="architecture", confidence=0.9,
            stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.15,
            lessons="Semantic lesson", actual_result="Worked",
            reasons=[{"type": "analysis", "text": "D"}],
        )], query="t", query_time_ms=5)

        with (
            patch("a2a.cstp.dispatcher.query_decisions", AsyncMock(return_value=qr)),
            patch("a2a.cstp.deliberation_tracker.track_query"),
        ):
            from a2a.cstp.dispatcher import _handle_query_decisions

            result = await _handle_query_decisions(
                {"query": "t", "retrievalMode": "semantic"}, "agent",
            )
            assert result["decisions"][0].get("lessons") == "Semantic lesson"

    @pytest.mark.asyncio
    async def test_semantic_gates_actual_result_on_include_detail(self) -> None:
        from a2a.cstp.query_service import QueryResponse

        qr = QueryResponse(results=[QueryResult(
            id="a1", title="T", category="architecture", confidence=0.9,
            stakes="medium", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.15, actual_result="It worked",
        )], query="t", query_time_ms=5)

        with (
            patch("a2a.cstp.dispatcher.query_decisions", AsyncMock(return_value=qr)),
            patch("a2a.cstp.deliberation_tracker.track_query"),
        ):
            from a2a.cstp.dispatcher import _handle_query_decisions

            r_no = await _handle_query_decisions(
                {"query": "t", "retrievalMode": "semantic"}, "agent",
            )
            assert "actualResult" not in r_no["decisions"][0]

            r_yes = await _handle_query_decisions(
                {"query": "t", "retrievalMode": "semantic", "includeDetail": True}, "agent",
            )
            assert r_yes["decisions"][0].get("actualResult") == "It worked"

    @pytest.mark.asyncio
    async def test_list_all_path_includes_lessons(self) -> None:
        decs = [{
            "id": "a1", "summary": "T", "category": "tooling", "confidence": 0.8,
            "stakes": "low", "status": "reviewed", "outcome": "success",
            "created_at": "2026-02-17T12:00:00",
            "lessons": "List lesson", "actual_result": "List result",
        }]

        with (
            patch("a2a.cstp.dispatcher.load_all_decisions", AsyncMock(return_value=decs)),
            patch("a2a.cstp.deliberation_tracker.track_query"),
        ):
            from a2a.cstp.dispatcher import _handle_query_decisions

            result = await _handle_query_decisions(
                {"query": "", "includeDetail": True}, "agent",
            )
            d = result["decisions"][0]
            assert d.get("lessons") == "List lesson"
            assert d.get("actualResult") == "List result"

    @pytest.mark.asyncio
    async def test_keyword_path_includes_lessons(self) -> None:
        decs = [{
            "id": "kw1", "summary": "KW", "category": "process", "confidence": 0.7,
            "stakes": "medium", "status": "reviewed", "outcome": "partial",
            "created_at": "2026-02-17T12:00:00",
            "lessons": "KW lesson", "actual_result": "KW result",
        }]
        mock_bm25 = MagicMock()
        mock_bm25.search.return_value = [("kw1", 5.0)]

        with (
            patch("a2a.cstp.dispatcher.load_all_decisions", AsyncMock(return_value=decs)),
            patch("a2a.cstp.dispatcher.get_cached_index", return_value=mock_bm25),
            patch("a2a.cstp.deliberation_tracker.track_query"),
        ):
            from a2a.cstp.dispatcher import _handle_query_decisions

            result = await _handle_query_decisions(
                {"query": "kw", "retrievalMode": "keyword", "includeDetail": True}, "agent",
            )
            d = result["decisions"][0]
            assert d.get("lessons") == "KW lesson"
            assert d.get("actualResult") == "KW result"

    @pytest.mark.asyncio
    async def test_to_dict_round_trip(self) -> None:
        ds = DecisionSummary(
            id="rt1", title="RT", category="security", confidence=0.95,
            stakes="high", status="reviewed", outcome="success",
            date="2026-02-17", distance=0.05,
            lessons="RT lesson", actual_result="RT result",
        )
        d = ds.to_dict()
        assert d["lessons"] == "RT lesson"
        assert d["actualResult"] == "RT result"
        assert d["id"] == "rt1"
        assert d["outcome"] == "success"
