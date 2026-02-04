"""CSTP method handlers package."""

from .dispatcher import CstpDispatcher, get_dispatcher, register_methods
from .guardrails_service import (
    EvaluationResult,
    GuardrailResult,
    clear_guardrails_cache,
    evaluate_guardrails,
    log_guardrail_check,
)
from .models import (
    ActionContext,
    AgentInfo,
    CheckGuardrailsRequest,
    CheckGuardrailsResponse,
    DecisionSummary,
    GuardrailViolation,
    QueryDecisionsRequest,
    QueryDecisionsResponse,
    QueryFilters,
)
from .query_service import QueryResponse, QueryResult, query_decisions

__all__ = [
    # Dispatcher
    "CstpDispatcher",
    "get_dispatcher",
    "register_methods",
    # Query models
    "QueryFilters",
    "QueryDecisionsRequest",
    "QueryDecisionsResponse",
    "DecisionSummary",
    # Query service
    "query_decisions",
    "QueryResult",
    "QueryResponse",
    # Guardrails models
    "ActionContext",
    "AgentInfo",
    "CheckGuardrailsRequest",
    "CheckGuardrailsResponse",
    "GuardrailViolation",
    # Guardrails service
    "evaluate_guardrails",
    "log_guardrail_check",
    "clear_guardrails_cache",
    "EvaluationResult",
    "GuardrailResult",
]
