"""F024 Phase 3: Auto-extract bridge-definitions from decision text.

Heuristic extraction of structure (what it looks like) and function
(what problem it solves) from decision text, context, and reasons.

Applied automatically when recordDecision is called without an explicit bridge.
"""

import logging
import re

from .decision_service import BridgeDefinition, RecordDecisionRequest

logger = logging.getLogger(__name__)

# Keywords that signal function/purpose (why, what-for)
_FUNCTION_SIGNALS = [
    "to prevent", "to avoid", "to enable", "to allow", "to fix",
    "to solve", "to handle", "to support", "to improve", "to reduce",
    "to ensure", "to make", "to keep", "so that", "in order to",
    "because", "prevents", "enables", "fixes", "solves", "addresses",
    "for safety", "for reliability", "for performance", "for correctness",
    "for security", "for compatibility", "for consistency",
]

# Keywords that signal structure/pattern (what, how)
_STRUCTURE_SIGNALS = [
    "implemented", "added", "created", "built", "used", "applied",
    "switched to", "moved to", "replaced", "refactored", "extracted",
    "configured", "deployed", "merged", "shipped", "wired",
    "dataclass", "endpoint", "schema", "field", "function", "method",
    "pattern", "approach", "architecture", "design",
]


def _score_as_function(text: str) -> float:
    """Score how likely text describes a function/purpose."""
    lower = text.lower()
    score = 0.0
    for signal in _FUNCTION_SIGNALS:
        if signal in lower:
            score += 1.0
    return score


def _score_as_structure(text: str) -> float:
    """Score how likely text describes a structure/pattern."""
    lower = text.lower()
    score = 0.0
    for signal in _STRUCTURE_SIGNALS:
        if signal in lower:
            score += 1.0
    # File paths and code references boost structure score
    if re.search(r"[a-z_]+\.[a-z]+", lower):  # file.ext pattern
        score += 0.5
    if re.search(r"PR #\d+|commit|branch", lower):
        score += 0.5
    return score


def _extract_function_from_reasons(
    reasons: list[dict[str, str]] | None,
) -> str | None:
    """Extract function/purpose from reason texts.

    Prioritizes analysis and authority reasons as they tend to explain WHY.
    """
    if not reasons:
        return None

    # Priority order for function extraction
    priority = {"analysis": 3, "authority": 2, "constraint": 2, "pattern": 1}

    candidates: list[tuple[float, str]] = []
    for r in reasons:
        r_type = r.type if hasattr(r, "type") else r.get("type", "")
        r_text = r.text if hasattr(r, "text") else r.get("text", "")
        if not r_text:
            continue
        p = priority.get(r_type, 0)
        func_score = _score_as_function(r_text)
        candidates.append((p + func_score, r_text))

    if not candidates:
        return None

    # Pick the best candidate
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]

    # Truncate to reasonable length
    if len(best) > 200:
        best = best[:197] + "..."
    return best


def _extract_structure_from_context(context: str | None) -> str | None:
    """Extract structure/pattern from context text.

    Looks for sentences that describe what was done/built.
    """
    if not context:
        return None

    # Split into sentences
    sentences = re.split(r"[.!]\s+", context)
    if not sentences:
        return None

    candidates: list[tuple[float, str]] = []
    for s in sentences:
        s = s.strip()
        if len(s) < 10:
            continue
        score = _score_as_structure(s)
        candidates.append((score, s))

    if not candidates:
        return None

    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[0][1]

    if len(best) > 200:
        best = best[:197] + "..."
    return best


def auto_extract_bridge(request: RecordDecisionRequest) -> BridgeDefinition | None:
    """Auto-extract a bridge-definition from decision fields.

    Strategy:
    - Structure: decision text (what was done) + best structural sentence from context
    - Function: best function-oriented reason + function signals from context

    Returns None if extraction produces nothing useful.
    """
    structure_parts: list[str] = []
    function_parts: list[str] = []

    # Decision text is primarily structural (what was done)
    if request.decision:
        decision_struct = _score_as_structure(request.decision)
        decision_func = _score_as_function(request.decision)

        if decision_struct >= decision_func:
            structure_parts.append(request.decision)
        else:
            # Rare case where decision text is more functional
            function_parts.append(request.decision)

    # Context: extract best structural sentence
    context_structure = _extract_structure_from_context(request.context)
    if context_structure:
        structure_parts.append(context_structure)

    # Context: check for function signals too
    if request.context:
        context_func = _score_as_function(request.context)
        if context_func > 0:
            # Find the most function-oriented sentence
            sentences = re.split(r"[.!]\s+", request.context)
            for s in sentences:
                s = s.strip()
                if len(s) >= 10 and _score_as_function(s) > 0:
                    function_parts.append(s)
                    break

    # Reasons: extract function/purpose
    reason_function = _extract_function_from_reasons(request.reasons)
    if reason_function:
        function_parts.append(reason_function)

    # Build structure and function strings
    structure = structure_parts[0] if structure_parts else ""
    function = function_parts[0] if function_parts else ""

    # If we got at least one side, return a bridge
    if structure or function:
        # Use decision text as fallback for whichever side is empty
        if not structure and request.decision:
            structure = request.decision
        if not function and request.decision:
            function = request.decision

        return BridgeDefinition(
            structure=structure,
            function=function,
        )

    return None
