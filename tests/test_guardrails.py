"""Tests for guardrail engine."""

import pytest
from cognition_engines.guardrails.engine import (
    Guardrail,
    GuardrailCondition,
    GuardrailRequirement,
    GuardrailEngine,
    parse_guardrail,
    parse_condition,
)


class TestGuardrailCondition:
    """Test condition evaluation."""
    
    def test_eq_match(self):
        cond = GuardrailCondition("status", "eq", "active")
        assert cond.evaluate({"status": "active"}) is True
        assert cond.evaluate({"status": "inactive"}) is False
    
    def test_lt_comparison(self):
        cond = GuardrailCondition("confidence", "lt", 0.5)
        assert cond.evaluate({"confidence": 0.3}) is True
        assert cond.evaluate({"confidence": 0.7}) is False
    
    def test_gte_comparison(self):
        cond = GuardrailCondition("confidence", "gte", 0.5)
        assert cond.evaluate({"confidence": 0.5}) is True
        assert cond.evaluate({"confidence": 0.8}) is True
        assert cond.evaluate({"confidence": 0.3}) is False
    
    def test_missing_field(self):
        cond = GuardrailCondition("missing", "eq", "value")
        assert cond.evaluate({}) is False


class TestGuardrailRequirement:
    """Test requirement checking."""
    
    def test_bool_requirement(self):
        req = GuardrailRequirement("code_review", True)
        passed, msg = req.check({"code_review": True})
        assert passed is True
        
        passed, msg = req.check({"code_review": False})
        assert passed is False
    
    def test_comparison_requirement(self):
        req = GuardrailRequirement("confidence", ">= 0.5")
        passed, _ = req.check({"confidence": 0.8})
        assert passed is True
        
        passed, msg = req.check({"confidence": 0.3})
        assert passed is False
    
    def test_missing_field(self):
        req = GuardrailRequirement("required_field", True)
        passed, msg = req.check({})
        assert passed is False
        assert "Missing" in msg


class TestGuardrail:
    """Test guardrail evaluation."""
    
    def test_no_conditions_applies_to_all(self):
        guardrail = Guardrail(
            id="test",
            description="Test guardrail",
            conditions=[],
            requirements=[],
        )
        assert guardrail.applies_to({}) is True
        assert guardrail.applies_to({"any": "context"}) is True
    
    def test_condition_filtering(self):
        guardrail = Guardrail(
            id="test",
            description="Test",
            conditions=[GuardrailCondition("stakes", "eq", "high")],
        )
        assert guardrail.applies_to({"stakes": "high"}) is True
        assert guardrail.applies_to({"stakes": "low"}) is False
    
    def test_scope_filtering(self):
        guardrail = Guardrail(
            id="test",
            description="Test",
            scope=["ProjectA", "ProjectB"],
        )
        assert guardrail.applies_to({"project": "ProjectA"}) is True
        assert guardrail.applies_to({"project": "ProjectC"}) is False
    
    def test_block_on_condition_match_no_requirements(self):
        """When conditions match and no requirements, it should block."""
        guardrail = Guardrail(
            id="no-high-stakes-low-confidence",
            description="Block high stakes with low confidence",
            conditions=[
                GuardrailCondition("stakes", "eq", "high"),
                GuardrailCondition("confidence", "lt", 0.5),
            ],
            action="block",
        )
        
        result = guardrail.evaluate({"stakes": "high", "confidence": 0.3})
        assert result.passed is False
        assert result.action == "block"
    
    def test_pass_when_conditions_dont_match(self):
        guardrail = Guardrail(
            id="test",
            description="Test",
            conditions=[GuardrailCondition("stakes", "eq", "high")],
            action="block",
        )
        
        result = guardrail.evaluate({"stakes": "low"})
        assert result.passed is True
        assert result.action == "skip"


class TestParseCondition:
    """Test condition parsing from YAML values."""
    
    def test_simple_equality(self):
        cond = parse_condition("field", "value")
        assert cond.field == "field"
        assert cond.operator == "eq"
        assert cond.value == "value"
    
    def test_less_than(self):
        cond = parse_condition("confidence", "< 0.5")
        assert cond.operator == "lt"
        assert cond.value == 0.5
    
    def test_greater_equal(self):
        cond = parse_condition("score", ">= 10")
        assert cond.operator == "gte"
        assert cond.value == 10.0


class TestGuardrailEngine:
    """Test engine loading and evaluation."""
    
    def test_load_flat_format(self):
        yaml_content = """
- id: test-guardrail
  description: Test guardrail
  condition_stakes: high
  condition_confidence: "< 0.5"
  action: block
  message: Stakes too high for low confidence
"""
        engine = GuardrailEngine()
        count = engine.load_from_yaml(yaml_content)
        
        assert count == 1
        assert len(engine.guardrails) == 1
        assert engine.guardrails[0].id == "test-guardrail"
    
    def test_check_allows_valid_context(self):
        engine = GuardrailEngine()
        engine.guardrails.append(Guardrail(
            id="test",
            description="Test",
            conditions=[
                GuardrailCondition("stakes", "eq", "high"),
                GuardrailCondition("confidence", "lt", 0.5),
            ],
            action="block",
        ))
        
        # High confidence should pass
        allowed, results = engine.check({"stakes": "high", "confidence": 0.8})
        assert allowed is True
    
    def test_check_blocks_violation(self):
        engine = GuardrailEngine()
        engine.guardrails.append(Guardrail(
            id="test",
            description="Test",
            conditions=[
                GuardrailCondition("stakes", "eq", "high"),
                GuardrailCondition("confidence", "lt", 0.5),
            ],
            action="block",
        ))
        
        # Low confidence should block
        allowed, results = engine.check({"stakes": "high", "confidence": 0.3})
        assert allowed is False
