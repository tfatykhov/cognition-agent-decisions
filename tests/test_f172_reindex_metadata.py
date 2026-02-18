"""Tests for issue #172: reindex_decisions() delegates to reindex_decision().

Verifies that the bulk reindex path produces the same rich metadata and embedding
text as the single-decision reindex_decision() path in decision_service.

Covers:
1. Full metadata fields after reindex (bridge_json, tags, pattern, reasons_json,
   reason_types, outcome, lessons, actual_result, agent, path)
2. Rich embedding text includes bridge, tags, pattern, reasons, outcome, lessons
3. Error handling - one bad decision doesn't break entire reindex
4. Progress tracking (indexed/errors counts)
5. Empty decisions list handling
6. Reset failure handling
7. Decisions without id counted as errors
8. Delegation verification (reindex_decision called with correct args)
9. store.reset() called before loop
10. get_embedding_provider no longer called from reindex_service
11. Integration: query returns all metadata after reindex
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
    _mock_mcp = MagicMock()
    sys.modules["mcp"] = _mock_mcp
    sys.modules["mcp.server"] = _mock_mcp
    sys.modules["mcp.server.stdio"] = _mock_mcp
    sys.modules["mcp.server.streamable_http_manager"] = _mock_mcp
    sys.modules["mcp.types"] = _mock_mcp

import pytest  # noqa: E402

from a2a.cstp.reindex_service import reindex_decisions  # noqa: E402
from a2a.cstp.vectordb.memory import MemoryStore  # noqa: E402


def _make_rich_decision() -> dict:
    """Build a decision dict with ALL metadata fields populated."""
    return {
        "id": "abc12345",
        "summary": "Use PostgreSQL for production",
        "decision": "Use PostgreSQL for production",
        "category": "architecture",
        "confidence": 0.9,
        "stakes": "high",
        "status": "reviewed",
        "date": "2026-02-18T12:00:00",
        "outcome": "success",
        "lessons": "Always benchmark before choosing a database",
        "actual_result": "Deployed with zero downtime",
        "context": "Choosing primary database for production",
        "recorded_by": "test-agent",
        "tags": ["database", "infrastructure"],
        "pattern": "Benchmark before committing to infrastructure choices",
        "reasons": [
            {"type": "analysis", "text": "ACID compliance needed"},
            {"type": "empirical", "text": "Benchmarked PostgreSQL vs MySQL"},
        ],
        "bridge": {
            "structure": "SQL database with ACID guarantees",
            "function": "Reliable data storage for financial transactions",
        },
        "_file": "/decisions/2026/02/2026-02-18-decision-abc12345.yaml",
    }


def _make_minimal_decision() -> dict:
    """Build a minimal decision dict with only required fields."""
    return {
        "id": "min00001",
        "summary": "Minimal decision",
        "category": "process",
        "confidence": 0.7,
        "stakes": "low",
        "status": "pending",
        "date": "2026-02-18",
    }


def _setup_mocks() -> tuple[MemoryStore, AsyncMock]:
    """Create a MemoryStore and mock EmbeddingProvider for test injection."""
    store = MemoryStore()
    store._initialized = True
    mock_provider = AsyncMock()
    mock_provider.embed = AsyncMock(return_value=[0.1] * 768)
    return store, mock_provider


# ---------------------------------------------------------------------------
# 1. Full metadata fields after reindex
# ---------------------------------------------------------------------------


class TestReindexProducesFullMetadata:
    """Verify reindex_decisions() produces ALL metadata fields via delegation."""

    @pytest.mark.asyncio
    async def test_reindex_produces_bridge_json(self) -> None:
        """bridge_json metadata is present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 1
        meta = store._docs["abc12345"]["metadata"]
        bridge = json.loads(meta["bridge_json"])
        assert bridge["structure"] == "SQL database with ACID guarantees"
        assert bridge["function"] == "Reliable data storage for financial transactions"

    @pytest.mark.asyncio
    async def test_reindex_produces_tags(self) -> None:
        """tags metadata is present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert "database" in meta["tags"]
        assert "infrastructure" in meta["tags"]

    @pytest.mark.asyncio
    async def test_reindex_produces_pattern(self) -> None:
        """pattern metadata is present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert meta["pattern"] == "Benchmark before committing to infrastructure choices"

    @pytest.mark.asyncio
    async def test_reindex_produces_reasons_json_and_types(self) -> None:
        """reasons_json and reason_types metadata are present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        reasons = json.loads(meta["reasons_json"])
        assert len(reasons) == 2
        assert any(r["type"] == "analysis" for r in reasons)
        assert any(r["type"] == "empirical" for r in reasons)
        assert "analysis" in meta["reason_types"]
        assert "empirical" in meta["reason_types"]

    @pytest.mark.asyncio
    async def test_reindex_produces_outcome(self) -> None:
        """outcome metadata is present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert meta["outcome"] == "success"

    @pytest.mark.asyncio
    async def test_reindex_produces_lessons_and_actual_result(self) -> None:
        """lessons and actual_result metadata are present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert meta["lessons"] == "Always benchmark before choosing a database"
        assert meta["actual_result"] == "Deployed with zero downtime"

    @pytest.mark.asyncio
    async def test_reindex_produces_agent(self) -> None:
        """agent metadata is present after reindex (from recorded_by)."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert meta["agent"] == "test-agent"

    @pytest.mark.asyncio
    async def test_reindex_produces_path(self) -> None:
        """path metadata is present after reindex."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        assert meta["path"] == "/decisions/2026/02/2026-02-18-decision-abc12345.yaml"

    @pytest.mark.asyncio
    async def test_reindex_all_metadata_fields_present(self) -> None:
        """All expected metadata fields are present in a single assertion."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        meta = store._docs["abc12345"]["metadata"]
        expected_keys = {
            "bridge_json", "tags", "pattern", "reasons_json", "reason_types",
            "outcome", "lessons", "actual_result", "agent", "path",
            "title", "category", "stakes", "confidence", "date", "status",
        }
        assert expected_keys.issubset(set(meta.keys())), (
            f"Missing metadata keys: {expected_keys - set(meta.keys())}"
        )


# ---------------------------------------------------------------------------
# 2. Rich embedding text
# ---------------------------------------------------------------------------


class TestReindexRichEmbeddingText:
    """Verify embedding text is rich (includes bridge, tags, pattern, etc.)."""

    @pytest.mark.asyncio
    async def test_embedding_text_includes_bridge(self) -> None:
        """Embedding text includes bridge structure and function."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        doc_text = store._docs["abc12345"]["document"]
        assert "Structure: SQL database with ACID guarantees" in doc_text
        assert "Function: Reliable data storage for financial transactions" in doc_text

    @pytest.mark.asyncio
    async def test_embedding_text_includes_tags(self) -> None:
        """Embedding text includes tags."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        doc_text = store._docs["abc12345"]["document"]
        assert "Tags:" in doc_text
        assert "database" in doc_text
        assert "infrastructure" in doc_text

    @pytest.mark.asyncio
    async def test_embedding_text_includes_pattern(self) -> None:
        """Embedding text includes pattern."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        doc_text = store._docs["abc12345"]["document"]
        assert "Pattern: Benchmark before committing to infrastructure choices" in doc_text

    @pytest.mark.asyncio
    async def test_embedding_text_includes_reasons(self) -> None:
        """Embedding text includes reasons."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        doc_text = store._docs["abc12345"]["document"]
        assert "Reasons:" in doc_text
        assert "ACID compliance needed" in doc_text

    @pytest.mark.asyncio
    async def test_embedding_text_includes_outcome_and_lessons(self) -> None:
        """Embedding text includes outcome and lessons."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        doc_text = store._docs["abc12345"]["document"]
        assert "Outcome: success" in doc_text
        assert "Lessons: Always benchmark before choosing a database" in doc_text


# ---------------------------------------------------------------------------
# 3. Error handling
# ---------------------------------------------------------------------------


class TestReindexErrorHandling:
    """Verify one bad decision doesn't break entire reindex."""

    @pytest.mark.asyncio
    async def test_bad_decision_does_not_break_batch(self) -> None:
        """One decision that causes an exception doesn't stop the others."""
        store, provider = _setup_mocks()
        good_decision = _make_rich_decision()
        bad_decision = {"id": "bad00001", "summary": "Bad decision"}

        # Make embedding fail for the bad decision only
        async def selective_embed(text: str) -> list[float]:
            if "Bad decision" in text:
                raise RuntimeError("Embedding generation failed")
            return [0.1] * 768

        provider.embed = selective_embed

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[bad_decision, good_decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 1
        assert result.errors == 1
        assert "abc12345" in store._docs

    @pytest.mark.asyncio
    async def test_decision_without_id_counted_as_error(self) -> None:
        """Decisions missing an id field are counted as errors."""
        store, provider = _setup_mocks()
        no_id_decision = {"summary": "No id here", "category": "process"}

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[no_id_decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 0
        assert result.errors == 1

    @pytest.mark.asyncio
    async def test_reindex_decision_returning_false_counted_as_error(self) -> None:
        """If reindex_decision returns False, it's counted as an error."""
        store, provider = _setup_mocks()
        decision = _make_minimal_decision()

        # Make upsert return False to simulate indexing failure
        async def failing_upsert(*args, **kwargs) -> bool:
            return False

        store.upsert = failing_upsert  # type: ignore[assignment]

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 0
        assert result.errors == 1


# ---------------------------------------------------------------------------
# 4. Progress tracking
# ---------------------------------------------------------------------------


class TestReindexProgressTracking:
    """Verify indexed/errors counts and result fields."""

    @pytest.mark.asyncio
    async def test_multiple_decisions_counted_correctly(self) -> None:
        """Multiple successful decisions are all counted."""
        store, provider = _setup_mocks()
        decisions = [
            {**_make_rich_decision(), "id": f"dec{i:05d}"} for i in range(5)
        ]

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=decisions,
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 5
        assert result.errors == 0
        assert result.duration_ms >= 0
        assert "5" in result.message
        assert len(store._docs) == 5

    @pytest.mark.asyncio
    async def test_result_to_dict_format(self) -> None:
        """ReindexResult.to_dict() produces correct camelCase keys."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        d = result.to_dict()
        assert "decisionsIndexed" in d
        assert "durationMs" in d
        assert d["success"] is True
        assert d["decisionsIndexed"] == 1
        assert d["errors"] == 0


# ---------------------------------------------------------------------------
# 5. Empty decisions list
# ---------------------------------------------------------------------------


class TestReindexEmptyDecisions:
    """Verify behavior when no decisions are found."""

    @pytest.mark.asyncio
    async def test_empty_decisions_returns_zero_indexed(self) -> None:
        """Empty decision list returns success with 0 indexed."""
        store, provider = _setup_mocks()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[],
            )),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 0
        assert result.errors == 0
        assert "No decisions found" in result.message


# ---------------------------------------------------------------------------
# 6. Reset failure
# ---------------------------------------------------------------------------


class TestReindexResetFailure:
    """Verify behavior when vector store reset fails."""

    @pytest.mark.asyncio
    async def test_reset_failure_returns_error(self) -> None:
        """If store.reset() returns False, reindex fails immediately."""
        mock_store = AsyncMock()
        mock_store.reset = AsyncMock(return_value=False)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=mock_store),
        ):
            result = await reindex_decisions()

        assert result.success is False
        assert result.decisions_indexed == 0
        assert "Failed to reset" in result.message


# ---------------------------------------------------------------------------
# 7. Minimal decision (sparse fields) still works
# ---------------------------------------------------------------------------


class TestReindexMinimalDecision:
    """Verify that minimal decisions without optional fields still index."""

    @pytest.mark.asyncio
    async def test_minimal_decision_indexes_successfully(self) -> None:
        """Minimal decision with only required fields indexes without error."""
        store, provider = _setup_mocks()
        decision = _make_minimal_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 1
        assert result.errors == 0
        meta = store._docs["min00001"]["metadata"]
        assert meta["category"] == "process"
        assert meta["title"] == "Minimal decision"
        # Optional fields should NOT be present when not set
        assert "bridge_json" not in meta
        assert "lessons" not in meta
        assert "actual_result" not in meta
        assert "agent" not in meta


# ---------------------------------------------------------------------------
# 8. Delegation verification (architect spec #1)
# ---------------------------------------------------------------------------


class TestReindexDelegation:
    """Verify reindex_decisions() delegates to reindex_decision() with correct args."""

    @pytest.mark.asyncio
    async def test_reindex_decision_called_with_correct_args(self) -> None:
        """reindex_decision is called with (decision_id, full_dict, file_path)."""
        store = MemoryStore()
        store._initialized = True
        decision = _make_rich_decision()
        mock_reindex = AsyncMock(return_value=True)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.reindex_service.reindex_decision", mock_reindex),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert result.decisions_indexed == 1
        mock_reindex.assert_called_once_with(
            "abc12345",
            decision,
            "/decisions/2026/02/2026-02-18-decision-abc12345.yaml",
        )

    @pytest.mark.asyncio
    async def test_reindex_decision_called_per_decision(self) -> None:
        """reindex_decision is called once per decision in the list."""
        store = MemoryStore()
        store._initialized = True
        decisions = [
            {**_make_rich_decision(), "id": f"id{i:06d}", "_file": f"/path/{i}.yaml"}
            for i in range(3)
        ]
        mock_reindex = AsyncMock(return_value=True)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=decisions,
            )),
            patch("a2a.cstp.reindex_service.reindex_decision", mock_reindex),
        ):
            result = await reindex_decisions()

        assert result.decisions_indexed == 3
        assert mock_reindex.call_count == 3
        # Verify each call got the correct id and file path
        for i, call in enumerate(mock_reindex.call_args_list):
            assert call.args[0] == f"id{i:06d}"
            assert call.args[2] == f"/path/{i}.yaml"

    @pytest.mark.asyncio
    async def test_file_path_from_decision_underscore_file(self) -> None:
        """File path passed to reindex_decision comes from decision['_file']."""
        store = MemoryStore()
        store._initialized = True
        decision = _make_minimal_decision()
        decision["_file"] = "/custom/path/to/decision.yaml"
        mock_reindex = AsyncMock(return_value=True)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.reindex_service.reindex_decision", mock_reindex),
        ):
            await reindex_decisions()

        assert mock_reindex.call_args.args[2] == "/custom/path/to/decision.yaml"

    @pytest.mark.asyncio
    async def test_missing_file_path_passes_empty_string(self) -> None:
        """When _file is absent, empty string is passed as file_path."""
        store = MemoryStore()
        store._initialized = True
        decision = _make_minimal_decision()
        # No _file key
        mock_reindex = AsyncMock(return_value=True)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.reindex_service.reindex_decision", mock_reindex),
        ):
            await reindex_decisions()

        assert mock_reindex.call_args.args[2] == ""


# ---------------------------------------------------------------------------
# 9. store.reset() called before loop (architect spec #4)
# ---------------------------------------------------------------------------


class TestReindexResetCalledFirst:
    """Verify store.reset() is called before the delegation loop."""

    @pytest.mark.asyncio
    async def test_reset_called_before_reindex_decision(self) -> None:
        """store.reset() is called, and load_all_decisions comes after."""
        call_order: list[str] = []
        mock_store = AsyncMock()

        async def track_reset() -> bool:
            call_order.append("reset")
            return True

        async def track_load() -> list[dict]:
            call_order.append("load")
            return [_make_rich_decision()]

        mock_store.reset = track_reset
        mock_reindex = AsyncMock(side_effect=lambda *a: call_order.append("reindex") or True)

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=mock_store),
            patch("a2a.cstp.reindex_service.load_all_decisions", track_load),
            patch("a2a.cstp.reindex_service.reindex_decision", mock_reindex),
        ):
            result = await reindex_decisions()

        assert result.success is True
        assert call_order == ["reset", "load", "reindex"]


# ---------------------------------------------------------------------------
# 10. get_embedding_provider no longer called from reindex_service (spec #5)
# ---------------------------------------------------------------------------


class TestReindexNoDirectEmbeddingProvider:
    """Verify reindex_service no longer imports or calls get_embedding_provider."""

    def test_reindex_service_does_not_import_embedding_provider(self) -> None:
        """reindex_service module does not import get_embedding_provider."""
        import a2a.cstp.reindex_service as mod
        # The module should not have get_embedding_provider in its namespace
        assert not hasattr(mod, "get_embedding_provider"), (
            "reindex_service should not import get_embedding_provider — "
            "embedding is handled by the delegated reindex_decision()"
        )


# ---------------------------------------------------------------------------
# 11. Integration: query returns metadata after reindex (architect spec #6)
# ---------------------------------------------------------------------------


class TestReindexQueryIntegration:
    """After reindex, verify query_decisions returns all metadata fields."""

    @pytest.mark.asyncio
    async def test_query_returns_metadata_after_reindex(self) -> None:
        """query_decisions returns outcome, lessons, tags, pattern, bridge_json."""
        store, provider = _setup_mocks()
        decision = _make_rich_decision()

        with (
            patch("a2a.cstp.reindex_service.get_vector_store", return_value=store),
            patch("a2a.cstp.reindex_service.load_all_decisions", AsyncMock(
                return_value=[decision],
            )),
            patch("a2a.cstp.decision_service.get_vector_store", return_value=store),
            patch("a2a.cstp.decision_service.get_embedding_provider", return_value=provider),
        ):
            await reindex_decisions()

        # Now query the store using the query_service path
        with (
            patch("a2a.cstp.query_service.get_vector_store", return_value=store),
            patch("a2a.cstp.query_service.get_embedding_provider", return_value=provider),
        ):
            from a2a.cstp.query_service import query_decisions
            resp = await query_decisions("PostgreSQL database", n_results=5)

        assert not resp.error
        assert len(resp.results) == 1
        r = resp.results[0]
        assert r.outcome == "success"
        assert r.lessons == "Always benchmark before choosing a database"
        assert r.actual_result == "Deployed with zero downtime"
        assert r.reason_types is not None
        assert "analysis" in r.reason_types
        assert "empirical" in r.reason_types
        assert r.reasons is not None
        assert len(r.reasons) == 2
