"""Query service for semantic decision search.

Wraps ChromaDB HTTP API for querying decisions.
Uses httpx for async HTTP to avoid blocking the event loop.
"""

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

# Configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "decisions_gemini")
DECISIONS_PATH = os.getenv("DECISIONS_PATH", "decisions")

# Configurable secrets paths (can be overridden via env)
SECRETS_PATHS = os.getenv(
    "SECRETS_PATHS",
    "/home/node/.openclaw/workspace/.secrets:~/.secrets",
).split(":")


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


def _get_secrets_paths() -> list[Path]:
    """Get list of paths to search for secrets."""
    paths = []
    for p in SECRETS_PATHS:
        expanded = Path(p.strip()).expanduser()
        paths.append(expanded)
    return paths


def _load_gemini_key() -> str:
    """Load Gemini API key from env or secrets."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY

    for path in _get_secrets_paths():
        gemini_env = path / "gemini.env"
        if gemini_env.exists():
            for line in gemini_env.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return GEMINI_API_KEY

    raise ValueError("GEMINI_API_KEY not found in environment or secrets paths")


async def _async_request(
    method: str, url: str, data: dict | None = None, headers: dict | None = None
) -> tuple[int, Any]:
    """Make async HTTP request using httpx.

    Falls back to sync urllib if httpx not available.
    """
    try:
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            if method == "GET":
                response = await client.get(url, headers=headers)
            else:
                response = await client.request(
                    method, url, json=data, headers=headers
                )
            return response.status_code, response.json() if response.text else {}
    except ImportError:
        # Fallback to sync (less ideal but works)
        import urllib.request

        req_headers = {"Content-Type": "application/json"}
        if headers:
            req_headers.update(headers)
        body = json.dumps(data).encode() if data else None
        req = urllib.request.Request(url, data=body, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                content = resp.read().decode()
                return resp.status, json.loads(content) if content else {}
        except urllib.error.HTTPError as e:
            content = e.read().decode() if e.fp else ""
            return e.code, {"error": content}
        except Exception as e:
            return 0, {"error": str(e)}


async def _generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini API.

    API key is sent via header, not URL query param, for security.
    """
    api_key = _load_gemini_key()

    if len(text) > 8000:
        text = text[:8000]

    url = "https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent"
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key,
    }
    data = {"content": {"parts": [{"text": text}]}}

    status, result = await _async_request("POST", url, data, headers)

    if status != 200:
        raise RuntimeError(f"Embedding API error: {result}")

    return result["embedding"]["values"]


async def _get_collection_id() -> str | None:
    """Get the decisions collection ID."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    status, data = await _async_request("GET", f"{base}/collections")

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
    # F010: Project context filters
    project: str | None = None,
    feature: str | None = None,
    pr: int | None = None,
    has_outcome: bool | None = None,
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
        project: Filter by project (owner/repo).
        feature: Filter by feature name.
        pr: Filter by PR number.
        has_outcome: Filter to only reviewed decisions (True) or pending (False).

    Returns:
        QueryResponse with results or error.
    """
    start_time = time.time()

    # Get collection
    coll_id = await _get_collection_id()
    if not coll_id:
        return QueryResponse(
            results=[],
            query=query,
            query_time_ms=0,
            error="Collection not found. Index decisions first.",
        )

    # Generate embedding
    try:
        embedding = await _generate_embedding(query)
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

    # F010: Project context filters
    if project:
        where["project"] = project
    if feature:
        where["feature"] = feature
    if pr is not None:
        where["pr"] = pr
    if has_outcome is True:
        where["status"] = "reviewed"
    elif has_outcome is False:
        where["status"] = "pending"

    # Query ChromaDB
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    payload: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        payload["where"] = where

    status, data = await _async_request(
        "POST", f"{base}/collections/{coll_id}/query", payload
    )

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


async def load_all_decisions(
    decisions_path: str | None = None,
    category: str | None = None,
    project: str | None = None,
) -> list[dict[str, Any]]:
    """Load all decision files from disk.

    Args:
        decisions_path: Override for decisions directory.
        category: Optional category filter.
        project: Optional project filter.

    Returns:
        List of decision dictionaries with id and content.
    """
    base = Path(decisions_path or DECISIONS_PATH)
    decisions: list[dict[str, Any]] = []

    if not base.exists():
        return decisions

    for yaml_file in base.rglob("*-decision-*.yaml"):
        try:
            with open(yaml_file) as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            # Extract ID from filename
            filename = yaml_file.stem
            parts = filename.rsplit("-decision-", 1)
            if len(parts) == 2:
                data["id"] = parts[1]
            else:
                data["id"] = filename

            # Apply filters
            if category and data.get("category") != category:
                continue
            if project and data.get("project") != project:
                continue

            decisions.append(data)

        except Exception:
            continue

    return decisions
