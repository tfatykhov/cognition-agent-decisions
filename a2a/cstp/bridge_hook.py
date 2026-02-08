"""F024: Shared bridge auto-extraction hook.

Single entry point for both dispatcher and MCP server to avoid logic drift.
"""

import logging

from .bridge_extractor import auto_extract_bridge
from .decision_service import RecordDecisionRequest

logger = logging.getLogger(__name__)


def maybe_auto_extract_bridge(request: RecordDecisionRequest) -> bool:
    """Auto-extract bridge if not explicitly provided.

    Modifies request.bridge in place if extraction succeeds.

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
