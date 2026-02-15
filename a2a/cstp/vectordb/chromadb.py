"""ChromaDB vector store implementation for CSTP.

Extracts and unifies ChromaDB HTTP API v2 logic previously scattered
across query_service.py, decision_service.py, and reindex_service.py.
"""

import json
import logging
import os
from typing import Any

from . import VectorResult, VectorStore

logger = logging.getLogger(__name__)


class ChromaDBStore(VectorStore):
    """ChromaDB backend via HTTP API v2."""

    def __init__(
        self,
        url: str | None = None,
        collection: str | None = None,
        tenant: str | None = None,
        database: str | None = None,
    ) -> None:
        self._url = url or os.getenv("CHROMA_URL", "http://chromadb:8000")
        self._collection_name = collection or os.getenv(
            "CHROMA_COLLECTION", "decisions_gemini"
        )
        self._tenant = tenant or os.getenv("CHROMA_TENANT", "default_tenant")
        self._database = database or os.getenv("CHROMA_DATABASE", "default_database")
        self._collection_id: str | None = None

    @property
    def _base(self) -> str:
        return (
            f"{self._url}/api/v2/tenants/{self._tenant}"
            f"/databases/{self._database}"
        )

    async def _request(
        self,
        method: str,
        url: str,
        data: dict[str, Any] | None = None,
        headers: dict[str, Any] | None = None,
    ) -> tuple[int, Any]:
        """Make an async HTTP request, falling back to sync urllib."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                if method == "GET":
                    response = await client.get(url, headers=headers)
                elif method == "DELETE":
                    response = await client.delete(url, headers=headers)
                else:
                    response = await client.request(
                        method, url, json=data, headers=headers
                    )
                return response.status_code, response.json() if response.text else {}
        except ImportError:
            import urllib.request

            req_headers = {"Content-Type": "application/json"}
            if headers:
                req_headers.update(headers)
            body = json.dumps(data).encode() if data else None
            req = urllib.request.Request(
                url, data=body, headers=req_headers, method=method
            )

            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    content = resp.read().decode()
                    return resp.status, json.loads(content) if content else {}
            except urllib.error.HTTPError as e:
                content = e.read().decode() if e.fp else ""
                return e.code, {"error": content}
            except Exception as e:
                return 0, {"error": str(e)}

    async def initialize(self) -> None:
        """Ensure collection exists, creating it if needed."""
        self._collection_id = await self.get_collection_id()
        if self._collection_id:
            return

        # Create the collection
        status, data = await self._request(
            "POST",
            f"{self._base}/collections",
            {"name": self._collection_name, "metadata": {"hnsw:space": "cosine"}},
        )
        if status in (200, 201) and isinstance(data, dict):
            self._collection_id = data.get("id")
            logger.info("Created ChromaDB collection: %s", self._collection_name)
        else:
            logger.error("Failed to create collection: %s", data)

    async def get_collection_id(self) -> str | None:
        """Get collection ID by listing collections and matching by name."""
        if self._collection_id:
            return self._collection_id

        status, data = await self._request(
            "GET", f"{self._base}/collections"
        )
        if status == 200 and isinstance(data, list):
            for c in data:
                if c.get("name") == self._collection_name:
                    self._collection_id = c["id"]
                    return self._collection_id
        return None

    async def upsert(
        self,
        doc_id: str,
        document: str,
        embedding: list[float],
        metadata: dict[str, Any],
    ) -> bool:
        """Upsert a document, falling back to add on failure."""
        coll_id = await self.get_collection_id()
        if not coll_id:
            await self.initialize()
            coll_id = self._collection_id
        if not coll_id:
            logger.error("Could not get or create ChromaDB collection")
            return False

        payload = {
            "ids": [doc_id],
            "documents": [document],
            "metadatas": [metadata],
            "embeddings": [embedding],
        }

        # Try upsert first
        status, data = await self._request(
            "POST", f"{self._base}/collections/{coll_id}/upsert", payload
        )
        if status in (200, 201):
            return True

        logger.warning("ChromaDB upsert failed, trying add: %s", data)

        # Fallback to add
        status, data = await self._request(
            "POST", f"{self._base}/collections/{coll_id}/add", payload
        )
        if status in (200, 201):
            return True

        logger.error("ChromaDB indexing failed: %s", data)
        return False

    async def query(
        self,
        embedding: list[float],
        n_results: int = 10,
        where: dict[str, Any] | None = None,
    ) -> list[VectorResult]:
        """Query by embedding similarity with optional metadata filters."""
        coll_id = await self.get_collection_id()
        if not coll_id:
            return []

        payload: dict[str, Any] = {
            "query_embeddings": [embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            payload["where"] = where

        status, data = await self._request(
            "POST", f"{self._base}/collections/{coll_id}/query", payload
        )

        if status != 200 or not data.get("documents"):
            return []

        results: list[VectorResult] = []
        docs = data["documents"][0] if data.get("documents") else []
        metas = data["metadatas"][0] if data.get("metadatas") else []
        dists = data["distances"][0] if data.get("distances") else []
        ids = data["ids"][0] if data.get("ids") else []

        for i, doc_id in enumerate(ids):
            results.append(
                VectorResult(
                    id=doc_id,
                    document=docs[i] if i < len(docs) else "",
                    metadata=metas[i] if i < len(metas) else {},
                    distance=dists[i] if i < len(dists) else 0.0,
                )
            )

        return results

    async def delete(self, ids: list[str]) -> bool:
        """Delete documents by IDs."""
        coll_id = await self.get_collection_id()
        if not coll_id:
            return False

        if not ids:
            return True

        status, _data = await self._request(
            "POST",
            f"{self._base}/collections/{coll_id}/delete",
            {"ids": ids},
        )
        return status in (200, 204)

    async def count(self) -> int:
        """Return document count by fetching all IDs."""
        coll_id = await self.get_collection_id()
        if not coll_id:
            return 0

        status, data = await self._request(
            "POST",
            f"{self._base}/collections/{coll_id}/get",
            {"limit": 100000, "include": []},
        )
        if status == 200 and isinstance(data, dict):
            return len(data.get("ids", []))
        return 0

    async def reset(self) -> bool:
        """Delete and recreate the collection."""
        # Delete existing collection
        coll_id = await self.get_collection_id()
        if coll_id:
            status, data = await self._request(
                "DELETE", f"{self._base}/collections/{coll_id}"
            )
            if status not in (200, 204, 404):
                # Check for NotFoundError (already deleted)
                if isinstance(data, dict) and data.get("error") != "NotFoundError":
                    logger.error("Failed to delete collection: %s", data)
                    return False
            logger.info("Deleted collection %s", self._collection_name)

        self._collection_id = None

        # Recreate
        status, data = await self._request(
            "POST",
            f"{self._base}/collections",
            {"name": self._collection_name, "metadata": {"hnsw:space": "cosine"}},
        )
        if status in (200, 201) and isinstance(data, dict):
            self._collection_id = data.get("id")
            logger.info("Created collection %s", self._collection_name)
            return True

        # Collection might already exist if delete didn't fully propagate
        if status not in (200, 201):
            existing_id = await self._find_collection_id()
            if existing_id:
                self._collection_id = existing_id
                await self._clear_all_documents(existing_id)
                return True

        logger.error("Failed to recreate collection: %s", data)
        return False

    async def _find_collection_id(self) -> str | None:
        """Find collection ID by listing (bypasses cache)."""
        self._collection_id = None
        return await self.get_collection_id()

    async def _clear_all_documents(self, coll_id: str) -> bool:
        """Remove all documents from a collection."""
        status, data = await self._request(
            "POST",
            f"{self._base}/collections/{coll_id}/get",
            {"limit": 100000},
        )
        if status != 200 or not isinstance(data, dict):
            return False

        ids = data.get("ids", [])
        if not ids:
            return True

        logger.info("Clearing %d documents from collection", len(ids))
        return await self.delete(ids)
