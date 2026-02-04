"""
Semantic Decision Index
Embeds decisions into ChromaDB for similarity search
"""

import os
import json
import hashlib
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional

# ChromaDB configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
CHROMA_TOKEN = os.getenv("CHROMA_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = "cognition_decisions"
EMBEDDING_DIM = 768


def load_gemini_key() -> str:
    """Load Gemini API key from secrets if not in env."""
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
    
    raise ValueError("GEMINI_API_KEY not found in environment or secrets")


def api_request(method: str, url: str, data: dict = None) -> tuple[int, any]:
    """Make HTTP request to ChromaDB API."""
    headers = {"Content-Type": "application/json"}
    if CHROMA_TOKEN:
        headers["Authorization"] = f"Bearer {CHROMA_TOKEN}"
    
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
    """Generate embedding using Gemini text-embedding-004."""
    api_key = load_gemini_key()
    
    # Truncate if too long
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


def get_api_base() -> str:
    """Get ChromaDB API base URL."""
    return f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"


def get_or_create_collection() -> Optional[str]:
    """Get or create the decisions collection, returns collection ID."""
    base = get_api_base()
    
    # List existing collections
    status, data = api_request("GET", f"{base}/collections")
    if status == 200 and isinstance(data, list):
        for c in data:
            if c.get("name") == COLLECTION_NAME:
                return c["id"]
    
    # Create new
    status, data = api_request("POST", f"{base}/collections", {"name": COLLECTION_NAME})
    if status in (200, 201):
        return data.get("id")
    
    print(f"Error creating collection: {status} {data}")
    return None


def decision_to_text(decision: dict) -> str:
    """Convert decision dict to searchable text."""
    parts = []
    
    if decision.get("title"):
        parts.append(f"Title: {decision['title']}")
    
    if decision.get("context"):
        parts.append(f"Context: {decision['context']}")
    
    if decision.get("decision"):
        parts.append(f"Decision: {decision['decision']}")
    
    if decision.get("reasons"):
        reasons = decision["reasons"]
        if isinstance(reasons, list):
            reason_texts = [r.get("description", str(r)) for r in reasons]
            parts.append(f"Reasons: {'; '.join(reason_texts)}")
    
    if decision.get("category"):
        parts.append(f"Category: {decision['category']}")
    
    if decision.get("outcome"):
        parts.append(f"Outcome: {decision['outcome']}")
    
    return "\n".join(parts)


def decision_id(decision: dict) -> str:
    """Generate unique ID for decision."""
    if decision.get("id"):
        return decision["id"]
    
    # Hash based on title + date
    key = f"{decision.get('title', '')}-{decision.get('date', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


class SemanticIndex:
    """Semantic index for decisions using ChromaDB."""
    
    def __init__(self):
        self.collection_id = None
    
    def ensure_collection(self):
        """Ensure collection exists."""
        if not self.collection_id:
            self.collection_id = get_or_create_collection()
        return self.collection_id
    
    def index_decision(self, decision: dict) -> bool:
        """Index a single decision."""
        coll_id = self.ensure_collection()
        if not coll_id:
            return False
        
        text = decision_to_text(decision)
        embedding = generate_embedding(text)
        doc_id = decision_id(decision)
        
        metadata = {
            "title": decision.get("title", ""),
            "category": decision.get("category", ""),
            "confidence": float(decision.get("confidence", 0)),
            "status": decision.get("status", ""),
            "date": decision.get("date", ""),
            "indexed_at": datetime.utcnow().isoformat(),
        }
        
        base = get_api_base()
        status, data = api_request(
            "POST",
            f"{base}/collections/{coll_id}/add",
            {
                "ids": [doc_id],
                "documents": [text],
                "embeddings": [embedding],
                "metadatas": [metadata],
            }
        )
        
        return status in (200, 201)
    
    def index_decisions(self, decisions: list[dict]) -> int:
        """Index multiple decisions. Returns count indexed."""
        count = 0
        for i, d in enumerate(decisions):
            if self.index_decision(d):
                count += 1
            if (i + 1) % 10 == 0:
                print(f"  Indexed {i + 1}/{len(decisions)}...")
        return count
    
    def query(
        self,
        context: str,
        n_results: int = 5,
        category: Optional[str] = None,
        min_confidence: Optional[float] = None,
    ) -> list[dict]:
        """Query similar decisions."""
        coll_id = self.ensure_collection()
        if not coll_id:
            return []
        
        embedding = generate_embedding(context)
        
        # Build where clause
        where = {}
        if category:
            where["category"] = category
        if min_confidence is not None:
            where["confidence"] = {"$gte": min_confidence}
        
        base = get_api_base()
        payload = {
            "query_embeddings": [embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            payload["where"] = where
        
        status, data = api_request(
            "POST",
            f"{base}/collections/{coll_id}/query",
            payload
        )
        
        if status != 200:
            print(f"Query error: {status} {data}")
            return []
        
        results = []
        if data.get("documents") and data["documents"][0]:
            for i, doc in enumerate(data["documents"][0]):
                results.append({
                    "content": doc,
                    "metadata": data["metadatas"][0][i] if data.get("metadatas") else {},
                    "distance": data["distances"][0][i] if data.get("distances") else None,
                })
        
        return results
    
    def count(self) -> int:
        """Count indexed decisions."""
        coll_id = self.ensure_collection()
        if not coll_id:
            return 0
        
        base = get_api_base()
        status, data = api_request("GET", f"{base}/collections/{coll_id}/count")
        return data if status == 200 and isinstance(data, int) else 0


# Singleton instance
_index = None

def get_index() -> SemanticIndex:
    """Get singleton index instance."""
    global _index
    if _index is None:
        _index = SemanticIndex()
    return _index
