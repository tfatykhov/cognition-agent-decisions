#!/usr/bin/env python3
"""MCP Demo Agent for Cognition Engines.

Connects to the CSTP server via MCP and demonstrates the full
decision intelligence workflow:
  1. pre_action (query + guardrails + auto-record)
  2. record_thought (capture reasoning)
  3. update_decision (finalize)
  4. get_session_context (accumulated intelligence)
  5. ready (check what needs attention)

This agent is a reference implementation following the FORGE protocol:
  Fetch → Orient → Resolve → Go → Extract

See: https://github.com/tfatykhov/cognition-engines-marketplace/tree/main/forge
"""

import asyncio
import json
import logging
import os
import sys
import time
from contextlib import asynccontextmanager

import httpx

# MCP client imports
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("demo-agent")

CSTP_URL = os.environ.get("CSTP_URL", "http://cstp-server:8100")
MCP_URL = f"{CSTP_URL}/mcp"
AGENT_ID = "demo-agent"
LOOP_INTERVAL = int(os.environ.get("DEMO_INTERVAL", "30"))


async def call_tool(session: ClientSession, name: str, args: dict) -> dict:
    """Call an MCP tool and return the parsed result."""
    result = await session.call_tool(name, args)
    # MCP returns TextContent list; parse the JSON from first item
    if result.content and len(result.content) > 0:
        text = result.content[0].text
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}
    return {}


# =============================================================================
# Scenarios
# =============================================================================

async def scenario_architecture_decision(session: ClientSession) -> None:
    """Scenario 1: Full architecture decision workflow via MCP.

    Demonstrates: pre_action → record_thought → update_decision
    """
    logger.info("=" * 60)
    logger.info("SCENARIO 1: Architecture Decision")
    logger.info("  Question: Should we use connection pooling or per-request connections?")
    logger.info("=" * 60)

    # Step 1: Pre-action (query similar + guardrails + auto-record)
    logger.info("\n📋 Step 1: pre_action (query + guardrails + record)")
    result = await call_tool(session, "pre_action", {
        "description": "Use connection pooling for database access instead of per-request connections",
        "auto_record": True,
        "stakes": "medium",
        "category": "architecture",
        "agent_id": AGENT_ID,
    })

    decision_id = result.get("decisionId")
    similar = result.get("similar_decisions", [])
    logger.info(f"  Decision ID: {decision_id}")
    logger.info(f"  Similar decisions found: {len(similar)}")
    for s in similar[:2]:
        logger.info(f"    - {s.get('title', s.get('decision', '?'))[:60]}")

    guardrails = result.get("guardrails", {})
    logger.info(f"  Guardrails: {'✅ passed' if guardrails.get('allowed') else '🚫 blocked'}")

    if not decision_id:
        logger.warning("  No decision ID returned (guardrail block?). Skipping.")
        return

    await asyncio.sleep(2)

    # Step 2: Record micro-thoughts during deliberation
    # FORGE protocol: minimum 10 atomic signals per decision
    logger.info("\n💭 Step 2: record_thought (micro-thought stream)")

    thoughts = [
        "per-request connections waste ~3ms on TCP handshake alone",
        "at 500 req/s that's 1.5 seconds of pure handshake overhead",
        "connection pooling amortizes handshake across requests",
        "pool size of 10-20 covers our P99 concurrent query count",
        "risk: pool exhaustion under load spikes",
        "mitigation: max_overflow parameter handles burst traffic",
        "SQLAlchemy pool has built-in overflow and timeout support",
        "wait — do we need cross-process pooling? pgbouncer handles that",
        "no — single process per container, in-process pool is fine",
        "pool_timeout=30s prevents indefinite waits on exhaustion",
        "connection health checks prevent stale connection errors",
        "decision: in-process pool with pool_size=15, max_overflow=5",
    ]

    for i, thought in enumerate(thoughts, 1):
        await call_tool(session, "record_thought", {
            "text": thought,
            "decision_id": decision_id,
            "agent_id": AGENT_ID,
        })
        logger.info(f"  💭 {i}/{len(thoughts)}: {thought[:60]}")
        await asyncio.sleep(0.5)

    logger.info(f"  Recorded {len(thoughts)} micro-thoughts")

    await asyncio.sleep(2)

    # Step 3: Update decision with final outcome
    logger.info("\n✅ Step 3: update_decision (finalize)")
    await call_tool(session, "update_decision", {
        "id": decision_id,
        "decision": "Implemented connection pooling with pool_size=15, max_overflow=5, pool_timeout=30s",
        "context": "Deployed to staging. P95 query latency dropped from 12ms to 8ms. Pool utilization peaks at 60%.",
    })
    logger.info("  Decision updated with implementation details")

    await asyncio.sleep(2)

    # Step 4: Extract - review outcome (FORGE: every decision needs an outcome)
    logger.info("\n📊 Step 4: review_outcome (FORGE Extract phase)")
    await call_tool(session, "review_outcome", {
        "id": decision_id,
        "outcome": "success",
        "actual_result": "P95 latency dropped 33% (12ms → 8ms). Pool utilization stable at 60%.",
        "lessons": "In-process pooling sufficient for single-container deployments. pgbouncer only needed for multi-process.",
    })
    logger.info("  Outcome recorded: success")
    logger.info(f"  🎯 Decision {decision_id[:8]} — full FORGE loop complete!")


async def scenario_guardrail_block(session: ClientSession) -> None:
    """Scenario 2: Guardrail blocks a risky decision.

    Demonstrates: pre_action with high stakes + low confidence = blocked
    """
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 2: Guardrail Block")
    logger.info("  Attempting: High-stakes decision with low confidence")
    logger.info("=" * 60)

    logger.info("\n📋 Step 1: pre_action (will be blocked)")
    result = await call_tool(session, "pre_action", {
        "description": "Deploy untested database migration to production during peak hours",
        "auto_record": True,
        "stakes": "high",
        "category": "process",
        "confidence": 0.4,
        "agent_id": AGENT_ID,
    })

    guardrails = result.get("guardrails", {})
    allowed = guardrails.get("allowed", True)

    if not allowed:
        violations = guardrails.get("violations", [])
        logger.info(f"  🚫 BLOCKED by guardrails!")
        for v in violations:
            logger.info(f"    - {v.get('name', '?')}: {v.get('message', '?')}")
        logger.info("  This is the correct behavior - the system prevented a risky action.")
    else:
        logger.info("  ⚠️ Guardrails allowed this (no high-stakes-low-confidence guardrail active)")
        logger.info("  In production, you'd configure guardrails to catch this pattern.")


async def scenario_review_decisions(session: ClientSession) -> None:
    """Scenario 3: Review past decisions and check calibration.

    Demonstrates: query_decisions → review_outcome → get_calibration_stats
    """
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 3: Review Past Decisions")
    logger.info("  Checking calibration and reviewing outcomes")
    logger.info("=" * 60)

    # Query recent decisions
    logger.info("\n🔍 Step 1: query_decisions (find decisions to review)")
    result = await call_tool(session, "query_decisions", {
        "query": "infrastructure and performance decisions",
        "limit": 5,
    })

    decisions = result.get("decisions", [])
    logger.info(f"  Found {len(decisions)} similar decisions")
    for d in decisions[:3]:
        reviewed = "✅" if d.get("reviewed") else "⏳"
        logger.info(f"    {reviewed} [{d.get('category')}] {d.get('title', d.get('decision', '?'))[:50]}")

    await asyncio.sleep(2)

    # Check calibration stats
    logger.info("\n📊 Step 2: get_stats (calibration check)")
    stats = await call_tool(session, "get_stats", {})

    total = stats.get("total_decisions", 0)
    reviewed = stats.get("reviewed_decisions", 0)
    accuracy = stats.get("accuracy", 0)
    brier = stats.get("brier_score", 0)
    logger.info(f"  Total decisions: {total}")
    logger.info(f"  Reviewed: {reviewed}")
    logger.info(f"  Accuracy: {accuracy:.1%}" if isinstance(accuracy, float) else f"  Accuracy: {accuracy}")
    logger.info(f"  Brier score: {brier:.3f}" if isinstance(brier, float) else f"  Brier: {brier}")


async def scenario_session_context(session: ClientSession) -> None:
    """Scenario 4: Get accumulated session context.

    Demonstrates: get_session_context (the intelligence layer)
    """
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 4: Session Context")
    logger.info("  Fetching accumulated decision intelligence")
    logger.info("=" * 60)

    logger.info("\n🧠 get_session_context")
    result = await call_tool(session, "get_session_context", {
        "agent_id": AGENT_ID,
    })

    decisions_in_ctx = result.get("recent_decisions", [])
    wisdom = result.get("wisdom", [])
    calibration = result.get("calibration", {})

    logger.info(f"  Recent decisions in context: {len(decisions_in_ctx)}")
    logger.info(f"  Wisdom entries: {len(wisdom)}")
    if calibration:
        logger.info(f"  Calibration: Brier={calibration.get('brier_score', '?')}, Accuracy={calibration.get('accuracy', '?')}")


async def scenario_ready_check(session: ClientSession) -> None:
    """Scenario 5: Check what needs attention.

    Demonstrates: ready (prioritized cognitive actions)
    """
    logger.info("\n" + "=" * 60)
    logger.info("SCENARIO 5: Ready Check")
    logger.info("  What needs my attention?")
    logger.info("=" * 60)

    logger.info("\n📬 ready")
    result = await call_tool(session, "ready", {
        "agent_id": AGENT_ID,
    })

    actions = result.get("actions", [])
    logger.info(f"  Pending actions: {len(actions)}")
    for a in actions[:5]:
        logger.info(f"    [{a.get('priority', '?')}] {a.get('type', '?')}: {a.get('description', '?')[:50]}")

    if not actions:
        logger.info("  ✅ Nothing needs immediate attention!")


# =============================================================================
# Main loop
# =============================================================================

async def wait_for_server() -> None:
    """Wait for the CSTP server to be healthy."""
    health_url = f"{CSTP_URL}/health"
    logger.info(f"Waiting for CSTP server at {health_url}...")

    async with httpx.AsyncClient() as client:
        for attempt in range(60):
            try:
                resp = await client.get(health_url, timeout=5)
                if resp.status_code == 200:
                    logger.info("CSTP server is healthy!")
                    return
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            if attempt % 10 == 0 and attempt > 0:
                logger.info(f"  Still waiting... (attempt {attempt}/60)")
            await asyncio.sleep(2)

    logger.error("CSTP server did not become healthy in 120 seconds")
    sys.exit(1)


async def run_scenarios(session: ClientSession) -> None:
    """Run all demo scenarios once."""
    scenarios = [
        scenario_architecture_decision,
        scenario_guardrail_block,
        scenario_review_decisions,
        scenario_session_context,
        scenario_ready_check,
    ]

    for scenario in scenarios:
        try:
            await scenario(session)
        except Exception as e:
            logger.error(f"Scenario failed: {e}")
        await asyncio.sleep(3)


async def main() -> None:
    """Main entry point."""
    logger.info("🚀 Cognition Engines Demo Agent")
    logger.info(f"   MCP endpoint: {MCP_URL}")
    logger.info(f"   Agent ID: {AGENT_ID}")
    logger.info(f"   Loop interval: {LOOP_INTERVAL}s")
    logger.info("")

    await wait_for_server()

    cycle = 0
    while True:
        cycle += 1
        logger.info(f"\n{'#' * 60}")
        logger.info(f"# Demo Cycle {cycle}")
        logger.info(f"{'#' * 60}")

        try:
            async with streamablehttp_client(MCP_URL) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    logger.info("MCP session initialized")

                    # List available tools
                    tools = await session.list_tools()
                    logger.info(f"Available MCP tools: {len(tools.tools)}")
                    for t in tools.tools[:5]:
                        logger.info(f"  - {t.name}")
                    if len(tools.tools) > 5:
                        logger.info(f"  ... and {len(tools.tools) - 5} more")

                    await run_scenarios(session)

        except Exception as e:
            logger.error(f"MCP connection failed: {e}")
            logger.info("Retrying in 10 seconds...")
            await asyncio.sleep(10)
            continue

        logger.info(f"\n⏳ Sleeping {LOOP_INTERVAL}s before next cycle...")
        await asyncio.sleep(LOOP_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
