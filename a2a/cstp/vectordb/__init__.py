"""Vector store abstraction layer for CSTP.

Defines the VectorStore ABC and VectorResult dataclass that all
vector database backends must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class VectorResult:
    """Single result from vector similarity search."""

    id: str
    document: str
    metadata: dict[str, Any] = field(default_factory=dict)
    distance: float = 0.0


class VectorStore(ABC):
    """Abstract vector store for decision storage and retrieval.

    All vector database backends (ChromaDB, Weaviate, pgvector, in-memory)
    implement this interface. Services interact only through these methods.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize connection and ensure collection exists.

        Called once at startup or on first use. Implementations should
        create the collection if it does not exist.
        """
        ...

    @abstractmethod
    async def upsert(
        self,
        doc_id: str,
        document: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> bool:
        """Insert or update a document with its embedding and metadata.

        Args:
            doc_id: Unique document identifier.
            document: Document text content.
            embedding: Pre-computed embedding vector.
            metadata: Key-value metadata for filtering.

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        """Find similar documents by embedding vector.

        Args:
            embedding: Query embedding vector.
            n_results: Maximum number of results to return.
            where: Optional metadata filter (ChromaDB-style operators:
                   exact match, $gte, $lte, $in, $contains, $or, $and).

        Returns:
            List of VectorResult sorted by ascending distance.
        """
        ...

    @abstractmethod
    async def delete(self, ids: list[str]) -> bool:
        """Delete documents by their IDs.

        Args:
            ids: List of document IDs to remove.

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """Return total number of documents in the collection."""
        ...

    @abstractmethod
    async def reset(self) -> bool:
        """Delete and recreate the collection.

        Used by reindex operations to start from a clean state.

        Returns:
            True if the operation succeeded.
        """
        ...

    @abstractmethod
    async def get_collection_id(self) -> str | None:
        """Get the backend-specific collection identifier.

        Returns:
            Collection ID string, or None if the collection does not exist.
        """
        ...

    async def close(self) -> None:  # noqa: B027
        """Clean up connections. Override if the backend holds resources."""
