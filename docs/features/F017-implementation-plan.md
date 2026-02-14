# F017 Implementation Plan: Hybrid Retrieval Scoring

**Spec:** `docs/features/V0.9.0-FEATURES.md`  
**Skill:** python-pro  
**Complexity:** Medium (~3 hours)

---

## Overview

Combine semantic search (ChromaDB embeddings) with BM25 keyword search to improve recall for exact term matches like "CSRF", "OAuth", etc.

---

## API Changes

### New Parameters for `cstp.queryDecisions`

```json
{
  "query": "CSRF protection",
  "retrieval_mode": "semantic",  // "semantic" | "keyword" | "hybrid"
  "hybrid_weight": 0.7,          // semantic weight (keyword = 1 - this)
  "top_k": 10
}
```

### Response Enhancement

```json
{
  "decisions": [...],
  "scores": {
    "d1234": {"semantic": 0.85, "keyword": 0.72, "combined": 0.81}
  },
  "retrieval_mode": "hybrid"
}
```

---

## Implementation Steps

### Phase 1: BM25 Index (45 min)

#### Step 1.1: Add rank-bm25 dependency

**File:** `pyproject.toml` (a2a section)

```toml
dependencies = [
    ...
    "rank-bm25>=0.2.2",
]
```

#### Step 1.2: Create BM25 index module

**File:** `a2a/cstp/bm25_index.py`

```python
"""BM25 keyword search index for decisions."""
from __future__ import annotations

from dataclasses import dataclass
from rank_bm25 import BM25Okapi
import re


@dataclass
class BM25Index:
    """BM25 index for keyword search."""
    
    bm25: BM25Okapi
    doc_ids: list[str]
    
    @classmethod
    def from_decisions(cls, decisions: list[dict]) -> "BM25Index":
        """Build index from decisions."""
        corpus = []
        doc_ids = []
        
        for d in decisions:
            text = build_searchable_text(d)
            tokens = tokenize(text)
            corpus.append(tokens)
            doc_ids.append(d["id"])
        
        bm25 = BM25Okapi(corpus)
        return cls(bm25=bm25, doc_ids=doc_ids)
    
    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search index and return (doc_id, score) pairs."""
        tokens = tokenize(query)
        scores = self.bm25.get_scores(tokens)
        
        # Get top-k indices
        results = []
        for idx in scores.argsort()[::-1][:top_k]:
            if scores[idx] > 0:
                results.append((self.doc_ids[idx], float(scores[idx])))
        
        return results


def tokenize(text: str) -> list[str]:
    """Simple tokenization."""
    return re.findall(r'\w+', text.lower())


def build_searchable_text(decision: dict) -> str:
    """Build searchable text from decision fields."""
    parts = [
        decision.get("summary", ""),
        decision.get("decision", ""),
        decision.get("context", ""),
    ]
    
    # Add reason texts
    for r in decision.get("reasons", []):
        if isinstance(r, dict):
            parts.append(r.get("text", ""))
    
    return " ".join(parts)
```

---

### Phase 2: Hybrid Query Service (45 min)

#### Step 2.1: Add retrieval mode to QueryDecisionsRequest

**File:** `a2a/cstp/decision_service.py`

```python
@dataclass
class QueryDecisionsRequest:
    query: str
    top_k: int = 10
    category: str | None = None
    stakes: str | None = None
    project: str | None = None
    # F017: Hybrid retrieval
    retrieval_mode: str = "semantic"  # semantic | keyword | hybrid
    hybrid_weight: float = 0.7  # semantic weight
```

#### Step 2.2: Implement hybrid search logic

```python
async def query_decisions_hybrid(
    request: QueryDecisionsRequest,
    decisions: list[dict],
    semantic_results: list[tuple[str, float]],
) -> list[tuple[str, dict]]:
    """Merge semantic and keyword results."""
    
    if request.retrieval_mode == "semantic":
        return semantic_results
    
    # Build BM25 index
    bm25_index = BM25Index.from_decisions(decisions)
    keyword_results = bm25_index.search(request.query, request.top_k * 2)
    
    if request.retrieval_mode == "keyword":
        return keyword_results
    
    # Hybrid: merge with weighted scores
    return merge_results(
        semantic_results,
        keyword_results,
        semantic_weight=request.hybrid_weight,
        top_k=request.top_k,
    )
```

---

### Phase 3: Score Merging (30 min)

#### Step 3.1: Implement reciprocal rank fusion

```python
def merge_results(
    semantic: list[tuple[str, float]],
    keyword: list[tuple[str, float]],
    semantic_weight: float = 0.7,
    top_k: int = 10,
) -> list[tuple[str, dict]]:
    """Merge results using weighted reciprocal rank fusion."""
    
    # Normalize scores to 0-1 range
    sem_scores = normalize_scores(semantic)
    kw_scores = normalize_scores(keyword)
    
    # Combine
    all_ids = set(sem_scores.keys()) | set(kw_scores.keys())
    combined = {}
    
    keyword_weight = 1 - semantic_weight
    for doc_id in all_ids:
        sem = sem_scores.get(doc_id, 0.0)
        kw = kw_scores.get(doc_id, 0.0)
        combined[doc_id] = {
            "semantic": sem,
            "keyword": kw,
            "combined": semantic_weight * sem + keyword_weight * kw,
        }
    
    # Sort by combined score
    ranked = sorted(combined.items(), key=lambda x: x[1]["combined"], reverse=True)
    return ranked[:top_k]
```

---

### Phase 4: Integration (30 min)

#### Step 4.1: Update query_decisions to use hybrid

Modify the existing `query_decisions` function to call hybrid logic.

#### Step 4.2: Update response to include scores

Add `scores` field to QueryDecisionsResponse.

---

### Phase 5: Tests (30 min)

```python
def test_bm25_exact_match():
    """Test BM25 finds exact keyword matches."""
    decisions = [
        {"id": "1", "summary": "Implemented CSRF protection"},
        {"id": "2", "summary": "Added OAuth login flow"},
        {"id": "3", "summary": "Security improvements"},
    ]
    index = BM25Index.from_decisions(decisions)
    results = index.search("CSRF", top_k=3)
    
    assert results[0][0] == "1"  # CSRF decision should be first

def test_hybrid_combines_both():
    """Test hybrid mode combines semantic and keyword."""
    # Mock semantic results
    semantic = [("1", 0.9), ("2", 0.7)]
    keyword = [("3", 0.95), ("1", 0.5)]
    
    merged = merge_results(semantic, keyword, semantic_weight=0.7)
    
    # Both sources contribute
    assert any(r[0] == "3" for r in merged)  # keyword-only result included
```

---

## Checklist

| # | Task | Est. | Status |
|---|------|------|--------|
| 1 | Add rank-bm25 dependency | 5m | ⬜ |
| 2 | Create bm25_index.py | 30m | ⬜ |
| 3 | Add retrieval_mode to request | 10m | ⬜ |
| 4 | Implement merge_results | 20m | ⬜ |
| 5 | Update query_decisions | 30m | ⬜ |
| 6 | Add scores to response | 15m | ⬜ |
| 7 | Tests | 30m | ⬜ |
| 8 | Run ruff locally | 5m | ⬜ |
| 9 | Create PR + wait for CI | 15m | ⬜ |

**Total:** ~3 hours

---

## Notes

- BM25Okapi is the standard variant
- Reciprocal Rank Fusion (RRF) is an alternative to weighted scores
- Default hybrid_weight=0.7 favors semantic (handles synonyms better)
