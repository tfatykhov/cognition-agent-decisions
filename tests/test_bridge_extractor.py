"""Tests for F024 Phase 3: Bridge auto-extraction."""

import unittest

from a2a.cstp.bridge_extractor import (
    auto_extract_bridge,
    _score_as_function,
    _score_as_structure,
)
from a2a.cstp.decision_service import (
    BridgeDefinition,
    Reason,
    RecordDecisionRequest,
)


class TestScoring(unittest.TestCase):
    """Test scoring heuristics."""

    def test_function_scoring(self):
        assert _score_as_function("to prevent failures") > 0
        assert _score_as_function("to enable search") > 0
        assert _score_as_function("for security reasons") > 0
        assert _score_as_function("random technical text") == 0

    def test_structure_scoring(self):
        assert _score_as_structure("implemented a new endpoint") > 0
        assert _score_as_structure("added dataclass with schema") > 0
        assert _score_as_structure("merged PR #49") > 0
        assert _score_as_structure("why we should do this") == 0

    def test_file_paths_boost_structure(self):
        score_with = _score_as_structure("changed file.py")
        score_without = _score_as_structure("changed something")
        assert score_with > score_without


class TestAutoExtract(unittest.TestCase):
    """Test auto_extract_bridge function."""

    def test_basic_extraction(self):
        req = RecordDecisionRequest(
            decision="Added retry with backoff to API client",
            confidence=0.8,
            category="architecture",
            context="The API was failing intermittently. Implemented exponential backoff to handle transient failures.",
            reasons=[
                Reason(type="analysis", text="To prevent cascade failures in production"),
                Reason(type="pattern", text="Standard retry pattern used in distributed systems"),
            ],
        )
        bridge = auto_extract_bridge(req)
        assert bridge is not None
        assert bridge.structure  # Should have structure
        assert bridge.function  # Should have function

    def test_no_context(self):
        req = RecordDecisionRequest(
            decision="Switched to plain hyphens",
            confidence=0.9,
            category="process",
        )
        bridge = auto_extract_bridge(req)
        # Should still extract something from decision text
        assert bridge is not None
        assert bridge.structure

    def test_function_from_reasons(self):
        req = RecordDecisionRequest(
            decision="Used fail-open for tracking",
            confidence=0.85,
            category="architecture",
            reasons=[
                Reason(type="analysis", text="To prevent telemetry failures from breaking the core API"),
                Reason(type="empirical", text="CI green after changes"),
            ],
        )
        bridge = auto_extract_bridge(req)
        assert bridge is not None
        assert "prevent" in bridge.function.lower() or "telemetry" in bridge.function.lower()

    def test_explicit_bridge_skipped_by_hook(self):
        """Hook should not overwrite an explicit bridge."""
        from a2a.cstp.bridge_hook import maybe_auto_extract_bridge

        req = RecordDecisionRequest(
            decision="Added retry logic to API client",
            confidence=0.8,
            category="process",
            bridge=BridgeDefinition(
                structure="explicit structure",
                function="explicit function",
            ),
        )
        result = maybe_auto_extract_bridge(req)
        assert result is False
        assert req.bridge.structure == "explicit structure"
        assert req.bridge.function == "explicit function"

    def test_truncation(self):
        req = RecordDecisionRequest(
            decision="test " * 100,
            confidence=0.8,
            category="process",
            context="context " * 100,
        )
        bridge = auto_extract_bridge(req)
        if bridge:
            assert len(bridge.structure) <= 500
            assert len(bridge.function) <= 500

    def test_empty_decision(self):
        req = RecordDecisionRequest(
            decision="",
            confidence=0.8,
            category="process",
        )
        bridge = auto_extract_bridge(req)
        # Empty decision should produce None
        assert bridge is None

    def test_decision_with_function_signals(self):
        req = RecordDecisionRequest(
            decision="To prevent data loss, enabled automatic backups",
            confidence=0.9,
            category="process",
        )
        bridge = auto_extract_bridge(req)
        assert bridge is not None
        # Decision has function signals, so it should go to function side
        assert "prevent" in bridge.function.lower() or "backup" in bridge.function.lower()


if __name__ == "__main__":
    unittest.main()
