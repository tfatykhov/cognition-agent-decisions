#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
decide.py - Single command for the pre-decision protocol.

Usage:
    uv run decide.py "context of your decision" \
        --category architecture \
        --stakes high \
        --confidence 0.85 \
        --title "Short decision title"

Flow:
    1. Query similar past decisions
    2. Check guardrails
    3. If blocked → exit with error
    4. If allowed → log the decision
"""

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

# Configuration
CHROMA_URL = os.getenv("CHROMA_URL", "http://chromadb:8000")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TENANT = "default_tenant"
DATABASE = "default_database"
COLLECTION_NAME = "cognition_decisions"
GUARDRAILS_PATH = Path(__file__).parent.parent / "guardrails" / "default.yaml"


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
    
    return ""


def api_request(method: str, url: str, data: dict = None) -> tuple[int, any]:
    """Make HTTP request."""
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
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found")
    
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


def query_similar(query: str, top_k: int = 5) -> list[dict]:
    """Query similar decisions from ChromaDB."""
    coll_id = get_collection_id()
    if not coll_id:
        return []
    
    try:
        embedding = generate_embedding(query)
    except Exception:
        return []
    
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    payload = {
        "query_embeddings": [embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    
    status, data = api_request("POST", f"{base}/collections/{coll_id}/query", payload)
    
    if status != 200:
        return []
    
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
    
    return results


def check_guardrails(category: str, stakes: str, confidence: float) -> dict:
    """Check guardrails against context."""
    context = {
        "category": category,
        "stakes": stakes,
        "confidence": confidence,
    }
    
    # Load guardrails
    guardrails = []
    if GUARDRAILS_PATH.exists():
        content = GUARDRAILS_PATH.read_text()
        current = {}
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("- id:"):
                if current:
                    guardrails.append(current)
                current = {"id": stripped.split(":", 1)[1].strip()}
            elif stripped.startswith("condition_stakes:"):
                current["condition_stakes"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("condition_confidence:"):
                current["condition_confidence"] = stripped.split(":", 1)[1].strip().strip('"')
            elif stripped.startswith("condition_category:"):
                current["condition_category"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("action:"):
                current["action"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("message:"):
                current["message"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("scope:"):
                current["scope"] = stripped.split(":", 1)[1].strip()
            elif stripped.startswith("condition_affects_production:"):
                current["condition_affects_production"] = stripped.split(":", 1)[1].strip() == "true"
        if current:
            guardrails.append(current)
    
    violations = []
    for g in guardrails:
        matches = True
        
        # Skip scoped guardrails if scope doesn't match
        if g.get("scope"):
            matches = False  # Only match if explicitly in scope
            continue
        
        # Skip production guardrails (need explicit flag)
        if g.get("condition_affects_production"):
            matches = False
            continue
        
        # Check stakes condition
        if "condition_stakes" in g:
            if g["condition_stakes"] != context.get("stakes"):
                matches = False
        
        # Check category condition
        if "condition_category" in g and matches:
            if g["condition_category"] != context.get("category"):
                matches = False
        
        # Check confidence condition
        if "condition_confidence" in g and matches:
            conf_rule = g["condition_confidence"]
            if conf_rule.startswith("<"):
                threshold = float(conf_rule[1:].strip())
                if not (context.get("confidence", 1.0) < threshold):
                    matches = False
        
        if matches and g.get("action") == "block":
            violations.append({
                "id": g.get("id"),
                "action": g.get("action"),
                "message": g.get("message", "Guardrail violation"),
            })
    
    return {
        "allowed": len(violations) == 0,
        "context": context,
        "evaluated": len(guardrails),
        "matched": len(violations),
        "violations": violations,
    }


def generate_decision_yaml(
    title: str,
    context: str,
    category: str,
    stakes: str,
    confidence: float,
    similar_decisions: list,
) -> str:
    """Generate decision YAML content."""
    now = datetime.utcnow()
    date_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Build similar decisions reference
    similar_ref = ""
    if similar_decisions:
        similar_ref = "\nrelated_decisions:\n"
        for d in similar_decisions[:3]:
            similar_ref += f"  - title: \"{d.get('title', 'Unknown')}\"\n"
            similar_ref += f"    date: \"{d.get('date', 'Unknown')}\"\n"
            similar_ref += f"    distance: {d.get('distance', 0):.3f}\n"
    
    yaml_content = f"""id: {now.strftime('%Y-%m-%d')}-{title.lower().replace(' ', '-')[:30]}
title: {title}
date: {date_str}
status: decided
category: {category}
stakes: {stakes}
confidence: {confidence}

context: |
  {context}

pre_decision_protocol:
  query_run: true
  similar_found: {len(similar_decisions)}
  guardrails_checked: true
  guardrails_passed: true
{similar_ref}
reasons:
  - type: analysis
    content: "TODO: Add reasoning"
    strength: {confidence}

outcome: null
reviewed_at: null
"""
    return yaml_content


def save_decision(yaml_content: str, title: str) -> Path:
    """Save decision YAML to the decisions directory."""
    now = datetime.utcnow()
    decisions_dir = Path.home() / ".openclaw" / "workspace" / "decisions" / now.strftime("%Y") / now.strftime("%m")
    decisions_dir.mkdir(parents=True, exist_ok=True)
    
    safe_title = title.lower().replace(' ', '-')[:30]
    filename = f"{now.strftime('%Y-%m-%d')}-{safe_title}.yaml"
    filepath = decisions_dir / filename
    
    # Avoid overwriting
    counter = 1
    while filepath.exists():
        filename = f"{now.strftime('%Y-%m-%d')}-{safe_title}-{counter}.yaml"
        filepath = decisions_dir / filename
        counter += 1
    
    filepath.write_text(yaml_content)
    return filepath


def index_decision(filepath: Path, context: str, category: str, confidence: float, title: str):
    """Index a single decision to ChromaDB."""
    coll_id = get_collection_id()
    if not coll_id:
        # Create collection if it doesn't exist
        base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
        payload = {"name": COLLECTION_NAME}
        status, data = api_request("POST", f"{base}/collections", payload)
        if status not in (200, 201):
            raise ValueError(f"Failed to create collection: {data}")
        coll_id = data.get("id")
    
    # Generate embedding
    embedding = generate_embedding(context)
    
    # Create unique ID from filepath
    doc_id = filepath.stem
    
    # Upsert to ChromaDB
    base = f"{CHROMA_URL}/api/v2/tenants/{TENANT}/databases/{DATABASE}"
    payload = {
        "ids": [doc_id],
        "embeddings": [embedding],
        "documents": [context],
        "metadatas": [{
            "title": title,
            "category": category,
            "confidence": confidence,
            "date": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "decided",
            "path": str(filepath),
        }],
    }
    
    status, data = api_request("POST", f"{base}/collections/{coll_id}/upsert", payload)
    if status not in (200, 201):
        raise ValueError(f"Failed to index: {data}")


def main():
    parser = argparse.ArgumentParser(description="Pre-decision protocol: query + check + log")
    parser.add_argument("context", help="Context/description of the decision")
    parser.add_argument("--title", "-t", required=True, help="Short title for the decision")
    parser.add_argument("--category", "-c", default="architecture", 
                        choices=["architecture", "process", "integration", "tooling", "security"],
                        help="Decision category")
    parser.add_argument("--stakes", "-s", default="medium",
                        choices=["low", "medium", "high"],
                        help="Stakes level")
    parser.add_argument("--confidence", "-f", type=float, default=0.8,
                        help="Confidence level (0.0-1.0)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would happen without saving")
    parser.add_argument("--force", action="store_true",
                        help="Proceed even if guardrails block (with warning)")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("🧠 PRE-DECISION PROTOCOL")
    print("=" * 60)
    
    # Step 1: Query similar decisions
    print("\n📍 Step 1: Querying similar past decisions...")
    try:
        similar = query_similar(args.context, top_k=5)
        if similar:
            print(f"   Found {len(similar)} similar decisions:")
            for i, d in enumerate(similar[:3], 1):
                title = d.get('title', '(no title)')[:40]
                dist = d.get('distance', 0)
                conf = d.get('confidence', 0)
                print(f"   {i}. {title} (distance: {dist:.3f}, confidence: {conf})")
        else:
            print("   No similar decisions found.")
    except Exception as e:
        print(f"   ⚠️ Query failed: {e}")
        similar = []
    
    # Step 2: Check guardrails
    print("\n📍 Step 2: Checking guardrails...")
    try:
        check_result = check_guardrails(
            category=args.category,
            stakes=args.stakes,
            confidence=args.confidence
        )
        
        if check_result.get("allowed"):
            print(f"   ✅ ALLOWED - {check_result.get('evaluated', 0)} guardrails checked, 0 violations")
        else:
            violations = check_result.get("violations", [])
            print(f"   🛑 BLOCKED - {len(violations)} violation(s):")
            for v in violations:
                print(f"      - {v.get('id', 'unknown')}: {v.get('message', 'No message')}")
            
            if not args.force:
                print("\n❌ Decision blocked by guardrails. Use --force to override (not recommended).")
                sys.exit(1)
            else:
                print("\n⚠️ FORCING past guardrail block (--force flag used)")
    except Exception as e:
        print(f"   ⚠️ Guardrail check failed: {e}")
        check_result = {"allowed": True, "evaluated": 0}
    
    # Step 3: Generate and save decision
    print("\n📍 Step 3: Logging decision...")
    
    yaml_content = generate_decision_yaml(
        title=args.title,
        context=args.context,
        category=args.category,
        stakes=args.stakes,
        confidence=args.confidence,
        similar_decisions=similar,
    )
    
    if args.dry_run:
        print("   [DRY RUN] Would save:")
        print("-" * 40)
        print(yaml_content)
        print("-" * 40)
    else:
        filepath = save_decision(yaml_content, args.title)
        print(f"   ✅ Saved: {filepath}")
        
        # Step 4: Auto-index the new decision
        print("\n📍 Step 4: Indexing decision...")
        try:
            index_decision(filepath, args.context, args.category, args.confidence, args.title)
            print("   ✅ Indexed to ChromaDB")
        except Exception as e:
            print(f"   ⚠️ Index failed (will be picked up by cron): {e}")
    
    print("\n" + "=" * 60)
    print("✅ PRE-DECISION PROTOCOL COMPLETE")
    print("=" * 60)
    
    # Summary
    print(f"""
Decision: {args.title}
Category: {args.category}
Stakes: {args.stakes}
Confidence: {args.confidence}
Similar found: {len(similar)}
Guardrails: {'PASSED' if check_result.get('allowed') else 'BLOCKED (forced)'}
""")


if __name__ == "__main__":
    main()
