"""Tests for F023 Deliberation Traces — schema and storage."""

import tempfile
from pathlib import Path

import pytest
import yaml

from a2a.cstp.decision_service import (
    Deliberation,
    DeliberationInput,
    DeliberationStep,
    RecordDecisionRequest,
    build_decision_yaml,
    generate_decision_id,
    write_decision_file,
)


class TestDeliberationInput:
    """Tests for DeliberationInput dataclass."""

    def test_from_dict_full(self):
        data = {
            "id": "i1",
            "text": "Similar past decision found",
            "source": "cstp:queryDecisions",
            "timestamp": "2026-02-08T14:01:00Z",
        }
        inp = DeliberationInput.from_dict(data)
        assert inp.id == "i1"
        assert inp.text == "Similar past decision found"
        assert inp.source == "cstp:queryDecisions"
        assert inp.timestamp == "2026-02-08T14:01:00Z"

    def test_from_dict_minimal(self):
        data = {"id": "i1", "text": "Some input"}
        inp = DeliberationInput.from_dict(data)
        assert inp.id == "i1"
        assert inp.source is None
        assert inp.timestamp is None

    def test_to_dict_excludes_none(self):
        inp = DeliberationInput(id="i1", text="test")
        d = inp.to_dict()
        assert "source" not in d
        assert "timestamp" not in d
        assert d["id"] == "i1"

    def test_to_dict_full(self):
        inp = DeliberationInput(
            id="i1", text="test", source="memory", timestamp="2026-02-08T14:00:00Z"
        )
        d = inp.to_dict()
        assert d["source"] == "memory"
        assert d["timestamp"] == "2026-02-08T14:00:00Z"


class TestDeliberationStep:
    """Tests for DeliberationStep dataclass."""

    def test_from_dict_full(self):
        data = {
            "step": 1,
            "thought": "Compared options A and B",
            "inputs_used": ["i1", "i2"],
            "timestamp": "2026-02-08T14:01:03Z",
            "duration_ms": 3200,
            "type": "analysis",
            "conclusion": False,
        }
        step = DeliberationStep.from_dict(data)
        assert step.step == 1
        assert step.thought == "Compared options A and B"
        assert step.inputs_used == ["i1", "i2"]
        assert step.duration_ms == 3200
        assert step.type == "analysis"
        assert step.conclusion is False

    def test_from_dict_camel_case(self):
        """Test that camelCase keys also work."""
        data = {
            "step": 2,
            "thought": "Converged",
            "inputsUsed": ["i1", "i3"],
            "durationMs": 4500,
        }
        step = DeliberationStep.from_dict(data)
        assert step.inputs_used == ["i1", "i3"]
        assert step.duration_ms == 4500

    def test_from_dict_minimal(self):
        data = {"step": 1, "thought": "Basic thought"}
        step = DeliberationStep.from_dict(data)
        assert step.inputs_used == []
        assert step.timestamp is None
        assert step.duration_ms is None
        assert step.conclusion is False

    def test_to_dict_excludes_defaults(self):
        step = DeliberationStep(step=1, thought="test")
        d = step.to_dict()
        assert "inputs_used" not in d
        assert "timestamp" not in d
        assert "duration_ms" not in d
        assert "type" not in d
        assert "conclusion" not in d  # False is default, excluded

    def test_to_dict_conclusion_true(self):
        step = DeliberationStep(step=3, thought="final", conclusion=True)
        d = step.to_dict()
        assert d["conclusion"] is True


class TestDeliberation:
    """Tests for Deliberation dataclass."""

    def test_from_dict_full(self):
        data = {
            "inputs": [
                {"id": "i1", "text": "Input one", "source": "query"},
                {"id": "i2", "text": "Input two"},
            ],
            "steps": [
                {"step": 1, "thought": "Step one", "inputs_used": ["i1"]},
                {"step": 2, "thought": "Step two", "inputs_used": ["i1", "i2"], "conclusion": True},
            ],
            "total_duration_ms": 5000,
            "convergence_point": 2,
        }
        delib = Deliberation.from_dict(data)
        assert len(delib.inputs) == 2
        assert len(delib.steps) == 2
        assert delib.total_duration_ms == 5000
        assert delib.convergence_point == 2
        assert delib.has_content() is True

    def test_from_dict_camel_case(self):
        data = {
            "inputs": [],
            "steps": [{"step": 1, "thought": "test"}],
            "totalDurationMs": 3000,
            "convergencePoint": 1,
        }
        delib = Deliberation.from_dict(data)
        assert delib.total_duration_ms == 3000
        assert delib.convergence_point == 1

    def test_empty_has_no_content(self):
        delib = Deliberation()
        assert delib.has_content() is False

    def test_to_dict_roundtrip(self):
        original = Deliberation(
            inputs=[
                DeliberationInput(id="i1", text="test", source="api"),
            ],
            steps=[
                DeliberationStep(step=1, thought="thinking", inputs_used=["i1"], conclusion=True),
            ],
            total_duration_ms=1500,
            convergence_point=1,
        )
        d = original.to_dict()
        restored = Deliberation.from_dict(d)
        assert len(restored.inputs) == 1
        assert restored.inputs[0].id == "i1"
        assert len(restored.steps) == 1
        assert restored.steps[0].conclusion is True
        assert restored.total_duration_ms == 1500


class TestRecordDecisionWithDeliberation:
    """Tests for recording decisions with deliberation traces."""

    def test_from_dict_with_deliberation(self):
        data = {
            "decision": "Use Izhikevich neurons",
            "confidence": 0.85,
            "category": "architecture",
            "stakes": "medium",
            "deliberation": {
                "inputs": [
                    {"id": "i1", "text": "tinyHippo uses Izhikevich", "source": "github"},
                    {"id": "i2", "text": "Membrain uses LIF", "source": "memory"},
                ],
                "steps": [
                    {"step": 1, "thought": "LIF too simple", "inputs_used": ["i1", "i2"]},
                    {"step": 2, "thought": "Izhikevich proven", "inputs_used": ["i1"], "conclusion": True},
                ],
                "total_duration_ms": 8200,
            },
        }
        request = RecordDecisionRequest.from_dict(data)
        assert request.deliberation is not None
        assert len(request.deliberation.inputs) == 2
        assert len(request.deliberation.steps) == 2
        assert request.deliberation.total_duration_ms == 8200

    def test_from_dict_without_deliberation(self):
        """Backward compatible — no deliberation field."""
        data = {
            "decision": "Simple decision",
            "confidence": 0.8,
            "category": "process",
        }
        request = RecordDecisionRequest.from_dict(data)
        assert request.deliberation is None

    def test_build_yaml_includes_deliberation(self):
        request = RecordDecisionRequest(
            decision="Test decision",
            confidence=0.85,
            category="architecture",
            deliberation=Deliberation(
                inputs=[DeliberationInput(id="i1", text="evidence")],
                steps=[DeliberationStep(step=1, thought="reasoned", inputs_used=["i1"])],
                total_duration_ms=5000,
            ),
        )
        decision_id = generate_decision_id()
        yaml_data = build_decision_yaml(request, decision_id)

        assert "deliberation" in yaml_data
        assert len(yaml_data["deliberation"]["inputs"]) == 1
        assert len(yaml_data["deliberation"]["steps"]) == 1
        assert yaml_data["deliberation"]["total_duration_ms"] == 5000

    def test_build_yaml_no_deliberation_when_empty(self):
        request = RecordDecisionRequest(
            decision="No trace",
            confidence=0.8,
            category="process",
        )
        decision_id = generate_decision_id()
        yaml_data = build_decision_yaml(request, decision_id)

        assert "deliberation" not in yaml_data

    def test_write_and_read_with_deliberation(self):
        """Test full write/read cycle with deliberation."""
        request = RecordDecisionRequest(
            decision="Full cycle test",
            confidence=0.9,
            category="architecture",
            deliberation=Deliberation(
                inputs=[
                    DeliberationInput(id="i1", text="query result", source="cstp"),
                    DeliberationInput(id="i2", text="guardrail check", source="cstp"),
                ],
                steps=[
                    DeliberationStep(
                        step=1,
                        thought="Compared approaches",
                        inputs_used=["i1", "i2"],
                        type="analysis",
                        duration_ms=2000,
                    ),
                    DeliberationStep(
                        step=2,
                        thought="Both inputs support option A",
                        inputs_used=["i1", "i2"],
                        type="pattern",
                        conclusion=True,
                        duration_ms=1500,
                    ),
                ],
                total_duration_ms=3500,
                convergence_point=2,
            ),
        )

        with tempfile.TemporaryDirectory() as tmp:
            decision_id = generate_decision_id()
            yaml_data = build_decision_yaml(request, decision_id)
            path = write_decision_file(yaml_data, decision_id, base_path=tmp)

            # Read back and verify
            with open(path) as f:
                loaded = yaml.safe_load(f)

            assert "deliberation" in loaded
            delib = loaded["deliberation"]
            assert len(delib["inputs"]) == 2
            assert delib["inputs"][0]["source"] == "cstp"
            assert len(delib["steps"]) == 2
            assert delib["steps"][1]["conclusion"] is True
            assert delib["total_duration_ms"] == 3500
            assert delib["convergence_point"] == 2
