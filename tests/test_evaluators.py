"""Tests for guardrail evaluators v2."""

from cognition_engines.guardrails.evaluators import (
    FieldCondition,
    SemanticCondition,
    TemporalCondition,
    AggregateCondition,
    CompoundCondition,
    parse_condition_v2,
)


class TestFieldCondition:
    """Test field condition evaluation."""

    def test_eq_operator(self):
        cond = FieldCondition("status", "eq", "active")
        assert cond.evaluate({"status": "active"}) is True
        assert cond.evaluate({"status": "inactive"}) is False

    def test_lt_operator(self):
        cond = FieldCondition("confidence", "lt", 0.5)
        assert cond.evaluate({"confidence": 0.3}) is True
        assert cond.evaluate({"confidence": 0.7}) is False

    def test_gte_operator(self):
        cond = FieldCondition("count", "gte", 10)
        assert cond.evaluate({"count": 10}) is True
        assert cond.evaluate({"count": 15}) is True
        assert cond.evaluate({"count": 5}) is False

    def test_contains_operator(self):
        cond = FieldCondition("message", "contains", "error")
        assert cond.evaluate({"message": "an error occurred"}) is True
        assert cond.evaluate({"message": "all good"}) is False

    def test_in_operator(self):
        cond = FieldCondition("category", "in", ["arch", "process"])
        assert cond.evaluate({"category": "arch"}) is True
        assert cond.evaluate({"category": "other"}) is False

    def test_missing_field(self):
        cond = FieldCondition("missing", "eq", "value")
        assert cond.evaluate({}) is False

    def test_string_operator_in_value(self):
        """Test parsing operators from string values like '> 10'."""
        cond = FieldCondition("amount", "eq", "> 10")
        assert cond.evaluate({"amount": 15}) is True
        assert cond.evaluate({"amount": 5}) is False

    def test_string_operator_gte(self):
        cond = FieldCondition("score", "eq", ">= 50")
        assert cond.evaluate({"score": 50}) is True
        assert cond.evaluate({"score": 49}) is False


class TestSemanticCondition:
    """Test semantic similarity condition."""

    def test_no_index_returns_false(self):
        cond = SemanticCondition("decision", threshold=0.8)
        result, matches = cond.evaluate({"decision": "test"}, index=None)
        assert result is False
        assert matches == []

    def test_empty_query_field(self):
        cond = SemanticCondition("decision", threshold=0.8)
        result, matches = cond.evaluate({}, index=None)
        assert result is False


class TestTemporalCondition:
    """Test temporal condition."""

    def test_no_history_returns_false(self):
        cond = TemporalCondition("category", "arch", within_hours=24)
        assert cond.evaluate({"category": "arch"}, decision_history=None) is False
        assert cond.evaluate({"category": "arch"}, decision_history=[]) is False

    def test_missing_context_field(self):
        cond = TemporalCondition("category", "arch", within_hours=24)
        assert cond.evaluate({}, decision_history=[{"category": "arch"}]) is False


class TestAggregateCondition:
    """Test aggregate condition."""

    def test_not_enough_decisions(self):
        cond = AggregateCondition(metric="success_rate", operator="lt", value=0.5, min_decisions=5)
        decisions = [{"outcome": "success"}]  # Only 1 decision
        assert cond.evaluate(decisions) is False

    def test_success_rate_calculation(self):
        cond = AggregateCondition(metric="success_rate", operator="lt", value=0.5, min_decisions=2)
        decisions = [
            {"outcome": "failure"},
            {"outcome": "failure"},
            {"outcome": "success"},
        ]
        # Success rate = 1/3 = 0.33 < 0.5
        assert cond.evaluate(decisions) is True

    def test_success_rate_above_threshold(self):
        cond = AggregateCondition(metric="success_rate", operator="lt", value=0.5, min_decisions=2)
        decisions = [
            {"outcome": "success"},
            {"outcome": "success"},
        ]
        # Success rate = 1.0, not < 0.5
        assert cond.evaluate(decisions) is False

    def test_category_filter(self):
        cond = AggregateCondition(
            category="arch",
            metric="success_rate",
            operator="lt",
            value=0.5,
            min_decisions=2
        )
        decisions = [
            {"category": "arch", "outcome": "failure"},
            {"category": "arch", "outcome": "failure"},
            {"category": "other", "outcome": "success"},
        ]
        # Only arch decisions: 0/2 = 0.0 < 0.5
        assert cond.evaluate(decisions) is True

    def test_avg_confidence_metric(self):
        cond = AggregateCondition(metric="avg_confidence", operator="lt", value=0.6, min_decisions=2)
        decisions = [
            {"confidence": 0.4},
            {"confidence": 0.5},
        ]
        # Avg = 0.45 < 0.6
        assert cond.evaluate(decisions) is True


class TestCompoundCondition:
    """Test compound AND/OR conditions."""

    def test_and_all_true(self):
        cond = CompoundCondition("and", [
            FieldCondition("a", "eq", 1),
            FieldCondition("b", "eq", 2),
        ])
        assert cond.evaluate({"a": 1, "b": 2}) is True

    def test_and_one_false(self):
        cond = CompoundCondition("and", [
            FieldCondition("a", "eq", 1),
            FieldCondition("b", "eq", 2),
        ])
        assert cond.evaluate({"a": 1, "b": 3}) is False

    def test_or_one_true(self):
        cond = CompoundCondition("or", [
            FieldCondition("a", "eq", 1),
            FieldCondition("b", "eq", 2),
        ])
        assert cond.evaluate({"a": 1, "b": 99}) is True

    def test_or_all_false(self):
        cond = CompoundCondition("or", [
            FieldCondition("a", "eq", 1),
            FieldCondition("b", "eq", 2),
        ])
        assert cond.evaluate({"a": 99, "b": 99}) is False


class TestParseConditionV2:
    """Test v2 condition parsing."""

    def test_parse_field_condition(self):
        cond = parse_condition_v2({
            "type": "field",
            "field": "status",
            "operator": "eq",
            "value": "active",
        })
        assert isinstance(cond, FieldCondition)
        assert cond.field == "status"

    def test_parse_semantic_condition(self):
        cond = parse_condition_v2({
            "type": "semantic_similarity",
            "query_field": "context",
            "threshold": 0.7,
            "filter_outcome": "failure",
        })
        assert isinstance(cond, SemanticCondition)
        assert cond.threshold == 0.7

    def test_parse_temporal_condition(self):
        cond = parse_condition_v2({
            "type": "temporal",
            "field": "category",
            "value": "arch",
            "within_hours": 48,
        })
        assert isinstance(cond, TemporalCondition)
        assert cond.within_hours == 48

    def test_parse_aggregate_condition(self):
        cond = parse_condition_v2({
            "type": "aggregate",
            "category": "trading",
            "metric": "success_rate",
            "operator": "lt",
            "value": 0.5,
        })
        assert isinstance(cond, AggregateCondition)
        assert cond.category == "trading"

    def test_parse_compound_condition(self):
        cond = parse_condition_v2({
            "type": "compound",
            "operator": "and",
            "conditions": [
                {"type": "field", "field": "a", "operator": "eq", "value": 1},
                {"type": "field", "field": "b", "operator": "gt", "value": 0},
            ],
        })
        assert isinstance(cond, CompoundCondition)
        assert len(cond.conditions) == 2

    def test_default_to_field(self):
        cond = parse_condition_v2({"field": "x", "value": 1})
        assert isinstance(cond, FieldCondition)
