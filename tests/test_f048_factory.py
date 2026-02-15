"""Tests for F048: VectorStore and EmbeddingProvider factories."""

import pytest

from a2a.cstp.embeddings.factory import (
    create_embedding_provider,
    get_embedding_provider,
    set_embedding_provider,
)
from a2a.cstp.embeddings.gemini import GeminiEmbeddings
from a2a.cstp.vectordb.chromadb import ChromaDBStore
from a2a.cstp.vectordb.factory import (
    create_vector_store,
    get_vector_store,
    set_vector_store,
)
from a2a.cstp.vectordb.memory import MemoryStore


@pytest.fixture(autouse=True)
def _reset():
    """Reset singletons after each test."""
    yield
    set_vector_store(None)
    set_embedding_provider(None)


class TestVectorStoreFactory:
    """Tests for VectorStore factory functions."""

    def test_default_creates_chromadb(self, monkeypatch) -> None:
        """Default VECTOR_BACKEND creates ChromaDBStore."""
        monkeypatch.delenv("VECTOR_BACKEND", raising=False)
        store = create_vector_store()
        assert isinstance(store, ChromaDBStore)

    def test_memory_backend(self, monkeypatch) -> None:
        """VECTOR_BACKEND=memory creates MemoryStore."""
        monkeypatch.setenv("VECTOR_BACKEND", "memory")
        store = create_vector_store()
        assert isinstance(store, MemoryStore)

    def test_unknown_backend_raises(self, monkeypatch) -> None:
        """Unknown backend raises ValueError."""
        monkeypatch.setenv("VECTOR_BACKEND", "invalid")
        with pytest.raises(ValueError, match="Unknown vector backend"):
            create_vector_store()

    def test_singleton(self, monkeypatch) -> None:
        """get_vector_store returns the same instance."""
        monkeypatch.setenv("VECTOR_BACKEND", "memory")
        store1 = get_vector_store()
        store2 = get_vector_store()
        assert store1 is store2

    def test_set_and_get(self) -> None:
        """set_vector_store injects a custom instance."""
        custom_store = MemoryStore()
        set_vector_store(custom_store)
        assert get_vector_store() is custom_store

    def test_set_none_clears(self, monkeypatch) -> None:
        """set_vector_store(None) clears the singleton."""
        monkeypatch.setenv("VECTOR_BACKEND", "memory")
        set_vector_store(MemoryStore())
        set_vector_store(None)
        # Next get should create a new instance
        store = get_vector_store()
        assert isinstance(store, MemoryStore)


class TestEmbeddingProviderFactory:
    """Tests for EmbeddingProvider factory functions."""

    def test_default_creates_gemini(self, monkeypatch) -> None:
        """Default EMBEDDING_PROVIDER creates GeminiEmbeddings."""
        monkeypatch.delenv("EMBEDDING_PROVIDER", raising=False)
        monkeypatch.setenv("GEMINI_API_KEY", "test-key")
        provider = create_embedding_provider()
        assert isinstance(provider, GeminiEmbeddings)

    def test_unknown_provider_raises(self, monkeypatch) -> None:
        """Unknown provider raises ValueError."""
        monkeypatch.setenv("EMBEDDING_PROVIDER", "invalid")
        with pytest.raises(ValueError, match="Unknown embedding provider"):
            create_embedding_provider()

    def test_set_and_get(self) -> None:
        """set_embedding_provider injects a custom instance."""
        from unittest.mock import AsyncMock

        from a2a.cstp.embeddings import EmbeddingProvider

        mock = AsyncMock(spec=EmbeddingProvider)
        set_embedding_provider(mock)
        assert get_embedding_provider() is mock
