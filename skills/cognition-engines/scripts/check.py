#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""
Check guardrails before making a decision.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class GuardrailCondition:
    """Condition that triggers a guardrail."""
    field: str
    operator: str
    value: Any
    
    def evaluate(self, context: dict) -> bool:
        actual = context.get(self.field)
        if actual is None:
            return False
        
        if self.operator == "eq":
            return actual == self.value
        elif self.operator == "ne":
            return actual != self.value
        elif self.operator == "lt":
            return float(actual) < float(self.value)
        elif self.operator == "gt":
            return float(actual) > float(self.value)
        elif self.operator == "lte":
            return float(actual) <= float(self.value)
        elif self.operator == "gte":
            return float(actual) >= float(self.value)
        return False


@dataclass
class GuardrailRequirement:
    """Requirement that must be met."""
    field: str
    expected: Any
    
    def check(self, context: dict) -> tuple[bool, str]:
        actual = context.get(self.field)
        if actual is None:
            return False, f"Missing: {self.field}"
        
        if isinstance(self.expected, bool):
            passed = bool(actual) == self.expected
        elif isinstance(self.expected, str) and self.expected.startswith((">=", "<=", ">", "<")):
            match = re.match(r"([><=]+)\s*([\d.]+)", self.expected)
            if match:
                op, val = match.groups()
                val = float(val)
                actual = float(actual)
                if op == ">=":
                    passed = actual >= val
                elif op == "<=":
                    passed = actual <= val
                elif op == ">":
                    passed = actual > val
                else:
                    passed = actual < val
            else:
                passed = False
        else:
            passed = actual == self.expected
        
        return passed, "" if passed else f"{self.field}: expected {self.expected}, got {actual}"


@dataclass
class Guardrail:
    """A guardrail definition."""
    id: str
    description: str
    conditions: list[GuardrailCondition] = field(default_factory=list)
    requirements: list[GuardrailRequirement] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)
    action: str = "warn"
    message: str = ""
    
    def applies_to(self, context: dict) -> bool:
        if self.scope:
            project = context.get("project", context.get("scope", ""))
            if project and project not in self.scope:
                return False
        
        for cond in self.conditions:
            if not cond.evaluate(context):
                return False
        return True
    
    def evaluate(self, context: dict) -> dict:
        if not self.applies_to(context):
            return {"id": self.id, "matched": False, "action": "skip"}
        
        if self.requirements:
            failed = []
            for req in self.requirements:
                passed, msg = req.check(context)
                if not passed:
                    failed.append(msg)
            
            if failed:
                message = self.message or f"{self.id}: {'; '.join(failed)}"
                for k, v in context.items():
                    message = message.replace(f"{{{k}}}", str(v))
                return {
                    "id": self.id,
                    "matched": True,
                    "passed": False,
                    "action": self.action,
                    "message": message,
                }
            return {"id": self.id, "matched": True, "passed": True, "action": "pass"}
        
        # No requirements = condition match means violation
        message = self.message or f"Guardrail {self.id} triggered"
        for k, v in context.items():
            message = message.replace(f"{{{k}}}", str(v))
        return {
            "id": self.id,
            "matched": True,
            "passed": False,
            "action": self.action,
            "message": message,
        }


def parse_condition(field: str, value: Any) -> GuardrailCondition:
    if isinstance(value, str) and value.startswith(("<", ">", "=")):
        match = re.match(r"([<>=!]+)\s*(.*)", value)
        if match:
            op_str, val = match.groups()
            op_map = {"<": "lt", ">": "gt", "<=": "lte", ">=": "gte", "==": "eq", "!=": "ne"}
            op = op_map.get(op_str, "eq")
            try:
                val = float(val)
            except ValueError:
                pass
            return GuardrailCondition(field, op, val)
    return GuardrailCondition(field, "eq", value)


def parse_yaml_value(val: str):
    if val.lower() == 'true':
        return True
    if val.lower() == 'false':
        return False
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    try:
        return float(val)
    except ValueError:
        return val


def parse_yaml_basic(content: str) -> list:
    """Basic YAML list parsing."""
    items = []
    current = None
    
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        
        if line.startswith('- '):
            if current:
                items.append(current)
            current = {}
            rest = line[2:].strip()
            if ':' in rest:
                key, val = rest.split(':', 1)
                val = val.strip()
                if val:
                    current[key.strip()] = parse_yaml_value(val)
        elif current is not None and line.startswith('  ') and ':' in stripped:
            key, val = stripped.split(':', 1)
            key = key.strip()
            val = val.strip()
            if val:
                current[key] = parse_yaml_value(val)
    
    if current:
        items.append(current)
    return items


def parse_guardrail(data: dict) -> Guardrail:
    conditions = []
    requirements = []
    scope = []
    
    for key, value in data.items():
        if key.startswith("condition_"):
            conditions.append(parse_condition(key[10:], value))
        elif key.startswith("requires_"):
            requirements.append(GuardrailRequirement(key[9:], value))
    
    if "scope" in data:
        scope = data["scope"] if isinstance(data["scope"], list) else [data["scope"]]
    
    return Guardrail(
        id=data.get("id", "unknown"),
        description=data.get("description", ""),
        conditions=conditions,
        requirements=requirements,
        scope=scope,
        action=data.get("action", "warn"),
        message=data.get("message", ""),
    )


def load_guardrails() -> list[Guardrail]:
    """Load guardrails from default locations."""
    guardrails = []
    seen_ids = set()
    
    paths = [
        Path(__file__).parent.parent / "guardrails",
        Path("/home/node/.openclaw/workspace/cognition-agent-decisions/guardrails"),
        Path.cwd() / "guardrails",
    ]
    
    for dir_path in paths:
        if not dir_path.exists():
            continue
        for yaml_path in dir_path.glob("*.yaml"):
            try:
                content = yaml_path.read_text()
                try:
                    import yaml
                    items = yaml.safe_load(content)
                    if not isinstance(items, list):
                        items = [items]
                except ImportError:
                    items = parse_yaml_basic(content)
                
                for item in items:
                    if isinstance(item, dict):
                        g = parse_guardrail(item)
                        if g.id not in seen_ids:
                            guardrails.append(g)
                            seen_ids.add(g.id)
            except Exception as e:
                print(f"Warning: Failed to load {yaml_path}: {e}", file=sys.stderr)
    
    return guardrails


def check_guardrails(context: dict) -> dict:
    """Check all guardrails against context."""
    guardrails = load_guardrails()
    
    results = []
    violations = []
    allowed = True
    
    for g in guardrails:
        result = g.evaluate(context)
        if result.get("matched") and result.get("action") != "skip":
            results.append(result)
            if not result.get("passed", True):
                violations.append({
                    "guardrail": result["id"],
                    "action": result["action"],
                    "message": result.get("message", ""),
                })
                if result["action"] == "block":
                    allowed = False
    
    return {
        "allowed": allowed,
        "context": context,
        "evaluated": len(guardrails),
        "matched": len(results),
        "violations": violations,
    }


def main():
    parser = argparse.ArgumentParser(description="Check guardrails before a decision")
    parser.add_argument("--category", help="Decision category")
    parser.add_argument("--stakes", choices=["low", "medium", "high"], help="Stakes level")
    parser.add_argument("--confidence", type=float, help="Confidence level (0-1)")
    parser.add_argument("--project", help="Project scope")
    parser.add_argument("--affects-production", action="store_true", help="Affects production")
    parser.add_argument("--code-review", action="store_true", help="Code review completed")
    parser.add_argument("--context", type=json.loads, help="Full context as JSON")
    parser.add_argument("--format", choices=["json", "text"], default="json")
    
    args = parser.parse_args()
    
    # Build context from args
    context = args.context or {}
    if args.category:
        context["category"] = args.category
    if args.stakes:
        context["stakes"] = args.stakes
    if args.confidence is not None:
        context["confidence"] = args.confidence
    if args.project:
        context["project"] = args.project
    if args.affects_production:
        context["affects_production"] = True
    if args.code_review:
        context["code_review"] = True
    
    result = check_guardrails(context)
    
    if args.format == "json":
        print(json.dumps(result, indent=2))
    else:
        if result["allowed"]:
            print("✅ ALLOWED - All guardrails passed")
        else:
            print("❌ BLOCKED - Guardrail violation")
        
        print(f"\nEvaluated: {result['evaluated']} guardrails")
        print(f"Matched: {result['matched']}")
        
        if result["violations"]:
            print("\nViolations:")
            for v in result["violations"]:
                icon = "🚫" if v["action"] == "block" else "⚠️"
                print(f"  {icon} {v['guardrail']}: {v['message']}")
    
    return 0 if result["allowed"] else 1


if __name__ == "__main__":
    sys.exit(main())
