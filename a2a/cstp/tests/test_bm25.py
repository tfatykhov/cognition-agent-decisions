"""Tests for BM25 hybrid retrieval (F017)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from a2a.cstp.bm25_index import (
    BM25Index,
    build_searchable_text,
    merge_results,
    normalize_scores,
    tokenize,
)


class TestTokenize:
    """Tests for tokenize function."""

    def test_basic_tokenization(self) -> None:
        """Test basic word tokenization."""
        tokens = tokenize("Hello World")
        assert tokens == ["hello", "world"]

    def test_preserves_technical_terms(self) -> None:
        """Test technical terms are preserved."""
        tokens = tokenize("Implemented CSRF protection")
        assert "csrf" in tokens
        assert "protection" in tokens

    def test_handles_underscores(self) -> None:
        """Test underscore handling."""
        tokens = tokenize("snake_case variable")
        assert "snake_case" in tokens

    def test_empty_string(self) -> None:
        """Test empty string returns empty list."""
        tokens = tokenize("")
        assert tokens == []


class TestBuildSearchableText:
    """Tests for build_searchable_text function."""

    def test_combines_fields(self) -> None:
        """Test all fields are combined."""
        decision = {
            "summary": "Added CSRF protection",
            "context": "Security improvement needed",
            "category": "security",
        }
        text = build_searchable_text(decision)
        assert "csrf" in text.lower()
        assert "security" in text.lower()

    def test_includes_reasons(self) -> None:
        """Test reason texts are included."""
        decision = {
            "summary": "Test decision",
            "reasons": [
                {"type": "analysis", "text": "Careful analysis showed this was best"},
            ],
        }
        text = build_searchable_text(decision)
        assert "careful" in text.lower()
        assert "analysis" in text.lower()

    def test_handles_missing_fields(self) -> None:
        """Test graceful handling of missing fields."""
        decision = {}
        text = build_searchable_text(decision)
        assert text == ""


class TestBM25Index:
    """Tests for BM25Index class."""

    def test_build_from_decisions(self) -> None:
        """Test index building."""
        decisions = [
            {"id": "1", "summary": "CSRF protection added"},
            {"id": "2", "summary": "OAuth login implemented"},
        ]
        index = BM25Index.from_decisions(decisions)
        assert len(index.doc_ids) == 2

    def test_exact_keyword_match(self) -> None:
        """Test BM25 finds exact keyword matches."""
        decisions = [
            {"id": "1", "summary": "Implemented CSRF protection"},
            {"id": "2", "summary": "Added OAuth login flow"},
            {"id": "3", "summary": "General security improvements"},
        ]
        index = BM25Index.from_decisions(decisions)
        results = index.search("CSRF", top_k=3)

        # CSRF decision should be first
        assert len(results) > 0
        assert results[0][0] == "1"

    def test_empty_corpus(self) -> None:
        """Test handling empty corpus."""
        index = BM25Index.from_decisions([])
        results = index.search("test")
        assert results == []

    def test_no_matching_terms(self) -> None:
        """Test query with no matches returns empty."""
        decisions = [{"id": "1", "summary": "Python code"}]
        index = BM25Index.from_decisions(decisions)
        results = index.search("javascript", top_k=5)
        assert results == []


class TestNormalizeScores:
    """Tests for normalize_scores function."""

    def test_normalizes_to_0_1(self) -> None:
        """Test scores normalized to 0-1 range."""
        results = [("a", 10.0), ("b", 5.0), ("c", 0.0)]
        normalized = normalize_scores(results)

        assert normalized["a"] == 1.0
        assert normalized["c"] == 0.0
        assert 0 < normalized["b"] < 1

    def test_handles_single_result(self) -> None:
        """Test single result gets score 1.0."""
        results = [("a", 5.0)]
        normalized = normalize_scores(results)
        assert normalized["a"] == 1.0

    def test_empty_results(self) -> None:
        """Test empty results returns empty dict."""
        normalized = normalize_scores([])
        assert normalized == {}


class TestMergeResults:
    """Tests for merge_results function."""

    def test_combines_both_sources(self) -> None:
        """Test hybrid mode combines semantic and keyword."""
        semantic = [("1", 0.9), ("2", 0.7)]
        keyword = [("3", 0.95), ("1", 0.5)]

        merged = merge_results(semantic, keyword, semantic_weight=0.7, top_k=5)

        # All unique docs should be present
        doc_ids = [doc_id for doc_id, _ in merged]
        assert "1" in doc_ids
        assert "2" in doc_ids
        assert "3" in doc_ids

    def test_respects_weights(self) -> None:
        """Test weight affects ranking."""
        semantic = [("1", 1.0)]
        keyword = [("2", 1.0)]

        # High semantic weight
        merged_sem = merge_results(semantic, keyword, semantic_weight=0.9, top_k=2)
        assert merged_sem[0][0] == "1"  # Semantic result should be first

        # High keyword weight
        merged_kw = merge_results(semantic, keyword, semantic_weight=0.1, top_k=2)
        assert merged_kw[0][0] == "2"  # Keyword result should be first

    def test_top_k_limit(self) -> None:
        """Test top_k limits results."""
        semantic = [("1", 0.9), ("2", 0.8), ("3", 0.7)]
        keyword = [("4", 0.95), ("5", 0.85)]

        merged = merge_results(semantic, keyword, top_k=3)
        assert len(merged) == 3

    def test_score_breakdown(self) -> None:
        """Test merged results include score breakdown."""
        semantic = [("1", 0.8)]
        keyword = [("1", 0.6)]

        merged = merge_results(semantic, keyword, semantic_weight=0.7)

        # Should have score breakdown
        doc_id, scores = merged[0]
        assert "semantic" in scores
        assert "keyword" in scores
        assert "combined" in scores
