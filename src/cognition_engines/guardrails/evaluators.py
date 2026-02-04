"""
Condition Evaluators for Guardrail v2
Supports semantic similarity, temporal, and aggregate conditions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol


class ConditionEvaluator(Protocol):
    """Protocol for condition evaluators."""
    
    def evaluate(self, condition: dict, context: dict) -> bool:
        """Evaluate condition against context."""
        ...


@dataclass
class FieldCondition:
    """Simple field comparison condition."""
    field: str
    operator: str  # eq, ne, lt, gt, lte, gte, in, contains
    value: any
    
    def evaluate(self, context: dict) -> bool:
        actual = context.get(self.field)
        if actual is None:
            return False
        
        ops = {
            "eq": lambda a, v: a == v,
            "ne": lambda a, v: a != v,
            "lt": lambda a, v: float(a) < float(v),
            "gt": lambda a, v: float(a) > float(v),
            "lte": lambda a, v: float(a) <= float(v),
            "gte": lambda a, v: float(a) >= float(v),
            "in": lambda a, v: a in v,
            "contains": lambda a, v: v in str(a),
        }
        
        op_fn = ops.get(self.operator)
        if op_fn:
            try:
                return op_fn(actual, self.value)
            except (ValueError, TypeError):
                return False
        return False


@dataclass 
class SemanticCondition:
    """
    Semantic similarity condition.
    Checks if context is similar to past decisions matching criteria.
    """
    query_field: str  # Field to use as query (e.g., "decision", "context")
    threshold: float  # Similarity threshold (0-1, lower = more similar)
    filter_outcome: str | None = None  # Filter by outcome (success, failure)
    filter_since_days: int | None = None  # Only check recent decisions
    min_matches: int = 1  # Minimum similar decisions to trigger
    
    def evaluate(self, context: dict, index=None) -> tuple[bool, list]:
        """
        Evaluate semantic similarity.
        Returns (matches_condition, matching_decisions).
        
        Note: Requires semantic index to be passed in.
        """
        if index is None:
            # No index available, skip this condition
            return False, []
        
        query_text = context.get(self.query_field, "")
        if not query_text:
            return False, []
        
        try:
            # Query similar decisions
            results = index.query(query_text, n_results=10)
            
            matches = []
            for r in results:
                # Check distance threshold
                if r.get("distance", 1.0) > self.threshold:
                    continue
                
                # Check outcome filter
                if self.filter_outcome:
                    if r.get("metadata", {}).get("outcome") != self.filter_outcome:
                        continue
                
                # Check recency filter
                if self.filter_since_days:
                    decision_date = r.get("metadata", {}).get("date", "")
                    if decision_date:
                        try:
                            dt = datetime.fromisoformat(decision_date.replace("Z", "+00:00"))
                            cutoff = datetime.now(dt.tzinfo) - timedelta(days=self.filter_since_days)
                            if dt < cutoff:
                                continue
                        except ValueError:
                            pass
                
                matches.append(r)
            
            return len(matches) >= self.min_matches, matches
            
        except Exception:
            return False, []


@dataclass
class TemporalCondition:
    """
    Time-based condition.
    Checks if similar decision was made within time window.
    """
    field: str  # Field to match on
    value: any  # Value to match
    within_hours: int  # Time window in hours
    
    def evaluate(self, context: dict, decision_history: list = None) -> bool:
        """
        Check if matching decision exists within time window.
        """
        if not decision_history:
            return False
        
        target_value = context.get(self.field)
        if target_value is None:
            return False
        
        cutoff = datetime.utcnow() - timedelta(hours=self.within_hours)
        
        for decision in decision_history:
            if decision.get(self.field) != target_value:
                continue
            
            decision_date = decision.get("date", "")
            if decision_date:
                try:
                    dt = datetime.fromisoformat(decision_date.replace("Z", "+00:00"))
                    if dt.replace(tzinfo=None) > cutoff:
                        return True
                except ValueError:
                    pass
        
        return False


@dataclass
class AggregateCondition:
    """
    Statistical aggregate condition.
    Checks aggregate stats across decisions.
    """
    category: str | None = None  # Filter by category
    metric: str = "success_rate"  # success_rate, avg_confidence, count
    operator: str = "lt"  # Comparison operator
    value: float = 0.5  # Threshold value
    min_decisions: int = 5  # Minimum decisions for stat to be valid
    
    def evaluate(self, decisions: list) -> bool:
        """Check aggregate condition against decision history."""
        # Filter by category if specified
        if self.category:
            decisions = [d for d in decisions if d.get("category") == self.category]
        
        if len(decisions) < self.min_decisions:
            return False  # Not enough data
        
        # Calculate metric
        if self.metric == "success_rate":
            with_outcomes = [d for d in decisions if d.get("outcome")]
            if not with_outcomes:
                return False
            successes = sum(1 for d in with_outcomes if d.get("outcome") == "success")
            stat = successes / len(with_outcomes)
        
        elif self.metric == "avg_confidence":
            confs = [d.get("confidence", 0) for d in decisions if d.get("confidence") is not None]
            if not confs:
                return False
            stat = sum(confs) / len(confs)
            if stat > 1:
                stat = stat / 100  # Normalize percentages
        
        elif self.metric == "count":
            stat = len(decisions)
        
        else:
            return False
        
        # Compare
        ops = {
            "lt": lambda s, v: s < v,
            "gt": lambda s, v: s > v,
            "lte": lambda s, v: s <= v,
            "gte": lambda s, v: s >= v,
            "eq": lambda s, v: abs(s - v) < 0.01,
        }
        
        op_fn = ops.get(self.operator)
        return op_fn(stat, self.value) if op_fn else False


class CompoundCondition:
    """
    Compound condition with AND/OR logic.
    """
    
    def __init__(self, operator: str, conditions: list):
        """
        Args:
            operator: 'and' or 'or'
            conditions: List of condition objects
        """
        self.operator = operator.lower()
        self.conditions = conditions
    
    def evaluate(self, context: dict, **kwargs) -> bool:
        """Evaluate compound condition."""
        results = []
        
        for cond in self.conditions:
            if hasattr(cond, 'evaluate'):
                if isinstance(cond, (SemanticCondition, TemporalCondition)):
                    result = cond.evaluate(context, **kwargs)
                    if isinstance(result, tuple):
                        result = result[0]
                else:
                    result = cond.evaluate(context)
                results.append(result)
        
        if self.operator == "and":
            return all(results)
        elif self.operator == "or":
            return any(results)
        
        return False


def parse_condition_v2(condition_def: dict) -> FieldCondition | SemanticCondition | TemporalCondition | AggregateCondition | CompoundCondition:
    """
    Parse a v2 condition definition from YAML.
    
    Supports:
    - type: field (default)
    - type: semantic_similarity
    - type: temporal
    - type: aggregate
    - type: compound (and/or)
    """
    cond_type = condition_def.get("type", "field")
    
    if cond_type == "field":
        return FieldCondition(
            field=condition_def.get("field", ""),
            operator=condition_def.get("operator", "eq"),
            value=condition_def.get("value"),
        )
    
    elif cond_type == "semantic_similarity":
        return SemanticCondition(
            query_field=condition_def.get("query_field", "decision"),
            threshold=condition_def.get("threshold", 0.8),
            filter_outcome=condition_def.get("filter_outcome"),
            filter_since_days=condition_def.get("filter_since_days"),
            min_matches=condition_def.get("min_matches", 1),
        )
    
    elif cond_type == "temporal":
        return TemporalCondition(
            field=condition_def.get("field", ""),
            value=condition_def.get("value"),
            within_hours=condition_def.get("within_hours", 24),
        )
    
    elif cond_type == "aggregate":
        return AggregateCondition(
            category=condition_def.get("category"),
            metric=condition_def.get("metric", "success_rate"),
            operator=condition_def.get("operator", "lt"),
            value=condition_def.get("value", 0.5),
            min_decisions=condition_def.get("min_decisions", 5),
        )
    
    elif cond_type == "compound":
        sub_conditions = [
            parse_condition_v2(sub) for sub in condition_def.get("conditions", [])
        ]
        return CompoundCondition(
            operator=condition_def.get("operator", "and"),
            conditions=sub_conditions,
        )
    
    # Fallback to field condition
    return FieldCondition(
        field=condition_def.get("field", ""),
        operator=condition_def.get("operator", "eq"),
        value=condition_def.get("value"),
    )
