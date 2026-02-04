#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Index decisions to the semantic store.
"""

import argparse
import json
import hashlib
import os
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

# Configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = "cognition_decisions"


def load_gemini_key() -> str:
    """Load Gemini API key."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY:
        return GEMINI_API_KEY
    
    paths = [
        Path("/home/node/.openclaw/workspace/.secrets/gemini.env"),
        Path.home() / ".secrets" / "gemini.env",
    ]
    
    for path in paths:
        if path.exists():
            for line in path.read_text().splitlines():
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    return GEMINI_API_KEY
    
    raise ValueError("GEMINI_API_KEY not found")


def api_request(method: str, url: str, data: dict = None) -> tuple[int, any]:
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
    api_key = load_gemini_key()
    if len(text) > 8000:
        text = text[:8000]
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
    data = {"content": {"parts": [{"text": text}]}}
    
    req = urllib.request.Request(
        url, data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read().decode())
        return result["embedding"]["values"]


def get_or_create_collection() -> str | None:
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    
    status, data = api_request("GET", f"{base}/collections")
    if status == 200 and isinstance(data, list):
        for c in data:
            if c.get("name") == COLLECTION_NAME:
                return c["id"]
    
    status, data = api_request("POST", f"{base}/collections", {"name": COLLECTION_NAME})
    if status in (200, 201):
        return data.get("id")
    
    return None


def get_indexed_ids(coll_id: str) -> set[str]:
    """Get already indexed decision IDs."""
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    status, data = api_request(
        "POST", f"{base}/collections/{coll_id}/get",
        {"include": [], "limit": 10000}
    )
    if status == 200 and data.get("ids"):
        return set(data["ids"])
    return set()


def parse_yaml_value(val: str):
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    try:
        return float(val)
    except ValueError:
        return val


def parse_yaml_simple(content: str) -> dict:
    """Simple YAML parser for decision files."""
    try:
        import yaml
        return yaml.safe_load(content)
    except ImportError:
        pass
    
    result = {}
    current_key = None
    multiline = []
    in_multiline = False
    
    for line in content.split('\n'):
        if line.strip().startswith('#'):
            continue
        
        if in_multiline:
            if line.startswith('  ') or line.strip() == '':
                multiline.append(line.strip())
                continue
            else:
                result[current_key] = '\n'.join(multiline)
                in_multiline = False
        
        if ':' in line and not line.startswith(' '):
            key, val = line.split(':', 1)
            key = key.strip()
            val = val.strip()
            
            if val == '|':
                current_key = key
                multiline = []
                in_multiline = True
            elif val:
                result[key] = parse_yaml_value(val)
            else:
                result[key] = None
    
    if in_multiline and current_key:
        result[current_key] = '\n'.join(multiline)
    
    return result


def decision_to_text(decision: dict) -> str:
    parts = []
    if decision.get("title"):
        parts.append(f"Title: {decision['title']}")
    if decision.get("context"):
        parts.append(f"Context: {decision['context']}")
    if decision.get("decision"):
        parts.append(f"Decision: {decision['decision']}")
    if decision.get("category"):
        parts.append(f"Category: {decision['category']}")
    if decision.get("outcome"):
        parts.append(f"Outcome: {decision['outcome']}")
    return "\n".join(parts)


def decision_id(decision: dict, path: Path = None) -> str:
    if decision.get("id"):
        return decision["id"]
    
    # Generate from path or title+date
    if path:
        return hashlib.md5(str(path).encode()).hexdigest()[:16]
    
    key = f"{decision.get('title', '')}-{decision.get('date', '')}"
    return hashlib.md5(key.encode()).hexdigest()[:16]


def index_decisions(
    decisions_dir: Path,
    incremental: bool = True,
    verbose: bool = False,
) -> dict:
    """Index decisions from directory."""
    
    coll_id = get_or_create_collection()
    if not coll_id:
        return {"error": "Failed to create collection", "indexed": 0}
    
    # Get existing IDs for incremental
    existing_ids = get_indexed_ids(coll_id) if incremental else set()
    
    # Find YAML files
    yaml_files = list(decisions_dir.rglob("*.yaml")) + list(decisions_dir.rglob("*.yml"))
    
    indexed = 0
    skipped = 0
    errors = []
    
    for path in yaml_files:
        try:
            content = path.read_text()
            data = parse_yaml_simple(content)
            
            if not data or not isinstance(data, dict):
                continue
            if "decision" not in data and "title" not in data:
                continue
            
            doc_id = decision_id(data, path)
            
            if doc_id in existing_ids:
                skipped += 1
                continue
            
            text = decision_to_text(data)
            if not text:
                continue
            
            embedding = generate_embedding(text)
            
            metadata = {
                "title": str(data.get("title", ""))[:500],
                "category": str(data.get("category", ""))[:100],
                "confidence": float(data.get("confidence", 0)),
                "status": str(data.get("status", ""))[:50],
                "date": str(data.get("date", ""))[:20],
                "indexed_at": datetime.utcnow().isoformat(),
                "source_file": str(path)[-200:],
            }
            
            base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
            status, resp = api_request(
                "POST", f"{base}/collections/{coll_id}/add",
                {
                    "ids": [doc_id],
                    "documents": [text],
                    "embeddings": [embedding],
                    "metadatas": [metadata],
                }
            )
            
            if status in (200, 201):
                indexed += 1
                if verbose:
                    print(f"  Indexed: {data.get('title', path.name)}")
            else:
                errors.append(f"{path.name}: {resp}")
                
        except Exception as e:
            errors.append(f"{path.name}: {e}")
    
    return {
        "indexed": indexed,
        "skipped": skipped,
        "total_files": len(yaml_files),
        "errors": errors[:10],  # Limit errors in output
    }


def main():
    parser = argparse.ArgumentParser(description="Index decisions to semantic store")
    parser.add_argument("directory", nargs="?", default="decisions/", help="Decisions directory")
    parser.add_argument("--incremental", "-i", action="store_true", default=True,
                       help="Skip already indexed (default)")
    parser.add_argument("--full", action="store_true", help="Re-index all decisions")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    
    args = parser.parse_args()
    
    decisions_dir = Path(args.directory)
    if not decisions_dir.exists():
        result = {"error": f"Directory not found: {decisions_dir}", "indexed": 0}
        print(json.dumps(result, indent=2))
        return 1
    
    try:
        result = index_decisions(
            decisions_dir,
            incremental=not args.full,
            verbose=args.verbose,
        )
        
        if args.format == "json":
            print(json.dumps(result, indent=2))
        else:
            print(f"\nIndexing complete:")
            print(f"  Files found: {result['total_files']}")
            print(f"  Indexed: {result['indexed']}")
            print(f"  Skipped: {result['skipped']}")
            if result.get("errors"):
                print(f"  Errors: {len(result['errors'])}")
        
        return 0 if not result.get("error") else 1
        
    except Exception as e:
        result = {"error": str(e), "indexed": 0}
        print(json.dumps(result, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
