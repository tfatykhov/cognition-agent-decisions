"""Reindex service for CSTP.

Provides functionality to recreate the vector store collection with fresh embeddings.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from .embeddings.factory import get_embedding_provider
from .query_service import load_all_decisions
from .vectordb.factory import get_vector_store

logger = logging.getLogger(__name__)


@dataclass
class ReindexResult:
    """Result of reindex operation."""

    success: bool
    decisions_indexed: int
    errors: int
    duration_ms: int
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for JSON response."""
        return {
            "success": self.success,
            "decisionsIndexed": self.decisions_indexed,
            "errors": self.errors,
            "durationMs": self.duration_ms,
            "message": self.message,
        }


async def reindex_decisions() -> ReindexResult:
    """Reindex all decisions with fresh embeddings.

    This will:
    1. Reset the vector store collection
    2. Load all decisions from YAML files
    3. Generate embeddings for each
    4. Upsert to the store

    Returns:
        ReindexResult with operation status.
    """
    start_time = time.time()

    store = get_vector_store()
    provider = get_embedding_provider()

    # Step 1: Reset collection (delete + recreate)
    if not await store.reset():
        return ReindexResult(
            success=False,
            decisions_indexed=0,
            errors=0,
            duration_ms=int((time.time() - start_time) * 1000),
            message="Failed to reset vector store collection",
        )

    # Step 2: Load all decisions
    decisions = await load_all_decisions()
    if not decisions:
        return ReindexResult(
            success=True,
            decisions_indexed=0,
            errors=0,
            duration_ms=int((time.time() - start_time) * 1000),
            message="No decisions found to index",
        )

    # Step 3 & 4: Generate embeddings and upsert
    indexed = 0
    errors = 0

    for decision in decisions:
        doc_id = decision.get("id", "")
        if not doc_id:
            errors += 1
            continue

        # Build text for embedding
        summary = decision.get("summary", decision.get("decision", ""))
        context = decision.get("context", "")
        category = decision.get("category", "")

        text = f"{summary}\n{context}\nCategory: {category}"

        try:
            embedding = await provider.embed(text)
        except Exception as e:
            logger.error("Failed to generate embedding for %s: %s", doc_id, e)
            errors += 1
            continue

        # Build metadata
        title = (
            decision.get("title")
            or decision.get("decision")
            or decision.get("summary")
            or ""
        )
        date_raw = decision.get("date") or decision.get("timestamp") or ""
        date_str = str(date_raw)[:10] if date_raw else ""

        metadata: dict[str, Any] = {
            "title": title[:500] if title else "",
            "date": date_str,
            "category": decision.get("category", ""),
            "stakes": decision.get("stakes", ""),
            "confidence": float(decision.get("confidence", 0.5)),
            "status": decision.get("status", "pending"),
            "created_at": decision.get("created_at", ""),
        }

        # Filter None/empty values (some backends don't accept them)
        metadata = {k: v for k, v in metadata.items() if v is not None and v != ""}

        # Upsert to store
        if await store.upsert(doc_id, text, embedding, metadata):
            indexed += 1
        else:
            errors += 1

    duration_ms = int((time.time() - start_time) * 1000)

    return ReindexResult(
        success=True,
        decisions_indexed=indexed,
        errors=errors,
        duration_ms=duration_ms,
        message=f"Indexed {indexed} decisions with {errors} errors in {duration_ms}ms",
    )
