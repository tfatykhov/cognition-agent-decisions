"""Unit tests for query_service.py.

Tests use MemoryStore and mock EmbeddingProvider instead of
patching internal ChromaDB/Gemini functions.
"""

from unittest.mock import AsyncMock

import pytest

from a2a.cstp.embeddings import EmbeddingProvider
from a2a.cstp.embeddings.factory import set_embedding_provider
from a2a.cstp.query_service import QueryResult, query_decisions
from a2a.cstp.vectordb.factory import set_vector_store
from a2a.cstp.vectordb.memory import MemoryStore


def _mock_provider(embedding: list[float] | None = None) -> AsyncMock:
    """Create a mock EmbeddingProvider."""
    mock = AsyncMock(spec=EmbeddingProvider)
    mock.embed.return_value = embedding or [0.1] * 768
    mock.dimensions = 768
    mock.model_name = "test-model"
    mock.max_length = 8000
    return mock


@pytest.fixture(autouse=True)
def _reset_backends():
    """Reset vector store and embedding provider after each test."""
    yield
    set_vector_store(None)
    set_embedding_provider(None)


class TestQueryDecisions:
    """Tests for query_decisions function."""

    @pytest.mark.asyncio
    async def test_collection_not_found(self) -> None:
        """Missing collection should return error."""
        store = MemoryStore()
        # Don't initialize — no collection exists, no docs
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions("test query")

        assert response.error is not None
        assert "Collection not found" in response.error
        assert response.results == []

    @pytest.mark.asyncio
    async def test_successful_query(self) -> None:
        """Successful query should return results."""
        store = MemoryStore()
        await store.initialize()

        # Seed with test data
        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "Decision 1", "category": "arch", "confidence": 0.9,
             "status": "pending", "date": "2026-01-20"},
        )
        await store.upsert(
            "id2", "doc2", [0.2] * 768,
            {"title": "Decision 2", "category": "process",
             "status": "pending", "date": "2026-01-21"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions("test query", n_results=2)

        assert response.error is None
        assert len(response.results) == 2
        assert response.results[0].title == "Decision 1"

    @pytest.mark.asyncio
    async def test_embedding_failure(self) -> None:
        """Embedding failure should return error."""
        store = MemoryStore()
        await store.initialize()
        set_vector_store(store)

        mock_provider = _mock_provider()
        mock_provider.embed.side_effect = RuntimeError("API error")
        set_embedding_provider(mock_provider)

        response = await query_decisions("test query")

        assert response.error is not None
        assert "Embedding generation failed" in response.error

    @pytest.mark.asyncio
    async def test_query_with_category_filter(self) -> None:
        """Category filter should restrict results."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "Arch Decision", "category": "architecture",
             "confidence": 0.9, "stakes": "high", "status": "pending",
             "date": "2026-01-20"},
        )
        await store.upsert(
            "id2", "doc2", [0.15] * 768,
            {"title": "Process Decision", "category": "process",
             "confidence": 0.7, "stakes": "medium", "status": "pending",
             "date": "2026-01-21"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions(
            "test", category="architecture",
        )

        assert response.error is None
        assert len(response.results) == 1
        assert response.results[0].category == "architecture"

    @pytest.mark.asyncio
    async def test_query_with_stakes_filter(self) -> None:
        """Stakes filter should restrict results."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "High stakes", "category": "arch",
             "stakes": "high", "status": "pending", "date": "2026-01-20"},
        )
        await store.upsert(
            "id2", "doc2", [0.15] * 768,
            {"title": "Low stakes", "category": "arch",
             "stakes": "low", "status": "pending", "date": "2026-01-21"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions("test", stakes=["high"])

        assert response.error is None
        assert len(response.results) == 1
        assert response.results[0].stakes == "high"

    @pytest.mark.asyncio
    async def test_empty_results(self) -> None:
        """Empty store should return empty results."""
        store = MemoryStore()
        await store.initialize()
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions("test query")

        assert response.error is None
        assert response.results == []


class TestQueryResult:
    """Tests for QueryResult dataclass."""

    def test_creation(self) -> None:
        """QueryResult should be creatable."""
        result = QueryResult(
            id="abc12345",
            title="Test",
            category="arch",
            confidence=0.9,
            stakes="high",
            status="decided",
            outcome=None,
            date="2026-01-20",
            distance=0.23,
        )
        assert result.id == "abc12345"
        assert result.confidence == 0.9

    def test_with_reason_types(self) -> None:
        """QueryResult with reason types should work."""
        result = QueryResult(
            id="abc12345",
            title="Test",
            category="arch",
            confidence=0.9,
            stakes="high",
            status="decided",
            outcome="success",
            date="2026-01-20",
            distance=0.23,
            reason_types=["pattern", "analysis"],
        )
        assert result.reason_types == ["pattern", "analysis"]


class TestQueryFiltersProjectContext:
    """Tests for project context filters in QueryFilters."""

    def test_parses_project_filters(self) -> None:
        """Parses project context filters."""
        from a2a.cstp.models import QueryFilters

        data = {
            "category": "architecture",
            "project": "owner/repo",
            "feature": "cstp-v2",
            "pr": 42,
            "hasOutcome": True,
        }
        filters = QueryFilters.from_dict(data)

        assert filters.project == "owner/repo"
        assert filters.feature == "cstp-v2"
        assert filters.pr == 42
        assert filters.has_outcome is True

    def test_none_when_absent(self) -> None:
        """Project filters are None when not provided."""
        from a2a.cstp.models import QueryFilters

        data = {"category": "architecture"}
        filters = QueryFilters.from_dict(data)

        assert filters.project is None
        assert filters.feature is None
        assert filters.pr is None
        assert filters.has_outcome is None


class TestQueryDecisionsWithProjectFilters:
    """Tests for project context filters in query_decisions."""

    @pytest.mark.asyncio
    async def test_project_filter_in_where_clause(self) -> None:
        """Project filter restricts results to matching project."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "My decision", "category": "architecture",
             "confidence": 0.8, "stakes": "high", "status": "reviewed",
             "date": "2026-02-05", "project": "owner/repo",
             "feature": "my-feature", "pr": 10},
        )
        await store.upsert(
            "id2", "doc2", [0.15] * 768,
            {"title": "Other decision", "category": "architecture",
             "confidence": 0.7, "status": "pending", "date": "2026-02-06",
             "project": "other/repo"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions(
            query="test query",
            project="owner/repo",
            feature="my-feature",
            pr=10,
        )

        assert response.error is None
        assert len(response.results) == 1
        assert response.results[0].id == "id1"

    @pytest.mark.asyncio
    async def test_has_outcome_true_filters_reviewed(self) -> None:
        """has_outcome=True filters to reviewed status."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "Reviewed", "category": "arch", "status": "reviewed",
             "date": "2026-02-05"},
        )
        await store.upsert(
            "id2", "doc2", [0.15] * 768,
            {"title": "Pending", "category": "arch", "status": "pending",
             "date": "2026-02-06"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions(query="test query", has_outcome=True)

        assert response.error is None
        assert all(r.status == "reviewed" for r in response.results)

    @pytest.mark.asyncio
    async def test_has_outcome_false_filters_pending(self) -> None:
        """has_outcome=False filters to pending status."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert(
            "id1", "doc1", [0.1] * 768,
            {"title": "Reviewed", "category": "arch", "status": "reviewed",
             "date": "2026-02-05"},
        )
        await store.upsert(
            "id2", "doc2", [0.15] * 768,
            {"title": "Pending", "category": "arch", "status": "pending",
             "date": "2026-02-06"},
        )
        set_vector_store(store)
        set_embedding_provider(_mock_provider())

        response = await query_decisions(query="test query", has_outcome=False)

        assert response.error is None
        assert all(r.status == "pending" for r in response.results)
