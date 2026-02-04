#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Query similar decisions from the semantic index.
"""

import argparse
import json
import os
import sys
import hashlib
import urllib.request
from pathlib import Path

# Configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = "cognition_decisions"


def load_gemini_key() -> str:
    """Load Gemini API key from env or secrets."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    
    secrets_paths = [
        Path("/home/node/.openclaw/workspace/.secrets/gemini.env"),
        Path.home() / ".secrets" / "gemini.env",
        Path.home() / ".openclaw" / "workspace" / ".secrets" / "gemini.env",
    ]
    
    for path in secrets_paths:
        if path.exists():
            for line in path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return GEMINI_API_KEY
    
    raise ValueError("GEMINI_API_KEY not found. Set env var or add to .secrets/gemini.env")


def api_request(method: str, url: str, data: dict = None) -> tuple[int, any]:
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


def generate_embedding(text: str) -> list[float]:
    """Generate embedding using Gemini."""
    api_key = load_gemini_key()
    
    if len(text) > 8000:
        text = text[:8000]
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    data = {"content": {"parts": [{"text": text}]}}
    
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result["embedding"]["values"]


def get_collection_id() -> str | None:
    """Get the decisions collection ID."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    status, data = api_request("GET", f"{base}/collections")
    
    if status == 200 and isinstance(data, list):
        for c in data:
            if c.get("name") == COLLECTION_NAME:
                return c["id"]
    return None


def query_decisions(
    query: str,
    n_results: int = 5,
    category: str = None,
    min_confidence: float = None,
) -> dict:
    """Query similar decisions."""
    
    coll_id = get_collection_id()
    if not coll_id:
        return {
            "query": query,
            "error": "Collection not found. Run index.py first.",
            "results": []
        }
    
    embedding = generate_embedding(query)
    
    # Build where clause
    where = {}
    if category:
        where["category"] = category
    if min_confidence is not None:
        where["confidence"] = {"$gte": min_confidence}
    
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    payload = {
        "query_embeddings": [embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        payload["where"] = where
    
    status, data = api_request("POST", f"{base}/collections/{coll_id}/query", payload)
    
    if status != 200:
        return {
            "query": query,
            "error": f"Query failed: {data}",
            "results": []
        }
    
    results = []
    if data.get("documents") and data["documents"][0]:
        for i, doc in enumerate(data["documents"][0]):
            meta = data["metadatas"][0][i] if data.get("metadatas") else {}
            dist = data["distances"][0][i] if data.get("distances") else None
            
            results.append({
                "title": meta.get("title", "Untitled"),
                "category": meta.get("category", ""),
                "confidence": meta.get("confidence"),
                "status": meta.get("status", ""),
                "date": meta.get("date", ""),
                "distance": round(dist, 4) if dist else None,
            })
    
    return {
        "query": query,
        "count": len(results),
        "results": results
    }


def main():
    parser = argparse.ArgumentParser(description="Query similar decisions")
    parser.add_argument("query", help="Query text to find similar decisions")
    parser.add_argument("--top", "-n", type=int, default=5, help="Number of results")
    parser.add_argument("--category", "-c", help="Filter by category")
    parser.add_argument("--min-confidence", type=float, help="Minimum confidence threshold")
    parser.add_argument("--format", choices=["json", "text"], default="json", help="Output format")
    
    args = parser.parse_args()
    
    try:
        result = query_decisions(
            args.query,
            n_results=args.top,
            category=args.category,
            min_confidence=args.min_confidence,
        )
        
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"\nQuery: {result['query']}")
            print(f"Found: {result['count']} similar decisions\n")
            
            for i, r in enumerate(result["results"], 1):
                print(f"[{i}] {r['title']}")
                print(f"    Category: {r['category']} | Confidence: {r['confidence']}")
                print(f"    Distance: {r['distance']} | Status: {r['status']}")
                print()
        
        return 0 if not result.get("error") else 1
        
    except Exception as e:
        error_result = {"error": str(e), "query": args.query, "results": []}
        print(json.dumps(error_result, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
