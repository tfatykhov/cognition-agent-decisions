"""Reindex service for CSTP.

Provides functionality to recreate the ChromaDB collection with fresh embeddings.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx

from .query_service import (
    CHROMA_URL,
    COLLECTION_NAME,
    DATABASE,
    TENANT,
    _generate_embedding,
    load_all_decisions,
)

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


async def _delete_collection() -> bool:
    """Delete the existing collection if it exists."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    logger.info("Attempting to delete collection at %s", base)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # List collections to find our collection
            resp = await client.get(f"{base}/collections")
            logger.info("List collections response: %s %s", resp.status_code, resp.text[:200] if resp.text else "")
            if resp.status_code != 200:
                logger.warning("Failed to list collections: %s", resp.text)
                return False

            collections = resp.json()
            coll_id = None
            for c in collections:
                if c.get("name") == COLLECTION_NAME:
                    coll_id = c["id"]
                    break

            if not coll_id:
                logger.info("Collection %s does not exist, nothing to delete", COLLECTION_NAME)
                return True

            # Delete the collection
            logger.info("Deleting collection %s with id %s", COLLECTION_NAME, coll_id)
            resp = await client.delete(f"{base}/collections/{coll_id}")

            # Treat 404/NotFound as success (already deleted)
            if resp.status_code == 404:
                logger.info("Collection already deleted (404)")
                return True

            # Check response body for NotFoundError
            if resp.status_code not in (200, 204):
                try:
                    err_data = resp.json()
                    if err_data.get("error") == "NotFoundError":
                        logger.info("Collection already deleted (NotFoundError)")
                        return True
                except Exception:
                    pass
                logger.error("Failed to delete collection: %s", resp.text)
                return False

            logger.info("Deleted collection %s", COLLECTION_NAME)
            return True
    except Exception as e:
        logger.exception("Exception during collection delete: %s", e)
        return False


async def _create_collection() -> str | None:
    """Create a new collection and return its ID."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    logger.info("Creating collection at %s", base)

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Create collection with cosine distance
            payload = {
                "name": COLLECTION_NAME,
                "metadata": {
                    "hnsw:space": "cosine",
                },
            }
            logger.info("Create collection payload: %s", payload)
            resp = await client.post(f"{base}/collections", json=payload)
            logger.info("Create collection response: %s %s", resp.status_code, resp.text[:500] if resp.text else "")

            # If collection already exists, get its ID
            if resp.status_code not in (200, 201):
                try:
                    err_data = resp.json()
                    if "already exists" in err_data.get("message", ""):
                        logger.info("Collection already exists, fetching existing ID")
                        # Get existing collection ID
                        list_resp = await client.get(f"{base}/collections")
                        if list_resp.status_code == 200:
                            for c in list_resp.json():
                                if c.get("name") == COLLECTION_NAME:
                                    coll_id = c["id"]
                                    logger.info("Found existing collection with id %s", coll_id)
                                    # Clear all documents from existing collection
                                    await _clear_collection(client, base, coll_id)
                                    return coll_id
                except Exception:
                    pass
                logger.error("Failed to create collection: %s", resp.text)
                return None

            data = resp.json()
            coll_id = data.get("id")
            logger.info("Created collection %s with id %s", COLLECTION_NAME, coll_id)
            return coll_id
    except Exception as e:
        logger.exception("Exception during collection create: %s", e)
        return None


async def _clear_collection(client: httpx.AsyncClient, base: str, coll_id: str) -> bool:
    """Clear all documents from a collection."""
    try:
        # Get all document IDs
        resp = await client.post(f"{base}/collections/{coll_id}/get", json={"limit": 10000})
        if resp.status_code != 200:
            logger.warning("Failed to get documents for clearing: %s", resp.text)
            return False

        data = resp.json()
        ids = data.get("ids", [])
        if not ids:
            logger.info("Collection is already empty")
            return True

        logger.info("Clearing %d documents from collection", len(ids))
        # Delete all documents
        resp = await client.post(f"{base}/collections/{coll_id}/delete", json={"ids": ids})
        if resp.status_code not in (200, 204):
            logger.warning("Failed to delete documents: %s", resp.text)
            return False

        logger.info("Cleared %d documents", len(ids))
        return True
    except Exception as e:
        logger.exception("Exception clearing collection: %s", e)
        return False


async def _add_to_collection(
    coll_id: str,
    doc_id: str,
    embedding: list[float],
    metadata: dict[str, Any],
    document: str,
) -> bool:
    """Add a single document to the collection."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "ids": [doc_id],
            "embeddings": [embedding],
            "metadatas": [metadata],
            "documents": [document],
        }
        resp = await client.post(f"{base}/collections/{coll_id}/add", json=payload)
        if resp.status_code not in (200, 201):
            logger.error("Failed to add document %s: %s", doc_id, resp.text)
            return False
        return True


async def reindex_decisions() -> ReindexResult:
    """Reindex all decisions with fresh embeddings.

    This will:
    1. Delete the existing collection
    2. Create a new collection
    3. Load all decisions from YAML files
    4. Generate embeddings for each
    5. Add to the new collection

    Returns:
        ReindexResult with operation status.
    """
    start_time = time.time()

    # Step 1: Delete existing collection
    if not await _delete_collection():
        return ReindexResult(
            success=False,
            decisions_indexed=0,
            errors=0,
            duration_ms=int((time.time() - start_time) * 1000),
            message="Failed to delete existing collection",
        )

    # Step 2: Create new collection
    coll_id = await _create_collection()
    if not coll_id:
        return ReindexResult(
            success=False,
            decisions_indexed=0,
            errors=0,
            duration_ms=int((time.time() - start_time) * 1000),
            message="Failed to create new collection",
        )

    # Step 3: Load all decisions
    decisions = await load_all_decisions()
    if not decisions:
        return ReindexResult(
            success=True,
            decisions_indexed=0,
            errors=0,
            duration_ms=int((time.time() - start_time) * 1000),
            message="No decisions found to index",
        )

    # Step 4 & 5: Generate embeddings and add to collection
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
            embedding = await _generate_embedding(text)
        except Exception as e:
            logger.error("Failed to generate embedding for %s: %s", doc_id, e)
            errors += 1
            continue

        # Build metadata
        metadata = {
            "category": decision.get("category", ""),
            "stakes": decision.get("stakes", ""),
            "confidence": float(decision.get("confidence", 0.5)),
            "status": decision.get("status", "pending"),
            "created_at": decision.get("created_at", ""),
        }

        # Filter None values (ChromaDB doesn't like them)
        metadata = {k: v for k, v in metadata.items() if v is not None and v != ""}

        # Add to collection
        if await _add_to_collection(coll_id, doc_id, embedding, metadata, text):
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
