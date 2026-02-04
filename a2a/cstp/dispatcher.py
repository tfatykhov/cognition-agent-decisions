"""JSON-RPC method dispatcher for CSTP.

Routes incoming JSON-RPC requests to appropriate method handlers.
"""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from ..models.jsonrpc import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)
from .guardrails_service import evaluate_guardrails, log_guardrail_check
from .models import (
    CheckGuardrailsRequest,
    CheckGuardrailsResponse,
    DecisionSummary,
    GuardrailViolation,
    QueryDecisionsRequest,
    QueryDecisionsResponse,
)
from .query_service import query_decisions


# Type alias for method handlers
MethodHandler = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]

# Custom error codes
QUERY_FAILED = -32003
RATE_LIMITED = -32002
GUARDRAIL_EVAL_FAILED = -32004


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
        except ValueError as e:
            return JsonRpcResponse.failure(
                request.id,
                JsonRpcError(
                    code=INVALID_PARAMS,
                    message=str(e),
                ),
            )
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
    """Handle cstp.queryDecisions method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Query results as dict.
    """
    # Parse request
    request = QueryDecisionsRequest.from_params(params)

    # Execute query
    response = await query_decisions(
        query=request.query,
        n_results=request.limit,
        category=request.filters.category,
        min_confidence=request.filters.min_confidence if request.filters.min_confidence > 0 else None,
        max_confidence=request.filters.max_confidence if request.filters.max_confidence < 1 else None,
        stakes=request.filters.stakes,
        status_filter=request.filters.status,
    )

    # Check for errors
    if response.error:
        raise RuntimeError(response.error)

    # Map results to response format
    decisions = [
        DecisionSummary(
            id=r.id,
            title=r.title,
            category=r.category,
            confidence=r.confidence,
            stakes=r.stakes,
            status=r.status,
            outcome=r.outcome,
            date=r.date,
            distance=r.distance,
            reasons=r.reason_types if request.include_reasons else None,
        )
        for r in response.results
    ]

    result = QueryDecisionsResponse(
        decisions=decisions,
        total=len(decisions),
        query=request.query,
        query_time_ms=response.query_time_ms,
        agent="cognition-engines",
    )

    return result.to_dict()


async def _handle_check_guardrails(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.checkGuardrails method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Guardrail check results as dict.
    """
    # Parse request
    request = CheckGuardrailsRequest.from_params(params)

    # Build evaluation context
    context: dict[str, Any] = {
        "category": request.action.category,
        "stakes": request.action.stakes,
        "confidence": request.action.confidence,
    }
    # Merge additional context
    if request.action.context:
        context.update(request.action.context)

    # Evaluate guardrails
    eval_result = await evaluate_guardrails(context)

    # Audit log
    log_guardrail_check(
        requesting_agent=agent_id,
        action_description=request.action.description,
        allowed=eval_result.allowed,
        violations=eval_result.violations,
        evaluated=eval_result.evaluated,
    )

    # Map to response format
    violations = [
        GuardrailViolation(
            guardrail_id=v.guardrail_id,
            name=v.name,
            message=v.message,
            severity=v.severity,
            suggestion=v.suggestion,
        )
        for v in eval_result.violations
    ]

    warnings = [
        GuardrailViolation(
            guardrail_id=w.guardrail_id,
            name=w.name,
            message=w.message,
            severity=w.severity,
            suggestion=w.suggestion,
        )
        for w in eval_result.warnings
    ]

    result = CheckGuardrailsResponse(
        allowed=eval_result.allowed,
        violations=violations,
        warnings=warnings,
        evaluated=eval_result.evaluated,
        evaluated_at=datetime.now(UTC),
        agent="cognition-engines",
    )

    return result.to_dict()


def register_methods(dispatcher: CstpDispatcher) -> None:
    """Register all CSTP method handlers.

    Args:
        dispatcher: Dispatcher to register methods on.
    """
    dispatcher.register("cstp.queryDecisions", _handle_query_decisions)
    dispatcher.register("cstp.checkGuardrails", _handle_check_guardrails)
