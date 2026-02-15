"""In-memory vector store for testing and development.

Provides a VectorStore implementation that requires no external
services. Uses cosine distance for similarity and supports
ChromaDB-style where-clause filtering.
"""

import math
from typing import Any

from . import VectorResult, VectorStore


class MemoryStore(VectorStore):
    """In-memory vector store backed by a Python dict.

    Suitable for tests and development without ChromaDB.
    """

    def __init__(self) -> None:
        self._docs: dict[str, dict[str, Any]] = {}
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def upsert(
        self,
        doc_id: str,
        document: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> bool:
        self._docs[doc_id] = {
            "document": document,
            "embedding": embedding,
            "metadata": metadata,
        }
        return True

    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        results: list[VectorResult] = []
        for doc_id, doc in self._docs.items():
            if where and not _matches_where(doc["metadata"], where):
                continue
            dist = _cosine_distance(embedding, doc["embedding"])
            results.append(
                VectorResult(
                    id=doc_id,
                    document=doc["document"],
                    metadata=doc["metadata"],
                    distance=dist,
                )
            )
        results.sort(key=lambda r: r.distance)
        return results[:n_results]

    async def delete(self, ids: list[str]) -> bool:
        for doc_id in ids:
            self._docs.pop(doc_id, None)
        return True

    async def count(self) -> int:
        return len(self._docs)

    async def reset(self) -> bool:
        self._docs.clear()
        self._initialized = True
        return True

    async def get_collection_id(self) -> str | None:
        return "memory-collection" if self._initialized or self._docs else None


def _cosine_distance(a: list[float], b: list[float]) -> float:
    """Compute cosine distance between two vectors."""
    if len(a) != len(b):
        return 1.0
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 1.0
    return 1.0 - dot / (norm_a * norm_b)


def _matches_where(metadata: dict[str, Any], where: dict[str, Any]) -> bool:
    """Evaluate a ChromaDB-style where clause against metadata.

    Supports: exact match, $gte, $lte, $gt, $lt, $ne, $in, $nin,
    $contains, $or, $and.
    """
    for key, condition in where.items():
        if key == "$or":
            if not isinstance(condition, list) or not condition:
                return False
            if not any(_matches_where(metadata, sub) for sub in condition):
                return False
            continue

        if key == "$and":
            if not isinstance(condition, list) or not condition:
                return False
            if not all(_matches_where(metadata, sub) for sub in condition):
                return False
            continue

        value = metadata.get(key)

        # Operator dict
        if isinstance(condition, dict):
            for op, target in condition.items():
                if not _eval_operator(op, value, target):
                    return False
        else:
            # Exact match
            if value != condition:
                return False

    return True


def _eval_operator(op: str, value: Any, target: Any) -> bool:
    """Evaluate a single comparison operator."""
    if value is None:
        return False

    match op:
        case "$gte":
            return value >= target
        case "$lte":
            return value <= target
        case "$gt":
            return value > target
        case "$lt":
            return value < target
        case "$ne":
            return value != target
        case "$in":
            return value in target if isinstance(target, list) else False
        case "$nin":
            return value not in target if isinstance(target, list) else True
        case "$contains":
            if isinstance(value, str):
                return target in value
            if isinstance(value, list):
                return target in value
            return False
        case _:
            return False
