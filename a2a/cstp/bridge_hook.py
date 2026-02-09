"""F024/F027: Shared bridge auto-extraction hook.

Single entry point for both dispatcher and MCP server to avoid logic drift.
F027 P2 upgrade: uses smart abstractors (rule-based or LLM) instead of
simple text copying.
"""

import logging

from .bridge_abstractors import smart_extract_bridge
from .bridge_extractor import auto_extract_bridge
from .decision_service import RecordDecisionRequest

logger = logging.getLogger(__name__)


def maybe_auto_extract_bridge(request: RecordDecisionRequest) -> bool:
    """Auto-extract bridge if not explicitly provided (sync wrapper).

    Modifies request.bridge in place if extraction succeeds.
    Uses the legacy extractor (F024) as fallback.

    Returns:
        True if bridge was auto-extracted, False otherwise.
    """
    if request.bridge and request.bridge.has_content():
        return False

    try:
        extracted = auto_extract_bridge(request)
        if extracted and extracted.has_content():
            request.bridge = extracted
            return True
    except Exception:
        logger.debug("Bridge auto-extraction failed", exc_info=True)

    return False


async def maybe_smart_extract_bridge(
    request: RecordDecisionRequest,
    mode: str | None = None,
) -> tuple[bool, str]:
    """F027 P2: Smart bridge extraction with abstraction.

    Tries the new smart extractors first. Falls back to legacy if needed.
    Modifies request.bridge in place.

    Args:
        request: Decision request to extract bridge for.
        mode: Bridge mode override (rule | llm | both).

    Returns:
        Tuple of (was_extracted, method_used).
    """
    if request.bridge and request.bridge.has_content():
        return False, "explicit"

    try:
        bridge, method = await smart_extract_bridge(request, mode=mode)
        if bridge and bridge.has_content():
            request.bridge = bridge
            return True, method
    except Exception:
        logger.debug("Smart bridge extraction failed", exc_info=True)

    # Fall back to legacy extractor
    try:
        extracted = auto_extract_bridge(request)
        if extracted and extracted.has_content():
            request.bridge = extracted
            return True, "legacy"
    except Exception:
        logger.debug("Legacy bridge extraction failed", exc_info=True)

    return False, "none"
