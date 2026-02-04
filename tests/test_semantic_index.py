"""Tests for semantic index."""

from unittest.mock import patch

from cognition_engines.accelerators.semantic_index import (
    SemanticIndex,
    decision_id,
    decision_to_text,
)


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
        assert "Use ChromaDB for vectors" in text
        assert "Need a vector database" in text
        assert "ChromaDB is the best choice" in text
        assert "architecture" in text

    def test_with_reasons(self):
        decision = {
            "title": "Test decision",
            "reasons": [
                {"type": "analysis", "text": "Good fit for use case"},
                {"type": "empirical", "text": "Proven in production"},
            ],
        }
        text = decision_to_text(decision)
        assert "Good fit for use case" in text
        assert "Proven in production" in text

    def test_with_outcome(self):
        decision = {
            "title": "Test decision",
            "outcome": "success",
            "actual_result": "Worked perfectly",
        }
        text = decision_to_text(decision)
        assert "success" in text
        assert "Worked perfectly" in text

    def test_minimal_decision(self):
        decision = {"title": "Minimal"}
        text = decision_to_text(decision)
        assert "Minimal" in text

    def test_empty_decision(self):
        decision = {}
        text = decision_to_text(decision)
        assert text == ""


class TestDecisionId:
    """Test decision ID extraction."""

    def test_from_id_field(self):
        decision = {"id": "abc123", "title": "Test"}
        assert decision_id(decision) == "abc123"

    def test_from_file_path(self):
        decision = {"file_path": "/path/to/decision-xyz.yaml"}
        assert decision_id(decision) == "decision-xyz"

    def test_generated_hash(self):
        decision = {"title": "Test decision"}
        id1 = decision_id(decision)
        id2 = decision_id(decision)
        assert id1 == id2
        assert len(id1) == 8


class TestSemanticIndex:
    """Test semantic index operations."""

    @patch("cognition_engines.accelerators.semantic_index.chromadb")
    def test_init_creates_collection(self, mock_chromadb):
        mock_client = mock_chromadb.PersistentClient.return_value
        mock_client.get_or_create_collection.return_value = None

        SemanticIndex(persist_dir="/tmp/test")

        mock_chromadb.PersistentClient.assert_called_once()
        mock_client.get_or_create_collection.assert_called_once()

    @patch("cognition_engines.accelerators.semantic_index.chromadb")
    def test_add_decision(self, mock_chromadb):
        mock_client = mock_chromadb.PersistentClient.return_value
        mock_collection = mock_client.get_or_create_collection.return_value

        index = SemanticIndex(persist_dir="/tmp/test")
        decision = {"id": "test-1", "title": "Test decision"}
        index.add(decision)

        mock_collection.upsert.assert_called_once()

    @patch("cognition_engines.accelerators.semantic_index.chromadb")
    def test_query(self, mock_chromadb):
        mock_client = mock_chromadb.PersistentClient.return_value
        mock_collection = mock_client.get_or_create_collection.return_value
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "distances": [[0.1, 0.2]],
            "metadatas": [[{"title": "D1"}, {"title": "D2"}]],
        }

        index = SemanticIndex(persist_dir="/tmp/test")
        results = index.query("test query", top_k=2)

        assert len(results) == 2
        mock_collection.query.assert_called_once()
