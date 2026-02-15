"""Factory for vector store backends.

Provides singleton management and test injection for VectorStore instances.
"""

import os

from . import VectorStore

_store: VectorStore | None = None


def create_vector_store() -> VectorStore:
    """Create a VectorStore based on VECTOR_BACKEND env var.

    Supported values:
        - "chromadb" (default): ChromaDB via HTTP API v2.
        - "memory": In-memory store for testing.
    """
    backend = os.getenv("VECTOR_BACKEND", "chromadb")
    match backend:
        case "chromadb":
            from .chromadb import ChromaDBStore

            return ChromaDBStore()
        case "memory":
            from .memory import MemoryStore

            return MemoryStore()
        case _:
            msg = f"Unknown vector backend: {backend}"
            raise ValueError(msg)


def get_vector_store() -> VectorStore:
    """Get or create the singleton VectorStore."""
    global _store
    if _store is None:
        _store = create_vector_store()
    return _store


def set_vector_store(store: VectorStore | None) -> None:
    """Set the VectorStore instance (for testing)."""
    global _store
    _store = store
