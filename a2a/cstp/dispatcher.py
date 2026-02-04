"""JSON-RPC method dispatcher for CSTP.

Routes incoming JSON-RPC requests to appropriate method handlers.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from ..models.jsonrpc import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    METHOD_NOT_FOUND,
    INTERNAL_ERROR,
)


# Type alias for method handlers
MethodHandler = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]


class CstpDispatcher:
    """Dispatches JSON-RPC requests to method handlers.

    Attributes:
        methods: Registry of method name -> handler.
    """

    def __init__(self) -> None:
        """Initialize empty dispatcher."""
        self._methods: dict[str, MethodHandler] = {}

    def register(self, method: str, handler: MethodHandler) -> None:
        """Register a method handler.

        Args:
            method: Method name (e.g., "cstp.queryDecisions").
            handler: Async function to handle the method.
        """
        self._methods[method] = handler

    async def dispatch(
        self,
        request: JsonRpcRequest,
        agent_id: str,
    ) -> JsonRpcResponse:
        """Dispatch a JSON-RPC request to the appropriate handler.

        Args:
            request: Validated JSON-RPC request.
            agent_id: Authenticated agent ID.

        Returns:
            JSON-RPC response with result or error.
        """
        # Validate request format
        validation_error = request.validate()
        if validation_error:
            return JsonRpcResponse.failure(request.id, validation_error)

        # Find handler
        handler = self._methods.get(request.method)
        if not handler:
            return JsonRpcResponse.failure(
                request.id,
                JsonRpcError(
                    code=METHOD_NOT_FOUND,
                    message=f"Method not found: {request.method}",
                    data={"method": request.method, "available": list(self._methods.keys())},
                ),
            )

        # Execute handler
        try:
            result = await handler(request.params, agent_id)
            return JsonRpcResponse.success(request.id, result)
        except Exception as e:
            return JsonRpcResponse.failure(
                request.id,
                JsonRpcError(
                    code=INTERNAL_ERROR,
                    message=str(e),
                    data={"type": type(e).__name__},
                ),
            )


# Global dispatcher instance
_dispatcher: CstpDispatcher | None = None


def get_dispatcher() -> CstpDispatcher:
    """Get the global dispatcher instance.

    Returns:
        The CSTP dispatcher.
    """
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = CstpDispatcher()
    return _dispatcher


async def _handle_query_decisions(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Stub handler for cstp.queryDecisions.

    TODO: Implement in F002.
    """
    return {
        "decisions": [],
        "total": 0,
        "query": params.get("query", ""),
        "queryTimeMs": 0,
        "agent": "cognition-engines",
        "note": "Not yet implemented - F002",
    }


async def _handle_check_guardrails(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Stub handler for cstp.checkGuardrails.

    TODO: Implement in F003.
    """
    return {
        "allowed": True,
        "violations": [],
        "warnings": [],
        "evaluated": 0,
        "agent": "cognition-engines",
        "note": "Not yet implemented - F003",
    }


def register_methods(dispatcher: CstpDispatcher) -> None:
    """Register all CSTP method handlers.

    Args:
        dispatcher: Dispatcher to register methods on.
    """
    dispatcher.register("cstp.queryDecisions", _handle_query_decisions)
    dispatcher.register("cstp.checkGuardrails", _handle_check_guardrails)
