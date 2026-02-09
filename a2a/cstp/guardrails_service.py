"""Guardrails evaluation service for CSTP.

Wraps the existing check.py guardrail evaluation logic.
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Configure audit logger
_audit_logger = logging.getLogger("cstp.guardrails.audit")

# Guardrail cache (cleared on process restart)
_guardrails_cache: dict[str, tuple[list["Guardrail"], float]] = {}
_CACHE_TTL_SECONDS = 300  # 5 minute cache

# Configurable guardrails paths
GUARDRAILS_PATHS = os.getenv(
    "GUARDRAILS_PATHS",
    "",
).split(":") if os.getenv("GUARDRAILS_PATHS") else []


@dataclass
class GuardrailCondition:
    """Condition that triggers a guardrail."""

    field: str
    operator: str
    value: Any

    def evaluate(self, context: dict[str, Any]) -> bool:
        """Evaluate condition against context."""
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

    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Check requirement against context."""
        actual = context.get(self.field)
        if actual is None:
            return False, f"Missing: {self.field}"

        if isinstance(self.expected, bool):
            passed = bool(actual) == self.expected
        elif isinstance(self.expected, str) and self.expected.startswith(
            (">=", "<=", ">", "<")
        ):
            match = re.match(r"([><]=?)\s*([\d.]+)", self.expected)
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

    def applies_to(self, context: dict[str, Any]) -> bool:
        """Check if guardrail applies to this context."""
        if self.scope:
            project = context.get("project", context.get("scope", ""))
            if project and project not in self.scope:
                return False

        for cond in self.conditions:
            if not cond.evaluate(context):
                return False
        return True

    def evaluate(self, context: dict[str, Any]) -> dict[str, Any]:
        """Evaluate guardrail against context."""
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
                    "description": self.description,
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
            "description": self.description,
        }


def _parse_condition(field_name: str, value: Any) -> GuardrailCondition:
    """Parse a condition from YAML."""
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
            return GuardrailCondition(field_name, op, val)
    return GuardrailCondition(field_name, "eq", value)


def _parse_guardrail(data: dict[str, Any]) -> Guardrail:
    """Parse a guardrail from dict."""
    conditions = []
    requirements = []
    scope: list[str] = []

    # Support nested format: condition: {field: value, ...}
    if "condition" in data and isinstance(data["condition"], dict):
        for field_name, value in data["condition"].items():
            conditions.append(_parse_condition(field_name, value))

    # Support nested format: requires: {field: value, ...}
    if "requires" in data and isinstance(data["requires"], dict):
        for field_name, value in data["requires"].items():
            requirements.append(GuardrailRequirement(field_name, value))

    # Support flat format: condition_field, requires_field
    for key, value in data.items():
        if key.startswith("condition_"):
            conditions.append(_parse_condition(key[10:], value))
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


def _get_guardrails_paths(guardrails_dir: Path | None = None) -> list[Path]:
    """Get list of guardrail directories to search.

    If guardrails_dir is provided, ONLY that directory is used (for testing).
    Otherwise, uses GUARDRAILS_PATHS env var + default locations.
    """
    # If custom directory provided, use ONLY that (for testing isolation)
    if guardrails_dir:
        return [guardrails_dir]

    paths: list[Path] = []

    # Configurable paths from environment
    for p in GUARDRAILS_PATHS:
        if p.strip():
            paths.append(Path(p.strip()).expanduser())

    # Default paths (relative to package and cwd)
    paths.extend([
        Path(__file__).parent.parent.parent / "guardrails",
        Path.cwd() / "guardrails",
    ])

    return paths


def _load_guardrails_from_paths(paths: list[Path]) -> list[Guardrail]:
    """Load guardrails from YAML files in given paths."""
    guardrails: list[Guardrail] = []
    seen_ids: set[str] = set()

    for dir_path in paths:
        if not dir_path.exists():
            continue
        for yaml_path in dir_path.glob("*.yaml"):
            try:
                content = yaml_path.read_text()

                # Use PyYAML if available (preferred)
                try:
                    import yaml
                    items = yaml.safe_load(content)
                    if items is None:
                        continue
                    if not isinstance(items, list):
                        items = [items]
                except ImportError:
                    # Fallback: skip if no yaml and content is complex
                    _audit_logger.warning(
                        f"PyYAML not installed, skipping {yaml_path}. "
                        "Install pyyaml for guardrail support."
                    )
                    continue

                for item in items:
                    if isinstance(item, dict):
                        g = _parse_guardrail(item)
                        if g.id not in seen_ids:
                            guardrails.append(g)
                            seen_ids.add(g.id)
            except Exception as e:
                _audit_logger.warning(f"Failed to load {yaml_path}: {e}")

    return guardrails


def _load_guardrails(guardrails_dir: Path | None = None) -> list[Guardrail]:
    """Load guardrails with caching.

    Guardrails are cached for 5 minutes to avoid repeated disk I/O.
    """
    import time

    cache_key = str(guardrails_dir) if guardrails_dir else "__default__"
    now = time.time()

    # Check cache
    if cache_key in _guardrails_cache:
        cached_guardrails, cached_at = _guardrails_cache[cache_key]
        if now - cached_at < _CACHE_TTL_SECONDS:
            return cached_guardrails

    # Load from disk
    paths = _get_guardrails_paths(guardrails_dir)
    guardrails = _load_guardrails_from_paths(paths)

    # Update cache
    _guardrails_cache[cache_key] = (guardrails, now)

    return guardrails


def clear_guardrails_cache() -> None:
    """Clear the guardrails cache. Use after modifying guardrail files."""
    _guardrails_cache.clear()


@dataclass(slots=True)
class GuardrailResult:
    """Result of guardrail evaluation."""

    guardrail_id: str
    name: str
    message: str
    severity: str
    suggestion: str | None = None


@dataclass(slots=True)
class EvaluationResult:
    """Result of full guardrail evaluation."""

    allowed: bool
    violations: list[GuardrailResult]
    warnings: list[GuardrailResult]
    evaluated: int


def list_guardrails(scope: str | None = None) -> list[dict[str, Any]]:
    """List active guardrails, optionally filtered by scope.

    Args:
        scope: Optional project/scope filter. If provided, returns only
               guardrails that would apply to this scope (or are global).

    Returns:
        List of guardrail definitions as dicts.
    """
    guardrails = _load_guardrails()
    result = []

    for g in guardrails:
        # Filter by scope if requested
        if scope:
            # If guardrail has specific scopes, and requested scope isn't in them
            if g.scope and scope not in g.scope:
                continue

        # Convert to dict
        g_dict = {
            "id": g.id,
            "description": g.description,
            "action": g.action,
            "scope": g.scope,
            "conditions": [
                {"field": c.field, "operator": c.operator, "value": c.value}
                for c in g.conditions
            ],
            "requirements": [
                {"field": r.field, "expected": r.expected}
                for r in g.requirements
            ],
        }
        result.append(g_dict)

    return result


async def evaluate_guardrails(
    context: dict[str, Any],
    guardrails_dir: Path | None = None,
) -> EvaluationResult:
    """Evaluate context against all guardrails.

    Args:
        context: Evaluation context (category, stakes, confidence, etc.)
        guardrails_dir: Optional custom guardrails directory.

    Returns:
        EvaluationResult with violations, warnings, and allow/block decision.

    Note:
        Guardrails are cached for 5 minutes. Call clear_guardrails_cache()
        after modifying guardrail files.
    """
    guardrails = _load_guardrails(guardrails_dir)

    violations: list[GuardrailResult] = []
    warnings: list[GuardrailResult] = []
    allowed = True

    for g in guardrails:
        result = g.evaluate(context)
        if result.get("matched") and result.get("action") != "skip":
            if not result.get("passed", True):
                gr = GuardrailResult(
                    guardrail_id=result["id"],
                    name=result.get("description", result["id"]),
                    message=result.get("message", ""),
                    severity=result["action"],
                    suggestion=None,
                )
                if result["action"] == "block":
                    violations.append(gr)
                    allowed = False
                else:
                    warnings.append(gr)

    return EvaluationResult(
        allowed=allowed,
        violations=violations,
        warnings=warnings,
        evaluated=len(guardrails),
    )


async def evaluate_record_guardrails(
    request: Any,
) -> list[dict[str, Any]]:
    """F026: Evaluate guardrails against a recordDecision request.

    Builds record context from the request and returns guardrail warnings.
    Shared between JSON-RPC dispatcher and MCP server.

    Args:
        request: RecordDecisionRequest with deliberation, decision, etc.

    Returns:
        List of warning dicts (empty if no guardrails triggered).
    """
    delib_input_count = len(request.deliberation.inputs) if request.deliberation else 0
    record_context = {
        "description": request.decision,
        "category": request.category,
        "stakes": request.stakes,
        "confidence": request.confidence,
        "deliberation_inputs_count": delib_input_count,
        "has_deliberation": delib_input_count > 0,
        "phase": "record",
    }

    # F027 P3: Add quality score to context for guardrail evaluation
    if hasattr(request, "pattern") or hasattr(request, "tags"):
        from .decision_service import score_decision_quality
        quality = score_decision_quality(request)
        record_context["quality_score"] = quality["score"]

    record_eval = await evaluate_guardrails(record_context)
    warnings: list[dict[str, Any]] = []
    for v in record_eval.violations:
        warnings.append({
            "guardrail_id": v.guardrail_id,
            "message": v.message,
            "severity": "block",
        })
    for w in record_eval.warnings:
        warnings.append({
            "guardrail_id": w.guardrail_id,
            "message": w.message,
        })
    return warnings


def log_guardrail_check(
    requesting_agent: str,
    action_description: str,
    allowed: bool,
    violations: list[GuardrailResult],
    evaluated: int,
) -> None:
    """Log guardrail check for audit purposes.

    Args:
        requesting_agent: Agent ID that requested the check.
        action_description: What action was being checked.
        allowed: Whether the action was allowed.
        violations: List of violations if any.
        evaluated: Number of guardrails evaluated.
    """
    audit_entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "event": "guardrail_check",
        "requesting_agent": requesting_agent,
        "action": action_description,
        "allowed": allowed,
        "violations": [v.guardrail_id for v in violations],
        "evaluated": evaluated,
    }
    _audit_logger.info(json.dumps(audit_entry))
