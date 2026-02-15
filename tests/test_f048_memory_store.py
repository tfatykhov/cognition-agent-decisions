"""Tests for F048: MemoryStore in-memory VectorStore backend."""

import pytest

from a2a.cstp.vectordb.memory import MemoryStore, _cosine_distance, _matches_where


class TestMemoryStoreBasic:
    """Basic CRUD operations."""

    @pytest.mark.asyncio
    async def test_initialize(self) -> None:
        store = MemoryStore()
        await store.initialize()
        coll_id = await store.get_collection_id()
        assert coll_id == "memory-collection"

    @pytest.mark.asyncio
    async def test_upsert_and_count(self) -> None:
        store = MemoryStore()
        await store.initialize()
        result = await store.upsert("doc1", "text", [0.1, 0.2], {"k": "v"})
        assert result is True
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_upsert_overwrites(self) -> None:
        store = MemoryStore()
        await store.initialize()
        await store.upsert("doc1", "old text", [0.1, 0.2], {"version": "1"})
        await store.upsert("doc1", "new text", [0.3, 0.4], {"version": "2"})
        assert await store.count() == 1
        results = await store.query([0.3, 0.4], n_results=1)
        assert results[0].document == "new text"

    @pytest.mark.asyncio
    async def test_delete(self) -> None:
        store = MemoryStore()
        await store.initialize()
        await store.upsert("doc1", "text1", [0.1, 0.2], {})
        await store.upsert("doc2", "text2", [0.3, 0.4], {})
        result = await store.delete(["doc1"])
        assert result is True
        assert await store.count() == 1

    @pytest.mark.asyncio
    async def test_reset(self) -> None:
        store = MemoryStore()
        await store.initialize()
        await store.upsert("doc1", "text", [0.1, 0.2], {})
        result = await store.reset()
        assert result is True
        assert await store.count() == 0

    @pytest.mark.asyncio
    async def test_collection_id_before_init(self) -> None:
        store = MemoryStore()
        coll_id = await store.get_collection_id()
        assert coll_id is None


class TestMemoryStoreQuery:
    """Similarity search tests."""

    @pytest.mark.asyncio
    async def test_returns_nearest(self) -> None:
        store = MemoryStore()
        await store.initialize()
        await store.upsert("near", "near doc", [1.0, 0.0], {})
        await store.upsert("far", "far doc", [0.0, 1.0], {})

        results = await store.query([1.0, 0.0], n_results=2)
        assert results[0].id == "near"
        assert results[0].distance < results[1].distance

    @pytest.mark.asyncio
    async def test_n_results_limit(self) -> None:
        store = MemoryStore()
        await store.initialize()
        for i in range(5):
            await store.upsert(f"doc{i}", f"text{i}", [float(i) / 5] * 2, {})

        results = await store.query([0.5, 0.5], n_results=2)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_empty_store(self) -> None:
        store = MemoryStore()
        await store.initialize()
        results = await store.query([0.1, 0.2], n_results=5)
        assert results == []


class TestWhereClauseMatching:
    """Tests for ChromaDB-style where clause matching."""

    def test_exact_match(self) -> None:
        assert _matches_where({"category": "arch"}, {"category": "arch"})
        assert not _matches_where({"category": "arch"}, {"category": "process"})

    def test_gte(self) -> None:
        assert _matches_where({"confidence": 0.9}, {"confidence": {"$gte": 0.8}})
        assert not _matches_where({"confidence": 0.5}, {"confidence": {"$gte": 0.8}})

    def test_lte(self) -> None:
        assert _matches_where({"confidence": 0.5}, {"confidence": {"$lte": 0.8}})
        assert not _matches_where({"confidence": 0.9}, {"confidence": {"$lte": 0.8}})

    def test_in(self) -> None:
        assert _matches_where({"stakes": "high"}, {"stakes": {"$in": ["high", "critical"]}})
        assert not _matches_where({"stakes": "low"}, {"stakes": {"$in": ["high", "critical"]}})

    def test_contains_string(self) -> None:
        assert _matches_where({"tags": "python,testing"}, {"tags": {"$contains": "python"}})
        assert not _matches_where({"tags": "python,testing"}, {"tags": {"$contains": "java"}})

    def test_or(self) -> None:
        clause = {"$or": [
            {"tags": {"$contains": "python"}},
            {"tags": {"$contains": "java"}},
        ]}
        assert _matches_where({"tags": "python,testing"}, clause)
        assert _matches_where({"tags": "java,spring"}, clause)
        assert not _matches_where({"tags": "rust,cargo"}, clause)

    def test_and(self) -> None:
        clause = {"$and": [
            {"category": "arch"},
            {"confidence": {"$gte": 0.8}},
        ]}
        assert _matches_where({"category": "arch", "confidence": 0.9}, clause)
        assert not _matches_where({"category": "arch", "confidence": 0.5}, clause)

    def test_missing_key(self) -> None:
        assert not _matches_where({}, {"category": "arch"})
        assert not _matches_where({}, {"confidence": {"$gte": 0.5}})

    def test_ne(self) -> None:
        assert _matches_where({"status": "pending"}, {"status": {"$ne": "reviewed"}})
        assert not _matches_where({"status": "reviewed"}, {"status": {"$ne": "reviewed"}})

    @pytest.mark.asyncio
    async def test_where_in_query(self) -> None:
        """Where clause applied during query."""
        store = MemoryStore()
        await store.initialize()

        await store.upsert("d1", "text", [0.1, 0.2], {"category": "arch", "status": "pending"})
        await store.upsert("d2", "text", [0.1, 0.2], {"category": "process", "status": "pending"})

        results = await store.query(
            [0.1, 0.2], n_results=10,
            where={"category": "arch"},
        )
        assert len(results) == 1
        assert results[0].id == "d1"


class TestCosineDistance:
    """Tests for cosine distance computation."""

    def test_identical_vectors(self) -> None:
        assert _cosine_distance([1.0, 0.0], [1.0, 0.0]) == pytest.approx(0.0)

    def test_orthogonal_vectors(self) -> None:
        assert _cosine_distance([1.0, 0.0], [0.0, 1.0]) == pytest.approx(1.0)

    def test_opposite_vectors(self) -> None:
        assert _cosine_distance([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(2.0)

    def test_mismatched_lengths(self) -> None:
        assert _cosine_distance([1.0], [1.0, 0.0]) == 1.0

    def test_zero_vector(self) -> None:
        assert _cosine_distance([0.0, 0.0], [1.0, 0.0]) == 1.0
