"""Tests for cstp.getDecision endpoint."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from a2a.cstp.decision_service import (
    GetDecisionRequest,
    GetDecisionResponse,
    get_decision,
)


@pytest.fixture
def decisions_dir():
    """Create a temp directory with sample decision files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create directory structure
        month_dir = Path(tmpdir) / "2026" / "02"
        month_dir.mkdir(parents=True)

        # Write a sample decision
        decision_data = {
            "title": "Test decision for getDecision endpoint",
            "decision": "Test decision for getDecision endpoint",
            "confidence": 0.85,
            "category": "architecture",
            "stakes": "medium",
            "status": "pending",
            "context": "Testing the new getDecision endpoint",
            "reasons": [
                {"type": "analysis", "text": "Need to verify endpoint works"},
                {"type": "pattern", "text": "Similar endpoints exist"},
            ],
            "project": "tfatykhov/cognition-agent-decisions",
            "pr": 99,
            "created_at": "2026-02-08T12:00:00+00:00",
            "recorded_by": "test-agent",
        }

        filepath = month_dir / "2026-02-08-decision-abc12345.yaml"
        with open(filepath, "w") as f:
            yaml.dump(decision_data, f, default_flow_style=False)

        # Write another decision
        decision_data_2 = {
            "title": "Second test decision",
            "decision": "Second test decision",
            "confidence": 0.90,
            "category": "process",
            "stakes": "low",
            "status": "reviewed",
            "outcome": "success",
            "created_at": "2026-02-07T10:00:00+00:00",
        }

        filepath_2 = month_dir / "2026-02-07-decision-def67890.yaml"
        with open(filepath_2, "w") as f:
            yaml.dump(decision_data_2, f, default_flow_style=False)

        yield tmpdir


class TestGetDecisionRequest:
    """Tests for GetDecisionRequest validation."""

    def test_from_dict_with_id(self):
        req = GetDecisionRequest.from_dict({"id": "abc12345"})
        assert req.decision_id == "abc12345"

    def test_from_dict_with_decision_id(self):
        req = GetDecisionRequest.from_dict({"decision_id": "abc12345"})
        assert req.decision_id == "abc12345"

    def test_from_dict_missing_id_raises(self):
        with pytest.raises(ValueError, match="Missing required parameter"):
            GetDecisionRequest.from_dict({})

    def test_from_dict_empty_id_raises(self):
        with pytest.raises(ValueError, match="Missing required parameter"):
            GetDecisionRequest.from_dict({"id": ""})

    def test_from_dict_invalid_id_raises(self):
        with pytest.raises(ValueError, match="Invalid decision ID"):
            GetDecisionRequest.from_dict({"id": "../../../etc/passwd"})

    def test_from_dict_path_traversal_blocked(self):
        with pytest.raises(ValueError, match="Invalid decision ID"):
            GetDecisionRequest.from_dict({"id": "abc/../../def"})


class TestGetDecision:
    """Tests for get_decision function."""

    @pytest.mark.asyncio
    async def test_get_existing_decision(self, decisions_dir):
        with patch.dict(os.environ, {"DECISIONS_PATH": decisions_dir}):
            # Reimport to pick up patched env
            from a2a.cstp import decision_service
            original = decision_service.DECISIONS_PATH
            decision_service.DECISIONS_PATH = decisions_dir
            try:
                req = GetDecisionRequest(decision_id="abc12345")
                resp = await get_decision(req)

                assert resp.found is True
                assert resp.decision is not None
                assert resp.decision["title"] == "Test decision for getDecision endpoint"
                assert resp.decision["confidence"] == 0.85
                assert resp.decision["category"] == "architecture"
                assert resp.decision["context"] == "Testing the new getDecision endpoint"
                assert len(resp.decision["reasons"]) == 2
                assert resp.decision["reasons"][0]["type"] == "analysis"
                assert resp.decision["project"] == "tfatykhov/cognition-agent-decisions"
                assert resp.decision["pr"] == 99
                assert resp.decision["id"] == "abc12345"
            finally:
                decision_service.DECISIONS_PATH = original

    @pytest.mark.asyncio
    async def test_get_nonexistent_decision(self, decisions_dir):
        from a2a.cstp import decision_service
        original = decision_service.DECISIONS_PATH
        decision_service.DECISIONS_PATH = decisions_dir
        try:
            req = GetDecisionRequest(decision_id="zzz99999")
            resp = await get_decision(req)

            assert resp.found is False
            assert resp.decision is None
            assert "not found" in resp.error.lower()
        finally:
            decision_service.DECISIONS_PATH = original

    @pytest.mark.asyncio
    async def test_get_decision_partial_id(self, decisions_dir):
        from a2a.cstp import decision_service
        original = decision_service.DECISIONS_PATH
        decision_service.DECISIONS_PATH = decisions_dir
        try:
            req = GetDecisionRequest(decision_id="abc123")
            resp = await get_decision(req)

            assert resp.found is True
            assert resp.decision is not None
            assert resp.decision["id"] == "abc12345"
        finally:
            decision_service.DECISIONS_PATH = original

    @pytest.mark.asyncio
    async def test_get_decision_with_outcome(self, decisions_dir):
        from a2a.cstp import decision_service
        original = decision_service.DECISIONS_PATH
        decision_service.DECISIONS_PATH = decisions_dir
        try:
            req = GetDecisionRequest(decision_id="def67890")
            resp = await get_decision(req)

            assert resp.found is True
            assert resp.decision["outcome"] == "success"
            assert resp.decision["status"] == "reviewed"
        finally:
            decision_service.DECISIONS_PATH = original

    @pytest.mark.asyncio
    async def test_get_decision_missing_directory(self):
        from a2a.cstp import decision_service
        original = decision_service.DECISIONS_PATH
        decision_service.DECISIONS_PATH = "/nonexistent/path"
        try:
            req = GetDecisionRequest(decision_id="abc12345")
            resp = await get_decision(req)

            assert resp.found is False
            assert "not found" in resp.error.lower()
        finally:
            decision_service.DECISIONS_PATH = original


class TestGetDecisionResponse:
    """Tests for GetDecisionResponse serialization."""

    def test_to_dict_found(self):
        resp = GetDecisionResponse(
            found=True,
            decision={"title": "Test", "confidence": 0.9},
        )
        d = resp.to_dict()
        assert d["found"] is True
        assert d["decision"]["title"] == "Test"
        assert "error" not in d

    def test_to_dict_not_found(self):
        resp = GetDecisionResponse(
            found=False,
            error="Decision not found: xyz",
        )
        d = resp.to_dict()
        assert d["found"] is False
        assert "decision" not in d
        assert d["error"] == "Decision not found: xyz"
