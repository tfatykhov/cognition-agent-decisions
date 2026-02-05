"""Unit tests for query_service.py."""

from unittest.mock import AsyncMock, patch

import pytest

from a2a.cstp.query_service import (
    QueryResult,
    _get_secrets_paths,
    _load_gemini_key,
    query_decisions,
)


class TestGetSecretsPaths:
    """Tests for _get_secrets_paths."""

    def test_default_paths(self) -> None:
        """Default paths should be returned."""
        paths = _get_secrets_paths()
        assert len(paths) >= 1

    def test_custom_paths_from_env(self, monkeypatch) -> None:
        """Custom paths from env should work."""
        monkeypatch.setenv("SECRETS_PATHS", "/custom/path:/another/path")
        # Force reimport to pick up env
        import importlib
        import a2a.cstp.query_service as qs
        importlib.reload(qs)

        paths = qs._get_secrets_paths()
        assert any("/custom/path" in str(p) for p in paths)


class TestLoadGeminiKey:
    """Tests for _load_gemini_key."""

    def test_from_env(self, monkeypatch) -> None:
        """Key from env should be returned."""
        monkeypatch.setenv("GEMINI_API_KEY", "test-key-from-env")
        # Clear cached key
        import a2a.cstp.query_service as qs
        qs.GEMINI_API_KEY = "test-key-from-env"

        key = _load_gemini_key()
        assert key == "test-key-from-env"

    def test_missing_key_raises(self, monkeypatch, tmp_path) -> None:
        """Missing key should raise ValueError."""
        monkeypatch.setenv("GEMINI_API_KEY", "")
        monkeypatch.setenv("SECRETS_PATHS", str(tmp_path))

        import importlib
        import a2a.cstp.query_service as qs
        qs.GEMINI_API_KEY = ""
        importlib.reload(qs)

        with pytest.raises(ValueError, match="GEMINI_API_KEY not found"):
            qs._load_gemini_key()


class TestQueryDecisions:
    """Tests for query_decisions function."""

    @pytest.mark.asyncio
    @patch("a2a.cstp.query_service._get_collection_id")
    async def test_collection_not_found(self, mock_get_coll: AsyncMock) -> None:
        """Missing collection should return error."""
        mock_get_coll.return_value = None

        response = await query_decisions("test query")

        assert response.error is not None
        assert "Collection not found" in response.error
        assert response.results == []

    @pytest.mark.asyncio
    @patch("a2a.cstp.query_service._async_request")
    @patch("a2a.cstp.query_service._generate_embedding")
    @patch("a2a.cstp.query_service._get_collection_id")
    async def test_successful_query(
        self,
        mock_get_coll: AsyncMock,
        mock_embed: AsyncMock,
        mock_request: AsyncMock,
    ) -> None:
        """Successful query should return results."""
        mock_get_coll.return_value = "coll-123"
        mock_embed.return_value = [0.1] * 768
        mock_request.return_value = (
            200,
            {
                "ids": [["id1", "id2"]],
                "documents": [["doc1", "doc2"]],
                "metadatas": [
                    [
                        {"title": "Decision 1", "category": "arch", "confidence": 0.9},
                        {"title": "Decision 2", "category": "process"},
                    ]
                ],
                "distances": [[0.1, 0.3]],
            },
        )

        response = await query_decisions("test query", n_results=2)

        assert response.error is None
        assert len(response.results) == 2
        assert response.results[0].title == "Decision 1"
        assert response.results[0].distance == 0.1
        assert response.results[1].title == "Decision 2"

    @pytest.mark.asyncio
    @patch("a2a.cstp.query_service._generate_embedding")
    @patch("a2a.cstp.query_service._get_collection_id")
    async def test_embedding_failure(
        self,
        mock_get_coll: AsyncMock,
        mock_embed: AsyncMock,
    ) -> None:
        """Embedding failure should return error."""
        mock_get_coll.return_value = "coll-123"
        mock_embed.side_effect = RuntimeError("API error")

        response = await query_decisions("test query")

        assert response.error is not None
        assert "Embedding generation failed" in response.error

    @pytest.mark.asyncio
    @patch("a2a.cstp.query_service._async_request")
    @patch("a2a.cstp.query_service._generate_embedding")
    @patch("a2a.cstp.query_service._get_collection_id")
    async def test_query_with_filters(
        self,
        mock_get_coll: AsyncMock,
        mock_embed: AsyncMock,
        mock_request: AsyncMock,
    ) -> None:
        """Filters should be passed to ChromaDB."""
        mock_get_coll.return_value = "coll-123"
        mock_embed.return_value = [0.1] * 768
        mock_request.return_value = (200, {"ids": [[]], "documents": [[]]})

        await query_decisions(
            "test",
            category="architecture",
            min_confidence=0.8,
            stakes=["high"],
        )

        # Check the where clause was passed
        call_args = mock_request.call_args
        payload = call_args[0][2]  # Third positional arg is data
        assert payload["where"]["category"] == "architecture"
        assert payload["where"]["confidence"] == {"$gte": 0.8}
        assert payload["where"]["stakes"] == {"$in": ["high"]}

    @pytest.mark.asyncio
    @patch("a2a.cstp.query_service._async_request")
    @patch("a2a.cstp.query_service._generate_embedding")
    @patch("a2a.cstp.query_service._get_collection_id")
    async def test_query_failure(
        self,
        mock_get_coll: AsyncMock,
        mock_embed: AsyncMock,
        mock_request: AsyncMock,
    ) -> None:
        """ChromaDB failure should return error."""
        mock_get_coll.return_value = "coll-123"
        mock_embed.return_value = [0.1] * 768
        mock_request.return_value = (500, {"error": "Internal server error"})

        response = await query_decisions("test query")

        assert response.error is not None
        assert "Query failed" in response.error


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
        """Project filter is included in ChromaDB where clause."""
        with (
            patch("a2a.cstp.query_service._get_collection_id", new_callable=AsyncMock) as mock_coll,
            patch("a2a.cstp.query_service._generate_embedding", new_callable=AsyncMock) as mock_embed,
            patch("a2a.cstp.query_service._async_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_coll.return_value = "test-collection-id"
            mock_embed.return_value = [0.1] * 768
            mock_req.return_value = (200, {
                "ids": [["id1"]],
                "documents": [["doc1"]],
                "metadatas": [[{
                    "category": "architecture",
                    "confidence": 0.8,
                    "stakes": "high",
                    "status": "reviewed",
                    "date": "2026-02-05",
                }]],
                "distances": [[0.1]],
            })

            await query_decisions(
                query="test query",
                project="owner/repo",
                feature="my-feature",
                pr=10,
            )

            # Check the where clause in the request
            call_args = mock_req.call_args
            payload = call_args[0][2]  # Third positional arg is payload
            where = payload.get("where", {})

            assert where.get("project") == "owner/repo"
            assert where.get("feature") == "my-feature"
            assert where.get("pr") == 10

    @pytest.mark.asyncio
    async def test_has_outcome_true_filters_reviewed(self) -> None:
        """has_outcome=True filters to reviewed status."""
        with (
            patch("a2a.cstp.query_service._get_collection_id", new_callable=AsyncMock) as mock_coll,
            patch("a2a.cstp.query_service._generate_embedding", new_callable=AsyncMock) as mock_embed,
            patch("a2a.cstp.query_service._async_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_coll.return_value = "test-collection-id"
            mock_embed.return_value = [0.1] * 768
            mock_req.return_value = (200, {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            })

            await query_decisions(
                query="test query",
                has_outcome=True,
            )

            call_args = mock_req.call_args
            payload = call_args[0][2]
            where = payload.get("where", {})

            assert where.get("status") == "reviewed"

    @pytest.mark.asyncio
    async def test_has_outcome_false_filters_pending(self) -> None:
        """has_outcome=False filters to pending status."""
        with (
            patch("a2a.cstp.query_service._get_collection_id", new_callable=AsyncMock) as mock_coll,
            patch("a2a.cstp.query_service._generate_embedding", new_callable=AsyncMock) as mock_embed,
            patch("a2a.cstp.query_service._async_request", new_callable=AsyncMock) as mock_req,
        ):
            mock_coll.return_value = "test-collection-id"
            mock_embed.return_value = [0.1] * 768
            mock_req.return_value = (200, {
                "ids": [[]],
                "documents": [[]],
                "metadatas": [[]],
                "distances": [[]],
            })

            await query_decisions(
                query="test query",
                has_outcome=False,
            )

            call_args = mock_req.call_args
            payload = call_args[0][2]
            where = payload.get("where", {})

            assert where.get("status") == "pending"

