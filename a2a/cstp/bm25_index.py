"""BM25 keyword search index for decisions (F017).

Provides exact keyword matching to complement semantic search.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

from rank_bm25 import BM25Okapi

# Cache for BM25 index to avoid rebuilding on every request
_index_cache: dict[str, tuple[BM25Index, float, int]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minute TTL
_CACHE_KEY = "default"


@dataclass
class BM25Index:
    """BM25 index for keyword search over decisions.

    Attributes:
        bm25: The BM25Okapi index instance.
        doc_ids: List of decision IDs in corpus order.
        corpus: Tokenized documents for debugging.
    """

    bm25: BM25Okapi
    doc_ids: list[str]
    corpus: list[list[str]] = field(default_factory=list, repr=False)

    @classmethod
    def from_decisions(cls, decisions: list[dict[str, Any]]) -> BM25Index:
        """Build BM25 index from decision documents.

        Args:
            decisions: List of decision dicts with id, summary, context, etc.

        Returns:
            BM25Index ready for search.
        """
        corpus: list[list[str]] = []
        doc_ids: list[str] = []

        for d in decisions:
            doc_id = d.get("id", "")
            if not doc_id:
                continue

            text = build_searchable_text(d)
            tokens = tokenize(text)

            corpus.append(tokens)
            doc_ids.append(doc_id)

        # Handle empty corpus
        if not corpus:
            return cls(bm25=BM25Okapi([[""]]), doc_ids=[], corpus=[])

        bm25 = BM25Okapi(corpus)
        return cls(bm25=bm25, doc_ids=doc_ids, corpus=corpus)

    def search(self, query: str, top_k: int = 10) -> list[tuple[str, float]]:
        """Search index and return ranked (doc_id, score) pairs.

        Args:
            query: Search query string.
            top_k: Maximum results to return.

        Returns:
            List of (doc_id, score) tuples, highest scores first.
        """
        if not self.doc_ids:
            return []

        tokens = tokenize(query)
        if not tokens:
            return []

        scores = self.bm25.get_scores(tokens)

        # Get top-k indices sorted by score descending
        ranked_indices = scores.argsort()[::-1][:top_k]

        results: list[tuple[str, float]] = []
        for idx in ranked_indices:
            score = float(scores[idx])
            if score > 0:
                results.append((self.doc_ids[idx], score))

        return results


def tokenize(text: str) -> list[str]:
    """Tokenize text for BM25 indexing.

    Simple word tokenization with lowercasing.
    Preserves technical terms like CSRF, OAuth, etc.

    Args:
        text: Input text.

    Returns:
        List of lowercase tokens.
    """
    # Match word characters including underscores
    tokens = re.findall(r"\w+", text.lower())
    return tokens


def build_searchable_text(decision: dict[str, Any]) -> str:
    """Build searchable text from decision fields.

    Combines summary, decision text, context, and reasons
    into a single searchable string.

    Args:
        decision: Decision dictionary.

    Returns:
        Combined text for indexing.
    """
    parts: list[str] = []

    # Primary fields
    if summary := decision.get("summary"):
        parts.append(str(summary))
    if dec_text := decision.get("decision"):
        parts.append(str(dec_text))
    if context := decision.get("context"):
        parts.append(str(context))

    # Category and tags
    if category := decision.get("category"):
        parts.append(str(category))
    if tags := decision.get("tags"):
        if isinstance(tags, list):
            parts.extend(str(t) for t in tags)

    # Reason texts
    reasons = decision.get("reasons", [])
    for r in reasons:
        if isinstance(r, dict):
            if reason_text := r.get("text"):
                parts.append(str(reason_text))
            if reason_type := r.get("type"):
                parts.append(str(reason_type))

    return " ".join(parts)


def normalize_scores(results: list[tuple[str, float]]) -> dict[str, float]:
    """Normalize scores to 0-1 range.

    Args:
        results: List of (doc_id, score) tuples.

    Returns:
        Dict mapping doc_id to normalized score.
    """
    if not results:
        return {}

    scores = [s for _, s in results]
    max_score = max(scores)
    min_score = min(scores)

    # Avoid division by zero
    score_range = max_score - min_score
    if score_range == 0:
        return {doc_id: 1.0 for doc_id, _ in results}

    return {
        doc_id: (score - min_score) / score_range for doc_id, score in results
    }


def merge_results(
    semantic_results: list[tuple[str, float]],
    keyword_results: list[tuple[str, float]],
    semantic_weight: float = 0.7,
    top_k: int = 10,
) -> list[tuple[str, dict[str, float]]]:
    """Merge semantic and keyword results using weighted combination.

    Args:
        semantic_results: Results from semantic search (doc_id, score).
        keyword_results: Results from BM25 search (doc_id, score).
        semantic_weight: Weight for semantic scores (0-1).
        top_k: Maximum results to return.

    Returns:
        List of (doc_id, scores_dict) with semantic, keyword, combined scores.
    """
    # Normalize both result sets
    sem_scores = normalize_scores(semantic_results)
    kw_scores = normalize_scores(keyword_results)

    # Combine all document IDs
    all_ids = set(sem_scores.keys()) | set(kw_scores.keys())

    # Calculate combined scores
    keyword_weight = 1.0 - semantic_weight
    combined: dict[str, dict[str, float]] = {}

    for doc_id in all_ids:
        sem = sem_scores.get(doc_id, 0.0)
        kw = kw_scores.get(doc_id, 0.0)
        combined[doc_id] = {
            "semantic": round(sem, 4),
            "keyword": round(kw, 4),
            "combined": round(semantic_weight * sem + keyword_weight * kw, 4),
        }

    # Sort by combined score descending
    ranked = sorted(
        combined.items(),
        key=lambda x: x[1]["combined"],
        reverse=True,
    )

    return ranked[:top_k]


def get_cached_index(
    decisions: list[dict[str, Any]],
    cache_key: str = _CACHE_KEY,
) -> BM25Index:
    """Get or create cached BM25 index.

    Caches the index for _CACHE_TTL_SECONDS to avoid rebuilding on every request.
    Invalidates cache if decision count changes.

    Args:
        decisions: List of decision dicts.
        cache_key: Cache key (use different keys for filtered queries).

    Returns:
        Cached or newly built BM25Index.
    """
    global _index_cache

    now = time.time()
    doc_count = len(decisions)

    # Check cache
    if cache_key in _index_cache:
        cached_index, cached_time, cached_count = _index_cache[cache_key]

        # Valid if within TTL and count matches
        if (now - cached_time) < _CACHE_TTL_SECONDS and cached_count == doc_count:
            return cached_index

    # Build new index
    new_index = BM25Index.from_decisions(decisions)
    _index_cache[cache_key] = (new_index, now, doc_count)

    return new_index


def invalidate_cache(cache_key: str | None = None) -> None:
    """Invalidate BM25 index cache.

    Args:
        cache_key: Specific key to invalidate, or None for all.
    """
    global _index_cache

    if cache_key is None:
        _index_cache.clear()
    elif cache_key in _index_cache:
        del _index_cache[cache_key]
