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
from .attribution_service import (
    AttributeOutcomesRequest,
    attribute_outcomes,
)
from .bm25_index import get_cached_index, merge_results
from .calibration_service import (
    GetCalibrationRequest,
    get_calibration,
)
from .decision_service import (
    GetDecisionRequest,
    RecordDecisionRequest,
    ReviewDecisionRequest,
    get_decision,
    record_decision,
    review_decision,
)
from .drift_service import (
    CheckDriftRequest,
    check_drift,
)
from .reason_stats_service import (
    GetReasonStatsRequest,
    get_reason_stats,
)
from .guardrails_service import evaluate_guardrails, log_guardrail_check, list_guardrails
from .models import (
    CheckGuardrailsRequest,
    CheckGuardrailsResponse,
    DecisionSummary,
    GuardrailViolation,
    PreActionRequest,
    QueryDecisionsRequest,
    QueryDecisionsResponse,
    SessionContextRequest,
)
from .preaction_service import pre_action
from .query_service import query_decisions, load_all_decisions
from .reindex_service import reindex_decisions
from .session_context_service import get_session_context


# Type alias for method handlers
MethodHandler = Callable[[dict[str, Any], str], Awaitable[dict[str, Any]]]

# Custom error codes
QUERY_FAILED = -32003
RATE_LIMITED = -32002
GUARDRAIL_EVAL_FAILED = -32004
RECORD_FAILED = -32005
ATTRIBUTION_FAILED = -32008
REVIEW_FAILED = -32006
DECISION_NOT_FOUND = -32007


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
    import time
    start_time = time.time()

    # Parse request
    request = QueryDecisionsRequest.from_params(params)

    # F017: Handle different retrieval modes
    scores: dict[str, dict[str, float]] = {}

    # Handle empty query - list all decisions (for dashboard)
    if not request.query.strip():
        all_decisions = await load_all_decisions(
            category=request.filters.category,
            project=request.filters.project,
        )
        # Sort by date descending, limit results
        all_decisions.sort(
            key=lambda d: d.get("created_at", ""),
            reverse=True,
        )
        all_decisions = all_decisions[:request.limit]

        decisions = []
        for d in all_decisions:
            doc_id = d.get("id", "")
            decisions.append(
                DecisionSummary(
                    id=doc_id[:8] if len(doc_id) > 8 else doc_id,
                    title=d.get("summary", d.get("decision", "Untitled"))[:50],
                    category=d.get("category", ""),
                    confidence=d.get("confidence"),
                    stakes=d.get("stakes"),
                    status=d.get("status", ""),
                    outcome=d.get("outcome"),
                    date=d.get("created_at", "")[:10],
                    distance=0.0,
                    reasons=None,
                    tags=d.get("tags"),
                    pattern=d.get("pattern"),
                )
            )

        query_time_ms = int((time.time() - start_time) * 1000)

        result = QueryDecisionsResponse(
            decisions=decisions,
            total=len(decisions),
            query=request.query,
            query_time_ms=query_time_ms,
            agent="cognition-engines",
            retrieval_mode="list",
            scores={},
        )

        # F023 Phase 2: Track query for auto-deliberation
        from .deliberation_tracker import track_query

        track_query(
            key=f"rpc:{agent_id}",
            query=request.query,
            result_count=result.total,
            top_ids=[d.id for d in result.decisions[:5]],
            retrieval_mode="list",
            top_results=[
                {"id": d.id, "summary": d.title[:100], "distance": d.distance}
                for d in result.decisions[:5]
            ],
        )

        return result.to_dict()

    if request.retrieval_mode == "keyword":
        # Keyword-only search via BM25
        all_decisions = await load_all_decisions(
            category=request.filters.category,
            project=request.filters.project,
        )
        # Use cached index for performance
        cache_key = f"kw:{request.filters.category}:{request.filters.project}"
        bm25_index = get_cached_index(all_decisions, cache_key)
        keyword_results = bm25_index.search(request.query, request.limit)

        # Build decision map for quick lookup
        decision_map = {d["id"]: d for d in all_decisions}

        decisions = []
        for doc_id, score in keyword_results:
            d = decision_map.get(doc_id, {})
            decisions.append(
                DecisionSummary(
                    id=doc_id[:8] if len(doc_id) > 8 else doc_id,
                    title=d.get("summary", d.get("decision", "Untitled"))[:50],
                    category=d.get("category", ""),
                    confidence=d.get("confidence"),
                    stakes=d.get("stakes"),
                    status=d.get("status", ""),
                    outcome=d.get("outcome"),
                    date=d.get("created_at", "")[:10],
                    distance=round(1.0 - score / 10.0, 4),  # Approximate distance
                    reasons=None,
                    tags=d.get("tags"),
                    pattern=d.get("pattern"),
                )
            )
            scores[doc_id[:8] if len(doc_id) > 8 else doc_id] = {
                "semantic": 0.0,
                "keyword": round(score, 4),
                "combined": round(score, 4),
            }

        query_time_ms = int((time.time() - start_time) * 1000)

    elif request.retrieval_mode == "hybrid":
        # Hybrid: combine semantic + keyword
        # First, get semantic results
        response = await query_decisions(
            query=request.effective_query,
            n_results=request.limit * 2,  # Get more for merging
            category=request.filters.category,
            min_confidence=request.filters.min_confidence if request.filters.min_confidence > 0 else None,
            max_confidence=request.filters.max_confidence if request.filters.max_confidence < 1 else None,
            stakes=request.filters.stakes,
            status_filter=request.filters.status,
            project=request.filters.project,
            feature=request.filters.feature,
            pr=request.filters.pr,
            has_outcome=request.filters.has_outcome,
            tags=request.filters.tags,
        )

        if response.error:
            raise RuntimeError(response.error)

        # Convert semantic results to (id, score) format
        # Distance is inverse of similarity, so convert
        semantic_results = [
            (r.id, 1.0 - r.distance) for r in response.results
        ]

        # Get keyword results
        all_decisions = await load_all_decisions(
            category=request.filters.category,
            project=request.filters.project,
        )
        # Use cached index for performance
        cache_key = f"hybrid:{request.filters.category}:{request.filters.project}"
        bm25_index = get_cached_index(all_decisions, cache_key)
        keyword_results = bm25_index.search(request.query, request.limit * 2)

        # Merge results
        merged = merge_results(
            semantic_results,
            keyword_results,
            semantic_weight=request.hybrid_weight,
            top_k=request.limit,
        )

        # Build response from merged results
        decision_map = {d["id"][:8]: d for d in all_decisions}
        decision_map.update({d["id"]: d for d in all_decisions})

        # Also map from semantic results
        semantic_map = {r.id: r for r in response.results}

        decisions = []
        for doc_id, score_dict in merged:
            # Try semantic result first
            if doc_id in semantic_map:
                r = semantic_map[doc_id]
                decisions.append(
                    DecisionSummary(
                        id=r.id,
                        title=r.title,
                        category=r.category,
                        confidence=r.confidence,
                        stakes=r.stakes,
                        status=r.status,
                        outcome=r.outcome,
                        date=r.date,
                        distance=round(1.0 - score_dict["combined"], 4),
                        reasons=r.reason_types if request.include_reasons else None,
                        tags=r.tags,
                        pattern=r.pattern,
                    )
                )
            elif doc_id in decision_map:
                d = decision_map[doc_id]
                decisions.append(
                    DecisionSummary(
                        id=doc_id[:8] if len(doc_id) > 8 else doc_id,
                        title=d.get("summary", d.get("decision", "Untitled"))[:50],
                        category=d.get("category", ""),
                        confidence=d.get("confidence"),
                        stakes=d.get("stakes"),
                        status=d.get("status", ""),
                        outcome=d.get("outcome"),
                        date=d.get("created_at", "")[:10],
                        distance=round(1.0 - score_dict["combined"], 4),
                        reasons=None,
                        tags=d.get("tags"),
                        pattern=d.get("pattern"),
                    )
                )
            scores[doc_id] = score_dict

        query_time_ms = int((time.time() - start_time) * 1000)

    else:
        # Default: semantic-only search
        response = await query_decisions(
            query=request.effective_query,
            n_results=request.limit,
            category=request.filters.category,
            min_confidence=request.filters.min_confidence if request.filters.min_confidence > 0 else None,
            max_confidence=request.filters.max_confidence if request.filters.max_confidence < 1 else None,
            stakes=request.filters.stakes,
            status_filter=request.filters.status,
            project=request.filters.project,
            feature=request.filters.feature,
            pr=request.filters.pr,
            has_outcome=request.filters.has_outcome,
            tags=request.filters.tags,
        )

        if response.error:
            raise RuntimeError(response.error)

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
                tags=r.tags,
                pattern=r.pattern,
            )
            for r in response.results
        ]
        query_time_ms = response.query_time_ms

    result = QueryDecisionsResponse(
        decisions=decisions,
        total=len(decisions),
        query=request.query,
        query_time_ms=query_time_ms,
        agent="cognition-engines",
        retrieval_mode=request.retrieval_mode,
        scores=scores if scores else {},
    )

    # F023 Phase 2: Track query for auto-deliberation
    from .deliberation_tracker import track_query

    track_query(
        key=f"rpc:{agent_id}",
        query=request.query,
        result_count=result.total,
        top_ids=[d.id for d in result.decisions[:5]],
        retrieval_mode=request.retrieval_mode,
        top_results=[
            {"id": d.id, "summary": d.title[:100], "distance": d.distance}
            for d in result.decisions[:5]
        ],
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

    # F023 Phase 2: Track guardrail check for auto-deliberation
    from .deliberation_tracker import track_guardrail

    track_guardrail(
        key=f"rpc:{agent_id}",
        description=request.action.description,
        allowed=eval_result.allowed,
        violation_count=len(eval_result.violations),
    )

    return result.to_dict()


async def _handle_list_guardrails(params: dict[str, Any], _agent_id: str) -> dict[str, Any]:
    """Handle cstp.listGuardrails method.

    Args:
        params: JSON-RPC params.
        _agent_id: Authenticated agent ID (unused).

    Returns:
        List of active guardrails.
    """
    scope = params.get("scope")
    guardrails = list_guardrails(scope=scope)

    return {
        "guardrails": guardrails,
        "count": len(guardrails),
        "agent": "cognition-engines"
    }


async def _handle_pre_action(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.preAction method (F046).

    Combines query + guardrails + calibration + optional record in one call.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Pre-action results as dict.
    """
    request = PreActionRequest.from_params(params)
    response = await pre_action(request, agent_id)
    return response.to_dict()


async def _handle_get_session_context(
    params: dict[str, Any], agent_id: str,
) -> dict[str, Any]:
    """Handle cstp.getSessionContext method (F047).

    Returns full cognitive context for session start.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Session context as dict.
    """
    request = SessionContextRequest.from_params(params)
    response = await get_session_context(request, agent_id)
    return response.to_dict()


def register_methods(dispatcher: CstpDispatcher) -> None:
    """Register all CSTP method handlers.

    Args:
        dispatcher: Dispatcher to register methods on.
    """
    dispatcher.register("cstp.queryDecisions", _handle_query_decisions)
    dispatcher.register("cstp.checkGuardrails", _handle_check_guardrails)
    dispatcher.register("cstp.listGuardrails", _handle_list_guardrails)
    dispatcher.register("cstp.recordDecision", _handle_record_decision)
    dispatcher.register("cstp.updateDecision", _handle_update_decision)
    dispatcher.register("cstp.recordThought", _handle_record_thought)
    dispatcher.register("cstp.getDecision", _handle_get_decision)

    dispatcher.register("cstp.reviewDecision", _handle_review_decision)
    dispatcher.register("cstp.getCalibration", _handle_get_calibration)
    dispatcher.register("cstp.attributeOutcomes", _handle_attribute_outcomes)
    dispatcher.register("cstp.checkDrift", _handle_check_drift)
    dispatcher.register("cstp.reindex", _handle_reindex)
    dispatcher.register("cstp.getReasonStats", _handle_get_reason_stats)

    # F046/F047: Agentic loop integration
    dispatcher.register("cstp.preAction", _handle_pre_action)
    dispatcher.register("cstp.getSessionContext", _handle_get_session_context)


async def _handle_update_decision(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.updateDecision method (F027 backfill).

    Updates specific fields on an existing decision.

    Args:
        params: {"id": "abc123", "updates": {"tags": [...], "pattern": "..."}}
        agent_id: Authenticated agent ID.

    Returns:
        Update result with success status.
    """
    from .decision_service import update_decision

    decision_id = params.get("id") or params.get("decision_id", "")
    if not decision_id:
        raise ValueError("Missing required parameter: id")

    updates = params.get("updates", {})
    if not updates:
        raise ValueError("Missing required parameter: updates")

    return await update_decision(decision_id, updates)


async def _handle_record_thought(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.recordThought method (F028).

    Records a reasoning/chain-of-thought step in the deliberation tracker.
    Two modes:
    - Pre-decision: no decision_id - thought accumulates in tracker,
      auto-attached when recordDecision is called.
    - Post-decision: decision_id provided - thought is appended to
      the existing decision's deliberation trace (append-only).

    Args:
        params: {"text": "reasoning...", "decision_id": "optional"}
        agent_id: Authenticated agent ID.

    Returns:
        Acknowledgment with tracked input ID.
    """
    from .deliberation_tracker import track_reasoning

    text = params.get("text", "")
    if not text:
        raise ValueError("Missing required parameter: text")

    decision_id = params.get("decision_id") or params.get("id")

    if decision_id:
        # Post-decision: append-only via shared service function
        from .decision_service import append_thought

        result = await append_thought(decision_id, text)
        if not result.get("success"):
            raise ValueError(result.get("error", "Unknown error"))
        return {
            "success": True,
            "mode": "post-decision",
            "decision_id": decision_id,
            "step_number": result["step_number"],
        }

    # Pre-decision: accumulate in tracker
    track_reasoning(f"rpc:{agent_id}", text)
    return {
        "success": True,
        "mode": "pre-decision",
        "agent_id": agent_id,
    }


async def _handle_get_decision(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.getDecision method.

    Retrieves full decision details by ID, including context, reasons,
    and all metadata stored in the YAML file.

    Args:
        params: JSON-RPC params with 'id' field.
        agent_id: Authenticated agent ID.

    Returns:
        Full decision data as dict.

    Raises:
        ValueError: If ID is missing or invalid.
    """
    request = GetDecisionRequest.from_dict(params)
    response = await get_decision(request)

    if not response.found:
        raise ValueError(response.error or f"Decision not found: {request.decision_id}")

    # F023 Phase 2: Track decision lookup for auto-deliberation
    from .deliberation_tracker import track_lookup

    dec = response.decision or {}
    track_lookup(
        key=f"rpc:{agent_id}",
        decision_id=request.decision_id,
        title=dec.get("summary", dec.get("decision", ""))[:50],
    )

    return response.to_dict()


async def _handle_reindex(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.reindex method.

    Reindexes all decisions with fresh embeddings.
    This will delete and recreate the ChromaDB collection.

    Args:
        params: JSON-RPC params (unused).
        agent_id: Authenticated agent ID.

    Returns:
        Reindex result as dict.
    """
    result = await reindex_decisions()
    return result.to_dict()


async def _handle_record_decision(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.recordDecision method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Record result as dict.

    Raises:
        ValueError: If validation fails.
        RuntimeError: If recording fails.
    """
    # Parse and validate request
    request = RecordDecisionRequest.from_dict(params, agent_id=agent_id)

    # F025: Extract related decisions BEFORE consuming tracker
    from .deliberation_tracker import extract_related_from_tracker

    if not request.related_to:
        related_raw = extract_related_from_tracker(f"rpc:{agent_id}")
        if related_raw:
            from .decision_service import RelatedDecision

            request.related_to = [
                RelatedDecision.from_dict(r) for r in related_raw
            ]

    # F023 Phase 2: Auto-attach deliberation from tracked inputs
    from .deliberation_tracker import auto_attach_deliberation

    request.deliberation, auto_captured = auto_attach_deliberation(
        key=f"rpc:{agent_id}",
        deliberation=request.deliberation,
    )

    # F027 P2: Smart bridge extraction (replaces F024 Phase 3)
    from .bridge_hook import maybe_smart_extract_bridge

    bridge_auto, bridge_method = await maybe_smart_extract_bridge(request)

    errors = request.validate()
    if errors:
        raise ValueError(f"Validation failed: {'; '.join(errors)}")

    # Record the decision
    response = await record_decision(request)

    if not response.success:
        raise RuntimeError(response.error or "Failed to record decision")

    # Add auto-deliberation info to response only if auto-capture happened
    result = response.to_dict()
    if auto_captured and request.deliberation:
        result["deliberation_auto"] = True
        result["deliberation_inputs_count"] = len(request.deliberation.inputs)

    # F026: Run guardrails against record context (supports deliberation checks)
    from .guardrails_service import evaluate_record_guardrails
    record_warnings = await evaluate_record_guardrails(request)
    if record_warnings:
        result["guardrail_warnings"] = record_warnings

    if bridge_auto and request.bridge:
        result["bridge_auto"] = True
        result["bridge_method"] = bridge_method

    if request.related_to:
        result["related_count"] = len(request.related_to)

    return result


async def _handle_review_decision(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.reviewDecision method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID (reviewer).

    Returns:
        Review result as dict.

    Raises:
        ValueError: If validation fails.
        RuntimeError: If review fails.
    """
    # Parse and validate request
    request = ReviewDecisionRequest.from_dict(params, reviewer_id=agent_id)

    errors = request.validate()
    if errors:
        raise ValueError(f"Validation failed: {'; '.join(errors)}")

    # Review the decision
    response = await review_decision(request)

    if not response.success:
        raise RuntimeError(response.error or "Failed to review decision")

    return response.to_dict()


async def _handle_get_calibration(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.getCalibration method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Calibration statistics as dict.
    """
    request = GetCalibrationRequest.from_dict(params)
    response = await get_calibration(request)
    return response.to_dict()


async def _handle_attribute_outcomes(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.attributeOutcomes method.

    Args:
        params: JSON-RPC params.
        agent_id: Authenticated agent ID.

    Returns:
        Attribution results as dict.

    Raises:
        ValueError: If validation fails.
    """
    request = AttributeOutcomesRequest.from_dict(params)
    response = await attribute_outcomes(request)
    return response.to_dict()


async def _handle_check_drift(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.checkDrift method.

    Compares recent (30d) vs historical (90d+) calibration to detect drift.

    Args:
        params: JSON-RPC params with thresholds and filters.
        agent_id: Authenticated agent ID.

    Returns:
        Drift check results as dict.
    """
    request = CheckDriftRequest.from_dict(params)
    response = await check_drift(request)
    return response.to_dict()


async def _handle_get_reason_stats(params: dict[str, Any], agent_id: str) -> dict[str, Any]:
    """Handle cstp.getReasonStats method.

    Analyzes which reason types correlate with better outcomes.
    Implements Minsky Ch 18 parallel bundle analysis.

    Args:
        params: JSON-RPC params with optional filters.
        agent_id: Authenticated agent ID.

    Returns:
        Reason-type calibration statistics as dict.
    """
    request = GetReasonStatsRequest.from_dict(params)
    response = await get_reason_stats(request)

    # F023 Phase 2: Track stats lookup for auto-deliberation
    from .deliberation_tracker import track_stats

    result = response.to_dict()
    track_stats(
        key=f"rpc:{agent_id}",
        total_decisions=result.get("totalDecisions", 0),
        reason_type_count=len(result.get("byReasonType", [])),
        diversity=result.get("diversity", {}).get("avgTypesPerDecision"),
    )

    return result
