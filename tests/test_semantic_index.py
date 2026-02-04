"""Tests for semantic index."""

from unittest.mock import patch

    SemanticIndex,
    decision_id,
    decision_to_text,
)
from cognition_engines.accelerators.semantic_index import (


class TestDecisionToText:
    """Test decision serialization for embedding."""

    def test_basic_fields(self):
        decision = {
            "title": "Use ChromaDB for vectors",
            "context": "Need a vector database",
            "decision": "ChromaDB is the best choice",
            "category": "architecture",
        }
        text = decision_to_text(decision)

        assert "Title: Use ChromaDB for vectors" in text
        assert "Context: Need a vector database" in text
        assert "Decision: ChromaDB is the best choice" in text
        assert "Category: architecture" in text

    def test_with_reasons(self):
        decision = {
            "title": "Test",
            "reasons": [
                {"description": "Reason 1"},
                {"description": "Reason 2"},
            ],
        }
        text = decision_to_text(decision)

        assert "Reasons: Reason 1; Reason 2" in text

    def test_empty_decision(self):
        text = decision_to_text({})
        assert text == ""


class TestDecisionId:
    """Test decision ID generation."""

    def test_uses_existing_id(self):
        decision = {"id": "custom-id", "title": "Test"}
        assert decision_id(decision) == "custom-id"

    def test_generates_hash(self):
        decision = {"title": "Test Decision", "date": "2026-02-04"}
        id1 = decision_id(decision)
        id2 = decision_id(decision)

        assert id1 == id2
        assert len(id1) == 16

    def test_different_decisions_different_ids(self):
        d1 = {"title": "Decision 1", "date": "2026-02-04"}
        d2 = {"title": "Decision 2", "date": "2026-02-04"}

        assert decision_id(d1) != decision_id(d2)


class TestSemanticIndex:
    """Test semantic index operations."""

    def test_init(self):
        index = SemanticIndex()
        assert index.collection_id is None

    @patch('cognition_engines.accelerators.semantic_index.get_or_create_collection')
    def test_ensure_collection(self, mock_get_collection):
        mock_get_collection.return_value = "test-collection-id"

        index = SemanticIndex()
        result = index.ensure_collection()

        assert result == "test-collection-id"
        assert index.collection_id == "test-collection-id"

    @patch('cognition_engines.accelerators.semantic_index.get_or_create_collection')
    @patch('cognition_engines.accelerators.semantic_index.generate_embedding')
    @patch('cognition_engines.accelerators.semantic_index.api_request')
    def test_index_decision(self, mock_api, mock_embed, mock_collection):
        mock_collection.return_value = "coll-id"
        mock_embed.return_value = [0.1] * 768
        mock_api.return_value = (200, {})

        index = SemanticIndex()
        result = index.index_decision({
            "title": "Test Decision",
            "decision": "Test content",
            "confidence": 0.8,
        })

        assert result is True
        mock_embed.assert_called_once()
        mock_api.assert_called_once()
