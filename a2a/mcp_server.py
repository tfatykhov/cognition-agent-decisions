"""MCP Server for CSTP Decision Intelligence.

Exposes CSTP capabilities as MCP tools so any MCP-compliant agent
(Claude Desktop, OpenClaw, etc.) can discover and use decision
intelligence natively.

F022 Phase 1: query_decisions + check_action tools via stdio transport.

Usage:
    python -m a2a.mcp_server
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

from .mcp_schemas import CheckActionInput, QueryDecisionsInput

# Configure logging to stderr (stdout is reserved for MCP protocol)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("cstp-mcp")

# Server instance
app = Server("cstp-decisions")


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


@app.list_tools()
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
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Dispatch tool calls to CSTP services."""
    logger.info("Tool called: %s", name)

    try:
        if name == "query_decisions":
            return await _handle_query_decisions(arguments)

        if name == "check_action":
            return await _handle_check_action(arguments)

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
        logger.error("Tool %s failed: %s", name, e, exc_info=True)
        return [
            TextContent(
                type="text",
                text=json.dumps({"error": "internal_error", "message": str(e)}),
            )
        ]


async def _handle_query_decisions(arguments: dict[str, Any]) -> list[TextContent]:
    """Handle query_decisions tool call."""
    from .models import QueryDecisionsRequest
    from .query_service import query_decisions

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
    from .guardrails_service import evaluate_guardrails, log_guardrail_check
    from .models import CheckGuardrailsRequest

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


async def run_stdio() -> None:
    """Run the MCP server with stdio transport."""
    logger.info("Starting CSTP MCP server (stdio transport)")

    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


def main() -> None:
    """Entry point for the MCP server."""
    asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
