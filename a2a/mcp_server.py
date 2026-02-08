"""MCP Server for CSTP Decision Intelligence.

Exposes CSTP capabilities as MCP tools so any MCP-compliant agent
(Claude Desktop, OpenClaw, etc.) can discover and use decision
intelligence natively.

Transports:
    - stdio: ``python -m a2a.mcp_server`` (local / Docker exec)
    - Streamable HTTP: mounted at ``/mcp`` on the FastAPI server (remote)

The ``mcp_app`` Server instance is importable for mounting into other
ASGI applications (see ``a2a/server.py``).
"""

import asyncio
import json
import logging
import sys
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    TextContent,
    Tool,
)

from .mcp_schemas import (
    CheckActionInput,
    GetDecisionInput,
    GetStatsInput,
    LogDecisionInput,
    QueryDecisionsInput,
    ReviewOutcomeInput,
)

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cstp-mcp")

# Server instance — importable for mounting in ASGI apps (see a2a/server.py)
mcp_app = Server("cstp-decisions")


def _build_query_params(args: QueryDecisionsInput) -> dict[str, Any]:
    """Convert Pydantic input to CSTP query params dict."""
    params: dict[str, Any] = {
        "query": args.query,
        "limit": args.limit,
        "retrievalMode": args.retrieval_mode,
    }
    if args.filters:
        filters: dict[str, Any] = {}
        if args.filters.category:
            filters["category"] = args.filters.category
        if args.filters.stakes:
            filters["stakes"] = args.filters.stakes
        if args.filters.project:
            filters["project"] = args.filters.project
        if args.filters.has_outcome is not None:
            filters["hasOutcome"] = args.filters.has_outcome
        if filters:
            params["filters"] = filters
    return params


def _build_guardrails_params(args: CheckActionInput) -> dict[str, Any]:
    """Convert Pydantic input to CSTP guardrails params dict."""
    action: dict[str, Any] = {
        "description": args.description,
        "stakes": args.stakes,
    }
    if args.category:
        action["category"] = args.category
    if args.confidence is not None:
        action["confidence"] = args.confidence
    return {"action": action}


@mcp_app.list_tools()
async def list_tools() -> list[Tool]:
    """List available CSTP tools for MCP discovery."""
    return [
        Tool(
            name="query_decisions",
            description=(
                "Search similar past decisions using semantic search, keyword matching, "
                "or hybrid retrieval. Returns matching decisions with confidence scores, "
                "categories, and outcomes. Use before making new decisions to learn from "
                "history."
            ),
            inputSchema=QueryDecisionsInput.model_json_schema(),
        ),
        Tool(
            name="check_action",
            description=(
                "Validate an intended action against safety guardrails and policies. "
                "Returns whether the action is allowed, any violations (blocking), and "
                "warnings. Always check before high-stakes actions."
            ),
            inputSchema=CheckActionInput.model_json_schema(),
        ),
        Tool(
            name="log_decision",
            description=(
                "Record a decision to the immutable decision log. Include what you "
                "decided, your confidence level, category, and supporting reasons. "
                "Use after making a decision to build calibration history."
            ),
            inputSchema=LogDecisionInput.model_json_schema(),
        ),
        Tool(
            name="review_outcome",
            description=(
                "Record the outcome of a past decision. Provide the decision ID, "
                "whether it succeeded or failed, what actually happened, and lessons "
                "learned. Builds calibration data over time."
            ),
            inputSchema=ReviewOutcomeInput.model_json_schema(),
        ),
        Tool(
            name="get_stats",
            description=(
                "Get calibration statistics: Brier score, accuracy, confidence "
                "distribution, and decision counts. Optionally filter by category, "
                "project, or time window. Use to check decision-making quality."
            ),
            inputSchema=GetStatsInput.model_json_schema(),
        ),
        Tool(
            name="get_decision",
            description=(
                "Retrieve full details of a single decision by ID. Returns the "
                "complete record including context, reasons, project metadata, "
                "outcome, and review information. Use when you need the full "
                "decision content beyond what query_decisions returns."
            ),
            inputSchema=GetDecisionInput.model_json_schema(),
        ),
    ]


@mcp_app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to CSTP services."""
    logger.info("Tool called: %s", name)

    try:
        if name == "query_decisions":
            return await _handle_query_decisions(arguments)

        if name == "check_action":
            return await _handle_check_action(arguments)

        if name == "log_decision":
            return await _handle_log_decision(arguments)

        if name == "review_outcome":
            return await _handle_review_outcome(arguments)

        if name == "get_stats":
            return await _handle_get_stats(arguments)

        if name == "get_decision":
            return await _handle_get_decision_mcp(arguments)

        raise ValueError(f"Unknown tool: {name}")

    except ValueError as e:
        logger.warning("Validation error in tool %s: %s", name, e)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "validation_error", "message": str(e)}),
            )
        ]
    except Exception as e:
        # Catches pydantic.ValidationError and any other unexpected errors
        error_type = "validation_error" if "ValidationError" in type(e).__name__ else "internal_error"
        logger.error("Tool %s failed (%s): %s", name, type(e).__name__, e, exc_info=True)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": error_type, "message": str(e)}),
            )
        ]


async def _handle_query_decisions(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle query_decisions tool call."""
    from .cstp.models import QueryDecisionsRequest
    from .cstp.query_service import query_decisions

    # Validate input via Pydantic
    args = QueryDecisionsInput(**arguments)

    # Convert to CSTP request
    params = _build_query_params(args)
    request = QueryDecisionsRequest.from_params(params)

    # Execute query
    response = await query_decisions(request)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def _handle_check_action(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle check_action tool call."""
    from .cstp.guardrails_service import evaluate_guardrails, log_guardrail_check
    from .cstp.models import CheckGuardrailsRequest

    # Validate input via Pydantic
    args = CheckActionInput(**arguments)

    # Convert to CSTP request
    params = _build_guardrails_params(args)
    request = CheckGuardrailsRequest.from_params(params)

    # Evaluate guardrails
    response = evaluate_guardrails(request, agent_id="mcp-client")

    # Log the check
    log_guardrail_check(request, response)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def _handle_log_decision(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle log_decision tool call."""
    from .cstp.decision_service import RecordDecisionRequest, record_decision

    # Validate input via Pydantic
    args = LogDecisionInput(**arguments)

    # Build params dict for CSTP
    params: dict[str, Any] = {
        "decision": args.decision,
        "confidence": args.confidence,
        "category": args.category,
        "stakes": args.stakes,
    }
    if args.context:
        params["context"] = args.context
    if args.reasons:
        params["reasons"] = [{"type": r.type, "text": r.text} for r in args.reasons]
    if args.tags:
        params["tags"] = args.tags
    if args.project:
        params["project"] = args.project
    if args.feature:
        params["feature"] = args.feature
    if args.pr is not None:
        params["pr"] = args.pr

    # Create request and record
    request = RecordDecisionRequest.from_dict(params, agent_id="mcp-client")
    response = await record_decision(request)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def _handle_review_outcome(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle review_outcome tool call."""
    from .cstp.decision_service import ReviewDecisionRequest, review_decision

    # Validate input via Pydantic
    args = ReviewOutcomeInput(**arguments)

    # Build params dict for CSTP
    params: dict[str, Any] = {
        "id": args.id,
        "outcome": args.outcome,
    }
    if args.actual_result:
        params["actualResult"] = args.actual_result
    if args.lessons:
        params["lessons"] = args.lessons
    if args.notes:
        params["notes"] = args.notes

    # Create request and review
    request = ReviewDecisionRequest.from_dict(params, reviewer_id="mcp-client")
    response = await review_decision(request)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def _handle_get_stats(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_stats tool call."""
    from .cstp.calibration_service import GetCalibrationRequest, get_calibration

    # Validate input via Pydantic
    args = GetStatsInput(**arguments)

    # Build request directly
    request = GetCalibrationRequest(
        category=args.category,
        project=args.project,
        window=args.window,
    )

    # Get calibration stats
    response = await get_calibration(request)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def _handle_get_decision_mcp(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle get_decision tool call."""
    from .cstp.decision_service import GetDecisionRequest, get_decision

    # Validate input via Pydantic
    args = GetDecisionInput(**arguments)

    # Create request and fetch
    request = GetDecisionRequest.from_dict({"id": args.id})
    response = await get_decision(request)

    # Format response
    result = response.to_dict()
    return [
        TextContent(
            type="text",
            text=json.dumps(result, indent=2, default=str),
        )
    ]


async def run_stdio() -> None:
    """Run the MCP server with stdio transport."""
    logger.info("Starting CSTP MCP server (stdio transport)")

    async with stdio_server() as (read_stream, write_stream):
        await mcp_app.run(
            read_stream,
            write_stream,
            mcp_app.create_initialization_options(),
        )


def main() -> None:
    """Entry point for the MCP server."""
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
