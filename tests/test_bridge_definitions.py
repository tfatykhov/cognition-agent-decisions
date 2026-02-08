"""Tests for F024: Bridge-Definitions."""

import time
import unittest
from unittest.mock import AsyncMock, patch

from a2a.cstp.decision_service import (
    BridgeDefinition,
    RecordDecisionRequest,
    build_embedding_text,
)


class TestBridgeDefinition(unittest.TestCase):
    """Test BridgeDefinition dataclass."""

    def test_from_dict_basic(self):
        data = {
            "structure": "try/except around telemetry",
            "function": "prevent observability from breaking API",
        }
        bridge = BridgeDefinition.from_dict(data)
        assert bridge.structure == "try/except around telemetry"
        assert bridge.function == "prevent observability from breaking API"
        assert bridge.tolerance == []
        assert bridge.enforcement == []
        assert bridge.prevention == []

    def test_from_dict_full(self):
        data = {
            "structure": "retry with exponential backoff",
            "function": "handle transient network failures",
            "tolerance": ["max retries count", "jitter algorithm"],
            "enforcement": ["must have backoff", "must have timeout"],
            "prevention": ["must not retry non-idempotent calls"],
        }
        bridge = BridgeDefinition.from_dict(data)
        assert bridge.structure == "retry with exponential backoff"
        assert bridge.function == "handle transient network failures"
        assert len(bridge.tolerance) == 2
        assert len(bridge.enforcement) == 2
        assert len(bridge.prevention) == 1

    def test_from_dict_purpose_alias(self):
        """The 'purpose' key should work as alias for 'function'."""
        data = {
            "structure": "pattern X",
            "purpose": "solve problem Y",
        }
        bridge = BridgeDefinition.from_dict(data)
        assert bridge.function == "solve problem Y"

    def test_to_dict_minimal(self):
        bridge = BridgeDefinition(
            structure="pattern A",
            function="solve B",
        )
        d = bridge.to_dict()
        assert d["structure"] == "pattern A"
        assert d["function"] == "solve B"
        assert "tolerance" not in d
        assert "enforcement" not in d
        assert "prevention" not in d

    def test_to_dict_full(self):
        bridge = BridgeDefinition(
            structure="pattern A",
            function="solve B",
            tolerance=["t1"],
            enforcement=["e1", "e2"],
            prevention=["p1"],
        )
        d = bridge.to_dict()
        assert d["tolerance"] == ["t1"]
        assert d["enforcement"] == ["e1", "e2"]
        assert d["prevention"] == ["p1"]

    def test_roundtrip(self):
        original = BridgeDefinition(
            structure="dataclass with from_dict/to_dict",
            function="serialize/deserialize without data loss",
            tolerance=["field ordering"],
            enforcement=["all fields present after roundtrip"],
            prevention=["data loss"],
        )
        d = original.to_dict()
        restored = BridgeDefinition.from_dict(d)
        assert restored.structure == original.structure
        assert restored.function == original.function
        assert restored.tolerance == original.tolerance
        assert restored.enforcement == original.enforcement
        assert restored.prevention == original.prevention

    def test_has_content(self):
        assert BridgeDefinition(structure="x", function="").has_content()
        assert BridgeDefinition(structure="", function="y").has_content()
        assert not BridgeDefinition(structure="", function="").has_content()

    def test_empty_lists(self):
        data = {
            "structure": "x",
            "function": "y",
            "tolerance": [],
            "enforcement": [],
            "prevention": [],
        }
        bridge = BridgeDefinition.from_dict(data)
        d = bridge.to_dict()
        # Empty lists should not appear in output
        assert "tolerance" not in d
        assert "enforcement" not in d
        assert "prevention" not in d


class TestRecordDecisionRequestWithBridge(unittest.TestCase):
    """Test RecordDecisionRequest parsing of bridge field."""

    def test_no_bridge(self):
        data = {
            "decision": "test",
            "confidence": 0.8,
            "category": "process",
        }
        req = RecordDecisionRequest.from_dict(data)
        assert req.bridge is None

    def test_with_bridge(self):
        data = {
            "decision": "use fail-open pattern",
            "confidence": 0.9,
            "category": "architecture",
            "bridge": {
                "structure": "try/except catch-all with debug logging",
                "function": "telemetry failures don't break core API",
            },
        }
        req = RecordDecisionRequest.from_dict(data)
        assert req.bridge is not None
        assert req.bridge.structure == "try/except catch-all with debug logging"
        assert req.bridge.function == "telemetry failures don't break core API"

    def test_with_full_bridge(self):
        data = {
            "decision": "use fail-open pattern",
            "confidence": 0.9,
            "category": "architecture",
            "bridge": {
                "structure": "try/except catch-all with debug logging",
                "function": "telemetry failures don't break core API",
                "tolerance": ["log level", "exception type"],
                "enforcement": ["must catch all", "must log"],
                "prevention": ["must not re-raise", "must not swallow silently"],
            },
        }
        req = RecordDecisionRequest.from_dict(data)
        assert req.bridge is not None
        assert len(req.bridge.tolerance) == 2
        assert len(req.bridge.enforcement) == 2
        assert len(req.bridge.prevention) == 2

    def test_bridge_ignored_if_not_dict(self):
        data = {
            "decision": "test",
            "confidence": 0.8,
            "category": "process",
            "bridge": "not a dict",
        }
        req = RecordDecisionRequest.from_dict(data)
        assert req.bridge is None


class TestEmbeddingWithBridge(unittest.TestCase):
    """Test that bridge fields are included in embedding text."""

    def test_embedding_includes_bridge(self):
        req = RecordDecisionRequest(
            decision="test decision",
            confidence=0.8,
            category="process",
            bridge=BridgeDefinition(
                structure="pattern X",
                function="solve problem Y",
            ),
        )
        text = build_embedding_text(req)
        assert "Structure: pattern X" in text
        assert "Function: solve problem Y" in text

    def test_embedding_without_bridge(self):
        req = RecordDecisionRequest(
            decision="test decision",
            confidence=0.8,
            category="process",
        )
        text = build_embedding_text(req)
        assert "Structure:" not in text
        assert "Function:" not in text

    def test_embedding_empty_bridge(self):
        req = RecordDecisionRequest(
            decision="test decision",
            confidence=0.8,
            category="process",
            bridge=BridgeDefinition(structure="", function=""),
        )
        text = build_embedding_text(req)
        # Empty bridge should not add lines
        assert "Structure:" not in text
        assert "Function:" not in text


if __name__ == "__main__":
    unittest.main()
