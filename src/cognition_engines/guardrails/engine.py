"""
Guardrail Definitions & Enforcement
Policy enforcement that prevents violations before they occur
"""

import re
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field


@dataclass
class GuardrailCondition:
    """Condition that triggers a guardrail."""
    field: str
    operator: str  # eq, ne, lt, gt, lte, gte, in, contains
    value: Any
    
    def evaluate(self, context: dict) -> bool:
        """Check if condition matches context."""
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
        elif self.operator == "in":
            return actual in self.value
        elif self.operator == "contains":
            return self.value in str(actual)
        
        return False


@dataclass
class GuardrailRequirement:
    """Requirement that must be met to pass guardrail."""
    field: str
    expected: Any
    
    def check(self, context: dict) -> tuple[bool, str]:
        """Check if requirement is met. Returns (passed, message)."""
        actual = context.get(self.field)
        
        if actual is None:
            return False, f"Missing required field: {self.field}"
        
        if isinstance(self.expected, bool):
            passed = bool(actual) == self.expected
        elif isinstance(self.expected, str) and self.expected.startswith((">=", "<=", ">", "<")):
            # Parse comparison
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
                elif op == "<":
                    passed = actual < val
                else:
                    passed = False
            else:
                passed = False
        else:
            passed = actual == self.expected
        
        if passed:
            return True, ""
        else:
            return False, f"{self.field}: expected {self.expected}, got {actual}"


@dataclass
class Guardrail:
    """A guardrail definition."""
    id: str
    description: str
    conditions: list[GuardrailCondition] = field(default_factory=list)
    requirements: list[GuardrailRequirement] = field(default_factory=list)
    scope: list[str] = field(default_factory=list)  # Empty = all
    action: str = "warn"  # block, warn, log
    message: str = ""
    
    def applies_to(self, context: dict) -> bool:
        """Check if guardrail applies to this context."""
        # Check scope
        if self.scope:
            project = context.get("project", context.get("scope", ""))
            if project and project not in self.scope:
                return False
        
        # Check all conditions
        for cond in self.conditions:
            if not cond.evaluate(context):
                return False
        
        return True
    
    def evaluate(self, context: dict) -> "GuardrailResult":
        """Evaluate guardrail against context."""
        if not self.applies_to(context):
            return GuardrailResult(
                guardrail_id=self.id,
                passed=True,
                action="skip",
                message="Guardrail does not apply",
            )
        
        # If there are requirements, check them
        if self.requirements:
            failed_reqs = []
            for req in self.requirements:
                passed, msg = req.check(context)
                if not passed:
                    failed_reqs.append(msg)
            
            if failed_reqs:
                message = self.message or f"Guardrail {self.id} failed: {'; '.join(failed_reqs)}"
                # Substitute context values in message
                for key, val in context.items():
                    message = message.replace(f"{{{key}}}", str(val))
                
                return GuardrailResult(
                    guardrail_id=self.id,
                    passed=False,
                    action=self.action,
                    message=message,
                    failed_requirements=failed_reqs,
                )
            
            return GuardrailResult(
                guardrail_id=self.id,
                passed=True,
                action="pass",
                message="All requirements met",
            )
        
        # If no requirements, conditions matching means violation
        # (e.g., "if stakes=high AND confidence < 0.5, block")
        message = self.message or f"Guardrail {self.id} triggered"
        for key, val in context.items():
            message = message.replace(f"{{{key}}}", str(val))
        
        return GuardrailResult(
            guardrail_id=self.id,
            passed=False,
            action=self.action,
            message=message,
        )


@dataclass
class GuardrailResult:
    """Result of guardrail evaluation."""
    guardrail_id: str
    passed: bool
    action: str  # pass, skip, warn, block, log
    message: str
    failed_requirements: list[str] = field(default_factory=list)


def parse_condition(field: str, value: Any) -> GuardrailCondition:
    """Parse a condition from YAML format."""
    if isinstance(value, str) and value.startswith(("<", ">", "=")):
        # Parse comparison operator
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


def parse_guardrail(data: dict) -> Guardrail:
    """Parse guardrail from YAML dict (supports both nested and flat formats)."""
    conditions = []
    requirements = []
    scope = []
    
    # Handle nested format
    if "condition" in data and isinstance(data["condition"], dict):
        for field, value in data["condition"].items():
            conditions.append(parse_condition(field, value))
    
    if "requires" in data and isinstance(data["requires"], dict):
        for field, value in data["requires"].items():
            requirements.append(GuardrailRequirement(field, value))
    
    if "scope" in data:
        scope = data["scope"] if isinstance(data["scope"], list) else [data["scope"]]
    
    # Handle flat format (condition_* and requires_* prefixes)
    for key, value in data.items():
        if key.startswith("condition_"):
            field = key[10:]  # Remove "condition_" prefix
            conditions.append(parse_condition(field, value))
        elif key.startswith("requires_"):
            field = key[9:]  # Remove "requires_" prefix
            requirements.append(GuardrailRequirement(field, value))
    
    return Guardrail(
        id=data.get("id", "unknown"),
        description=data.get("description", ""),
        conditions=conditions,
        requirements=requirements,
        scope=scope,
        action=data.get("action", "warn"),
        message=data.get("message", ""),
    )


class GuardrailEngine:
    """Engine for loading and evaluating guardrails."""
    
    def __init__(self):
        self.guardrails: list[Guardrail] = []
    
    def load_from_yaml(self, content: str) -> int:
        """Load guardrails from YAML content. Returns count loaded."""
        data = None
        
        # Try PyYAML first
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            # Fallback to basic parsing
            data = self._parse_yaml_basic(content)
        except Exception as e:
            print(f"YAML parse error: {e}")
            return 0
        
        if data is None:
            return 0
        
        if isinstance(data, list):
            for item in data:
                self.guardrails.append(parse_guardrail(item))
        elif isinstance(data, dict) and "guardrails" in data:
            for item in data["guardrails"]:
                self.guardrails.append(parse_guardrail(item))
        elif isinstance(data, dict):
            self.guardrails.append(parse_guardrail(data))
        
        return len(self.guardrails)
    
    def _parse_yaml_basic(self, content: str) -> list:
        """Basic YAML list parsing without external deps."""
        items = []
        current_item = None
        current_section = None
        
        for line in content.split('\n'):
            # Skip empty lines and comments
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue
            
            # New list item at root level (starts with "- ")
            if line.startswith('- '):
                if current_item:
                    items.append(current_item)
                current_item = {}
                current_section = None
                
                # Check if there's key: value on same line
                rest = line[2:].strip()
                if ':' in rest:
                    key, val = rest.split(':', 1)
                    val = val.strip()
                    if val:
                        current_item[key.strip()] = self._parse_value(val)
                    else:
                        current_section = key.strip()
                        current_item[current_section] = {}
            
            # Nested content
            elif current_item is not None and line.startswith('  '):
                stripped = line.strip()
                if ':' in stripped:
                    key, val = stripped.split(':', 1)
                    key = key.strip()
                    val = val.strip()
                    
                    if val:
                        if current_section and isinstance(current_item.get(current_section), dict):
                            current_item[current_section][key] = self._parse_value(val)
                        else:
                            current_item[key] = self._parse_value(val)
                    else:
                        current_section = key
                        current_item[key] = {}
                elif stripped.startswith('- '):
                    # List value
                    val = stripped[2:].strip()
                    if current_section:
                        if not isinstance(current_item.get(current_section), list):
                            current_item[current_section] = []
                        current_item[current_section].append(self._parse_value(val))
        
        if current_item:
            items.append(current_item)
        
        return items
    
    def _parse_value(self, val: str):
        """Parse a YAML value."""
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
    
    def load_from_file(self, path: Path) -> int:
        """Load guardrails from YAML file."""
        content = path.read_text()
        return self.load_from_yaml(content)
    
    def load_from_directory(self, directory: Path) -> int:
        """Load all guardrails from directory."""
        count = 0
        existing_ids = {g.id for g in self.guardrails}
        
        for path in directory.glob("*.yaml"):
            loaded = self._load_from_file_dedup(path, existing_ids)
            count += loaded
        for path in directory.glob("*.yml"):
            loaded = self._load_from_file_dedup(path, existing_ids)
            count += loaded
        return count
    
    def _load_from_file_dedup(self, path: Path, existing_ids: set) -> int:
        """Load guardrails from file, skipping duplicates."""
        content = path.read_text()
        data = None
        
        try:
            import yaml
            data = yaml.safe_load(content)
        except ImportError:
            data = self._parse_yaml_basic(content)
        except Exception as e:
            print(f"YAML parse error in {path}: {e}")
            return 0
        
        if data is None:
            return 0
        
        count = 0
        items = data if isinstance(data, list) else [data]
        
        for item in items:
            if isinstance(item, dict):
                guardrail = parse_guardrail(item)
                if guardrail.id not in existing_ids:
                    self.guardrails.append(guardrail)
                    existing_ids.add(guardrail.id)
                    count += 1
        
        return count
    
    def evaluate(self, context: dict) -> list[GuardrailResult]:
        """Evaluate all guardrails against context."""
        results = []
        for guardrail in self.guardrails:
            result = guardrail.evaluate(context)
            if result.action != "skip":
                results.append(result)
        return results
    
    def check(self, context: dict) -> tuple[bool, list[GuardrailResult]]:
        """
        Check if decision passes all guardrails.
        Returns (allowed, results).
        """
        results = self.evaluate(context)
        
        # Check for any blocking failures
        for result in results:
            if not result.passed and result.action == "block":
                return False, results
        
        return True, results
    
    def list_guardrails(self) -> list[dict]:
        """List all loaded guardrails."""
        return [
            {
                "id": g.id,
                "description": g.description,
                "action": g.action,
                "scope": g.scope,
            }
            for g in self.guardrails
        ]


# Singleton instance
_engine = None

def get_engine() -> GuardrailEngine:
    """Get singleton engine instance."""
    global _engine
    if _engine is None:
        _engine = GuardrailEngine()
    return _engine


def load_default_guardrails() -> int:
    """Load guardrails from default locations."""
    engine = get_engine()
    count = 0
    
    # Check common locations
    paths = [
        Path(__file__).parent.parent.parent.parent / "guardrails",
        Path.cwd() / "guardrails",
        Path.home() / ".cognition" / "guardrails",
    ]
    
    for path in paths:
        if path.exists() and path.is_dir():
            count += engine.load_from_directory(path)
    
    return count
