"""Reindex service for CSTP.

Provides functionality to recreate the vector store collection with fresh embeddings.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

from .decision_service import reindex_decision
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

        file_path = decision.get("_file", "")

        try:
            if await reindex_decision(doc_id, decision, file_path):
                indexed += 1
            else:
                errors += 1
        except Exception as e:
            logger.error("Failed to reindex decision %s: %s", doc_id, e)
            errors += 1

    duration_ms = int((time.time() - start_time) * 1000)

    return ReindexResult(
        success=True,
        decisions_indexed=indexed,
        errors=errors,
        duration_ms=duration_ms,
        message=f"Indexed {indexed} decisions with {errors} errors in {duration_ms}ms",
    )
