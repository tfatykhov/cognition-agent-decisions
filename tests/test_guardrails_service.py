"""Unit tests for guardrails_service.py."""

from pathlib import Path

import pytest

from a2a.cstp.guardrails_service import (
    Guardrail,
    GuardrailCondition,
    GuardrailRequirement,
    _parse_guardrail,
    clear_guardrails_cache,
    evaluate_guardrails,
)


class TestGuardrailCondition:
    """Tests for GuardrailCondition."""

    def test_eq_operator(self) -> None:
        """Equality operator should work."""
        cond = GuardrailCondition("stakes", "eq", "high")
        assert cond.evaluate({"stakes": "high"}) is True
        assert cond.evaluate({"stakes": "low"}) is False

    def test_lt_operator(self) -> None:
        """Less than operator should work."""
        cond = GuardrailCondition("confidence", "lt", 0.5)
        assert cond.evaluate({"confidence": 0.3}) is True
        assert cond.evaluate({"confidence": 0.7}) is False

    def test_gte_operator(self) -> None:
        """Greater than or equal operator should work."""
        cond = GuardrailCondition("confidence", "gte", 0.5)
        assert cond.evaluate({"confidence": 0.5}) is True
        assert cond.evaluate({"confidence": 0.3}) is False

    def test_missing_field(self) -> None:
        """Missing field should return False."""
        cond = GuardrailCondition("stakes", "eq", "high")
        assert cond.evaluate({}) is False


class TestGuardrailRequirement:
    """Tests for GuardrailRequirement."""

    def test_bool_requirement(self) -> None:
        """Boolean requirement should check truthiness."""
        req = GuardrailRequirement("code_review", True)
        passed, _ = req.check({"code_review": True})
        assert passed is True

        passed, msg = req.check({"code_review": False})
        assert passed is False
        assert "code_review" in msg

    def test_comparison_requirement(self) -> None:
        """Comparison requirement should work."""
        req = GuardrailRequirement("confidence", ">= 0.5")
        passed, _ = req.check({"confidence": 0.7})
        assert passed is True

        passed, msg = req.check({"confidence": 0.3})
        assert passed is False

    def test_missing_field(self) -> None:
        """Missing field should fail."""
        req = GuardrailRequirement("code_review", True)
        passed, msg = req.check({})
        assert passed is False
        assert "Missing" in msg


class TestGuardrail:
    """Tests for Guardrail."""

    def test_applies_to_with_conditions(self) -> None:
        """Guardrail should only apply when conditions match."""
        g = Guardrail(
            id="test",
            description="Test",
            conditions=[GuardrailCondition("stakes", "eq", "high")],
        )
        assert g.applies_to({"stakes": "high"}) is True
        assert g.applies_to({"stakes": "low"}) is False

    def test_applies_to_with_scope(self) -> None:
        """Guardrail should respect scope."""
        g = Guardrail(
            id="test",
            description="Test",
            scope=["project-a", "project-b"],
        )
        assert g.applies_to({"project": "project-a"}) is True
        assert g.applies_to({"project": "project-c"}) is False

    def test_evaluate_with_requirements(self) -> None:
        """Guardrail should check requirements."""
        g = Guardrail(
            id="needs-review",
            description="Needs code review",
            conditions=[GuardrailCondition("stakes", "eq", "high")],
            requirements=[GuardrailRequirement("code_review", True)],
            action="block",
        )

        # Passes when requirement met
        result = g.evaluate({"stakes": "high", "code_review": True})
        assert result["passed"] is True

        # Fails when requirement not met
        result = g.evaluate({"stakes": "high", "code_review": False})
        assert result["passed"] is False
        assert result["action"] == "block"


class TestParseGuardrail:
    """Tests for _parse_guardrail."""

    def test_parse_basic(self) -> None:
        """Basic guardrail should parse."""
        data = {
            "id": "test-rule",
            "description": "Test rule",
            "action": "block",
            "message": "Test message",
        }
        g = _parse_guardrail(data)
        assert g.id == "test-rule"
        assert g.description == "Test rule"
        assert g.action == "block"

    def test_parse_with_conditions(self) -> None:
        """Guardrail with conditions should parse."""
        data = {
            "id": "test-rule",
            "description": "Test",
            "condition_stakes": "high",
            "condition_confidence": "< 0.5",
        }
        g = _parse_guardrail(data)
        assert len(g.conditions) == 2

    def test_parse_with_requirements(self) -> None:
        """Guardrail with requirements should parse."""
        data = {
            "id": "test-rule",
            "description": "Test",
            "requires_code_review": True,
            "requires_tests": True,
        }
        g = _parse_guardrail(data)
        assert len(g.requirements) == 2


class TestEvaluateGuardrails:
    """Tests for evaluate_guardrails."""

    @pytest.mark.asyncio
    async def test_no_guardrails_returns_allowed(self, tmp_path: Path) -> None:
        """Empty guardrails dir should return allowed."""
        clear_guardrails_cache()  # Clear any cached guardrails
        result = await evaluate_guardrails({}, guardrails_dir=tmp_path)
        assert result.allowed is True
        assert result.evaluated == 0

    @pytest.mark.asyncio
    async def test_with_mock_guardrails(self, tmp_path: Path) -> None:
        """Should evaluate guardrails from file."""
        clear_guardrails_cache()  # Clear cache before test
        # Create a test guardrail file
        guardrail_yaml = tmp_path / "test.yaml"
        guardrail_yaml.write_text("""
- id: no-high-stakes-low-confidence
  description: Block high stakes with low confidence
  condition_stakes: high
  condition_confidence: "< 0.5"
  action: block
  message: High stakes decisions require confidence >= 0.5
""")

        # Should pass with high confidence
        result = await evaluate_guardrails(
            {"stakes": "high", "confidence": 0.8},
            guardrails_dir=tmp_path,
        )
        assert result.allowed is True

        # Should block with low confidence
        result = await evaluate_guardrails(
            {"stakes": "high", "confidence": 0.3},
            guardrails_dir=tmp_path,
        )
        assert result.allowed is False
        assert len(result.violations) == 1
        assert result.violations[0].guardrail_id == "no-high-stakes-low-confidence"
