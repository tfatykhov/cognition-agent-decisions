"""Query service for semantic decision search.

Wraps ChromaDB HTTP API for querying decisions.
"""

import json
import os
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = "cognition_decisions"


@dataclass(slots=True)
class QueryResult:
    """Single query result from ChromaDB."""

    id: str
    title: str
    category: str
    confidence: float | None
    stakes: str | None
    status: str
    outcome: str | None
    date: str
    distance: float
    reason_types: list[str] | None = None


@dataclass(slots=True)
class QueryResponse:
    """Response from query operation."""

    results: list[QueryResult]
    query: str
    query_time_ms: int
    error: str | None = None


def _load_gemini_key() -> str:
    """Load Gemini API key from env or secrets."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY

    secrets_paths = [
        Path("/home/node/.openclaw/workspace/.secrets/gemini.env"),
        Path.home() / ".secrets" / "gemini.env",
    ]

    for path in secrets_paths:
        if path.exists():
            for line in path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return GEMINI_API_KEY

    raise ValueError("GEMINI_API_KEY not found")


def _api_request(method: str, url: str, data: dict | None = None) -> tuple[int, Any]:
    """Make HTTP request to ChromaDB API."""
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode()
            return resp.status, json.loads(content) if content else {}
    except urllib.error.HTTPError as e:
        content = e.read().decode() if e.fp else ""
        return e.code, {"error": content}
    except Exception as e:
        return 0, {"error": str(e)}


def _generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini."""
    api_key = _load_gemini_key()

    if len(text) > 8000:
        text = text[:8000]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    data = {"content": {"parts": [{"text": text}]}}

    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result["embedding"]["values"]


def _get_collection_id() -> str | None:
    """Get the decisions collection ID."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    status, data = _api_request("GET", f"{base}/collections")

    if status == 200 and isinstance(data, list):
        for c in data:
            if c.get("name") == COLLECTION_NAME:
                return c["id"]
    return None


async def query_decisions(
    query: str,
    n_results: int = 10,
    category: str | None = None,
    min_confidence: float | None = None,
    max_confidence: float | None = None,
    stakes: list[str] | None = None,
    status_filter: list[str] | None = None,
) -> QueryResponse:
    """Query similar decisions from ChromaDB.

    Args:
        query: Search query text.
        n_results: Maximum results to return.
        category: Filter by category.
        min_confidence: Minimum confidence threshold.
        max_confidence: Maximum confidence threshold.
        stakes: Filter by stakes levels.
        status_filter: Filter by status values.

    Returns:
        QueryResponse with results or error.
    """
    start_time = time.time()

    # Get collection
    coll_id = _get_collection_id()
    if not coll_id:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=0,
            error="Collection not found. Index decisions first.",
        )

    # Generate embedding
    try:
        embedding = _generate_embedding(query)
    except Exception as e:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=int((time.time() - start_time) * 1000),
            error=f"Embedding generation failed: {e}",
        )

    # Build where clause
    where: dict[str, Any] = {}
    if category:
        where["category"] = category
    if min_confidence is not None:
        where["confidence"] = {"$gte": min_confidence}
    if stakes:
        where["stakes"] = {"$in": stakes}
    if status_filter:
        where["status"] = {"$in": status_filter}

    # Query ChromaDB
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    payload: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        payload["where"] = where

    status, data = _api_request("POST", f"{base}/collections/{coll_id}/query", payload)

    if status != 200:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=int((time.time() - start_time) * 1000),
            error=f"Query failed: {data}",
        )

    # Parse results
    results: list[QueryResult] = []
    if data.get("documents") and data["documents"][0]:
        ids = data.get("ids", [[]])[0]
        for i, _doc in enumerate(data["documents"][0]):
            meta = data["metadatas"][0][i] if data.get("metadatas") else {}
            dist = data["distances"][0][i] if data.get("distances") else 0.0
            doc_id = ids[i] if i < len(ids) else f"unknown-{i}"

            # Parse reason types if present
            reason_types = None
            if meta.get("reason_types"):
                reason_types = meta["reason_types"].split(",")

            results.append(
                QueryResult(
                    id=doc_id[:8] if len(doc_id) > 8 else doc_id,
                    title=meta.get("title", "Untitled"),
                    category=meta.get("category", ""),
                    confidence=meta.get("confidence"),
                    stakes=meta.get("stakes"),
                    status=meta.get("status", ""),
                    outcome=meta.get("outcome"),
                    date=meta.get("date", ""),
                    distance=round(dist, 4) if dist else 0.0,
                    reason_types=reason_types,
                )
            )

    return QueryResponse(
        results=results,
        query=query,
        query_time_ms=int((time.time() - start_time) * 1000),
    )
