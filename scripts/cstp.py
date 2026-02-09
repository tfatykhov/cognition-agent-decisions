#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["httpx"]
# ///
"""CSTP client for decision intelligence.

Usage:
    cstp.py query "search text" [--top 5] [--bridge-side function|structure]
    cstp.py get <id>
    cstp.py list-guardrails [--scope project]
    cstp.py check -d "action" -s high -f 0.8
    cstp.py record -d "decision" -f 0.85 -c architecture -s medium
    cstp.py review --id abc123 --outcome success --result "what happened"
    cstp.py calibration
    cstp.py reason-stats

Configuration:
    Set CSTP_URL and CSTP_TOKEN environment variables, or create
    .secrets/cstp.env in the project root with:
        CSTP_URL=http://localhost:9991
        CSTP_TOKEN=your-token
"""

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

# Load config
def load_config() -> tuple[str, str]:
    """Load CSTP config from .secrets/cstp.env."""
    env_path = Path(__file__).parent.parent / ".secrets" / "cstp.env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    
    url = os.environ.get("CSTP_URL", "http://localhost:9991")
    token = os.environ.get("CSTP_TOKEN", "")
    return url, token


def cstp_call(method: str, params: dict) -> dict:
    """Make a CSTP JSON-RPC call."""
    url, token = load_config()
    
    try:
        response = httpx.post(
            f"{url}/cstp",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
                "id": 1,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"Error connecting to CSTP server: {e}", file=sys.stderr)
        sys.exit(1)
    
    if "error" in data:
        print(f"Error: {data['error']['message']}", file=sys.stderr)
        sys.exit(1)
    return data.get("result", {})


def cmd_query(args):
    """Query similar decisions."""
    params = {"query": args.query, "limit": args.top}
    if hasattr(args, "mode") and args.mode:
        params["retrievalMode"] = args.mode
    if args.category:
        params["filters"] = {"category": args.category}
    if args.project:
        if "filters" not in params: params["filters"] = {}
        params["filters"]["project"] = args.project
    if hasattr(args, "bridge_side") and args.bridge_side:
        params["bridgeSide"] = args.bridge_side
    
    result = cstp_call("cstp.queryDecisions", params)
    
    if not result.get("decisions"):
        print("No similar decisions found.")
        return
    
    mode_label = f" [{params.get('retrievalMode', 'semantic')}]"
    bridge_label = f" (bridge: {args.bridge_side})" if hasattr(args, "bridge_side") and args.bridge_side else ""
    print(f"Found {result['total']} similar decisions{mode_label}{bridge_label}:\n")
    for d in result["decisions"]:
        print(f"  [{d['id']}] {d.get('title', 'Untitled')}")
        print(f"      Category: {d['category']} | Stakes: {d.get('stakes', '?')} | Confidence: {d['confidence']}")
        print(f"      Distance: {d['distance']:.3f}")
        print()


def cmd_list_guardrails(args):
    """List active guardrails."""
    params = {}
    if args.scope:
        params["scope"] = args.scope
        
    result = cstp_call("cstp.listGuardrails", params)
    
    guardrails = result.get("guardrails", [])
    if not guardrails:
        print("No active guardrails found.")
        return

    print(f"ACTIVE GUARDRAILS ({len(guardrails)}):")
    for g in guardrails:
        action = g.get('action', 'warn').upper()
        icon = "🚫" if action == "BLOCK" else "⚠️"
        print(f"\n{icon} {g['id']} ({action})")
        print(f"   {g.get('description', '')}")
        
        if g.get('conditions'):
            print("   Conditions:")
            for c in g['conditions']:
                print(f"     - {c['field']} {c['operator']} {c['value']}")
        
        if g.get('scope'):
            print(f"   Scope: {', '.join(g['scope'])}")


def cmd_check(args):
    """Check guardrails before acting."""
    params = {
        "action": {
            "description": args.description,
            "category": args.category,
            "stakes": args.stakes,
            "confidence": args.confidence,
        }
    }
    
    result = cstp_call("cstp.checkGuardrails", params)
    
    if result.get("allowed"):
        print("✅ ALLOWED — No guardrail violations.")
    else:
        print("🚫 BLOCKED — Guardrail violations:")
        for v in result.get("violations", []):
            print(f"  - {v['name']}: {v['message']}")
    
    if result.get("warnings"):
        print("\n⚠️ Warnings:")
        for w in result["warnings"]:
            print(f"  - {w['name']}: {w['message']}")


def cmd_record(args):
    """Record a decision."""
    params = {
        "decision": args.decision,
        "confidence": args.confidence,
        "category": args.category,
        "stakes": args.stakes,
    }
    if args.context:
        params["context"] = args.context
    
    # Project context
    if args.project:
        if "project_context" not in params: params["project_context"] = {}
        params["project_context"]["project"] = args.project
    if args.pr:
        if "project_context" not in params: params["project_context"] = {}
        params["project_context"]["pr"] = args.pr
    
    # Parse reasons (format: "type:text" or "type:text:strength")
    if args.reason:
        reasons = []
        for r in args.reason:
            parts = r.split(":", 2)
            if len(parts) >= 2:
                reason = {"type": parts[0], "text": parts[1]}
                # Optional strength
                if len(parts) == 3:
                    try:
                        reason["strength"] = float(parts[2])
                    except ValueError:
                        pass
                reasons.append(reason)
        if reasons:
            params["reasons"] = reasons
    
    # F024: Bridge-definition
    if getattr(args, "structure", None) or getattr(args, "function", None):
        bridge = {}
        if args.structure:
            bridge["structure"] = args.structure
        if args.function:
            bridge["function"] = args.function
        if getattr(args, "tolerance", None):
            bridge["tolerance"] = args.tolerance
        if getattr(args, "enforcement", None):
            bridge["enforcement"] = args.enforcement
        if getattr(args, "prevention", None):
            bridge["prevention"] = args.prevention
        params["bridge"] = bridge
    
    result = cstp_call("cstp.recordDecision", params)
    
    print(f"Decision recorded: {result['id']}")
    print(f"   Indexed: {result.get('indexed', False)}")
    if result.get("deliberation_auto"):
        print(f"   Deliberation: auto-captured ({result.get('deliberation_inputs_count', 0)} inputs)")
    if result.get("bridge_auto"):
        print(f"   Bridge: auto-extracted")
    elif "bridge" in (params or {}):
        print(f"   Bridge: explicit")
    if result.get("related_count"):
        print(f"   Related: {result['related_count']} linked decisions")


def cmd_get(args):
    """Get full decision details by ID."""
    result = cstp_call("cstp.getDecision", {"id": args.id})

    if not result.get("found"):
        print(f"Decision not found: {args.id}")
        return

    d = result["decision"]
    print(f"[{d.get('id', args.id)}] {d.get('decision', d.get('summary', 'Untitled'))}")
    print(f"   Category: {d.get('category', '?')} | Stakes: {d.get('stakes', '?')} | Confidence: {d.get('confidence', '?')}")
    print(f"   Date: {d.get('date', '?')}")

    if d.get("context"):
        print(f"   Context: {d['context'][:120]}")

    if d.get("reasons"):
        print(f"   Reasons:")
        for r in d["reasons"]:
            print(f"      [{r.get('type', '?')}] {r.get('text', '')[:80]}")

    if d.get("bridge"):
        b = d["bridge"]
        print(f"   Bridge:")
        if b.get("structure"):
            print(f"      Structure: {b['structure'][:80]}")
        if b.get("function"):
            print(f"      Function: {b['function'][:80]}")

    if d.get("related_to"):
        print(f"   Related ({len(d['related_to'])}):")
        for r in d["related_to"]:
            print(f"      [{r['id']}] {r.get('summary', '?')[:60]} (dist: {r.get('distance', 0):.3f})")

    if d.get("deliberation"):
        delib = d["deliberation"]
        inputs = delib.get("inputs", [])
        print(f"   Deliberation: {len(inputs)} inputs")

    if d.get("outcome"):
        print(f"   Outcome: {d['outcome']}")


def cmd_review(args):
    """Review a decision with outcome."""
    params = {
        "decision_id": args.id,  # API expects decision_id
        "outcome": args.outcome,
    }
    if args.result:
        params["actual_result"] = args.result
    if args.lessons:
        params["lessons"] = args.lessons
    
    result = cstp_call("cstp.reviewDecision", params)
    
    if result.get("success"):
        print(f"✅ Decision {args.id} reviewed successfully.")
    else:
        print(f"❌ Failed to review decision: {result.get('error')}")


def cmd_calibration(args):
    """Get calibration stats."""
    params = {}
    if args.project:
        params["project"] = args.project
    
    result = cstp_call("cstp.getCalibration", params)
    
    if result.get("overall"):
        o = result["overall"]
        print(f"📊 Calibration Stats:")
        print(f"   Decisions: {o['total_decisions']} ({o['reviewed_decisions']} reviewed)")
        print(f"   Accuracy: {o['accuracy']*100:.1f}%")
        print(f"   Brier Score: {o['brier_score']:.3f}")
        print(f"   Calibration: {o['interpretation']}")
    else:
        print("Not enough data for calibration.")
    
    for r in result.get("recommendations", []):
        print(f"\n💡 {r['message']}")


def cmd_reason_stats(args):
    """Get reason-type calibration stats."""
    params = {"minReviewed": args.min_reviewed}
    filters = {}
    if args.category:
        filters["category"] = args.category
    if args.stakes:
        filters["stakes"] = args.stakes
    if args.project:
        filters["project"] = args.project
    if filters:
        params["filters"] = filters

    result = cstp_call("cstp.getReasonStats", params)

    print(f"📊 Reason-Type Stats ({result.get('totalDecisions', 0)} decisions, "
          f"{result.get('reviewedDecisions', 0)} reviewed)\n")

    # Per-type stats
    types = result.get("byReasonType", [])
    if types:
        print("  TYPE            USES  REVIEWED  SUCCESS  AVG_CONF  BRIER")
        print("  " + "-" * 62)
        for t in types:
            brier = f"{t['brierScore']:.4f}" if t.get("brierScore") is not None else "  n/a "
            print(f"  {t['reasonType']:<16} {t['totalUses']:>4}  {t['reviewedUses']:>8}  "
                  f"{t['successRate']*100:>5.1f}%  {t['avgConfidence']*100:>6.1f}%  {brier}")
    else:
        print("  No reason types found.")

    # Diversity
    div = result.get("diversity")
    if div:
        print(f"\n🔀 Diversity (Minsky Ch 18 parallel bundles):")
        print(f"   Avg distinct types/decision: {div['avgTypesPerDecision']:.1f}")
        print(f"   Avg reasons/decision: {div['avgReasonsPerDecision']:.1f}")

        if div.get("diversityBuckets"):
            print(f"\n  DISTINCT_TYPES  DECISIONS  REVIEWED  SUCCESS  BRIER")
            print("  " + "-" * 55)
            for b in div["diversityBuckets"]:
                sr = f"{b['successRate']*100:.1f}%" if b.get("successRate") is not None else " n/a "
                brier = f"{b['brierScore']:.4f}" if b.get("brierScore") is not None else " n/a "
                print(f"  {b['distinctReasonTypes']:>14}  {b['totalDecisions']:>9}  "
                      f"{b['reviewedDecisions']:>8}  {sr:>7}  {brier}")

    # Recommendations
    recs = result.get("recommendations", [])
    if recs:
        print()
        for r in recs:
            icon = "⚠️" if r["severity"] == "warning" else "💡"
            print(f"  {icon} {r['message']}")


def main():
    parser = argparse.ArgumentParser(description="CSTP Decision Intelligence Client")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Query
    p_query = subparsers.add_parser("query", help="Query similar decisions")
    p_query.add_argument("query", help="Search text")
    p_query.add_argument("--top", type=int, default=5, help="Number of results")
    p_query.add_argument("--category", help="Filter by category")
    p_query.add_argument("--project", help="Filter by project")
    p_query.add_argument("--mode", default="hybrid", choices=["semantic", "keyword", "hybrid"], help="Retrieval mode")
    p_query.add_argument("--bridge-side", choices=["structure", "function"], help="Search by bridge side")
    p_query.set_defaults(func=cmd_query)

    # List Guardrails
    p_list = subparsers.add_parser("list-guardrails", help="List active guardrails")
    p_list.add_argument("--scope", help="Filter by scope (e.g. project name)")
    p_list.set_defaults(func=cmd_list_guardrails)
    
    # Check
    p_check = subparsers.add_parser("check", help="Check guardrails")
    p_check.add_argument("--description", "-d", required=True, help="Action description")
    p_check.add_argument("--category", "-c", default="process", help="Category")
    p_check.add_argument("--stakes", "-s", default="medium", help="Stakes level")
    p_check.add_argument("--confidence", "-f", type=float, default=0.8, help="Confidence")
    p_check.set_defaults(func=cmd_check)
    
    # Record
    p_record = subparsers.add_parser("record", help="Record a decision")
    p_record.add_argument("--decision", "-d", required=True, help="Decision summary")
    p_record.add_argument("--confidence", "-f", type=float, required=True, help="Confidence")
    p_record.add_argument("--category", "-c", required=True, help="Category")
    p_record.add_argument("--stakes", "-s", default="medium", help="Stakes level")
    p_record.add_argument("--context", help="Situation/question being decided")
    p_record.add_argument("--reason", "-r", action="append", help="Reason (type:text)")
    p_record.add_argument("--project", help="Project (owner/repo)")
    p_record.add_argument("--pr", type=int, help="PR number")
    p_record.add_argument("--structure", help="Bridge: what the pattern looks like")
    p_record.add_argument("--function", help="Bridge: what problem it solves")
    p_record.add_argument("--tolerance", action="append", help="Bridge: features that don't matter")
    p_record.add_argument("--enforcement", action="append", help="Bridge: features that must be present")
    p_record.add_argument("--prevention", action="append", help="Bridge: features that must not be present")
    p_record.set_defaults(func=cmd_record)
    
    # Get decision
    p_get = subparsers.add_parser("get", help="Get full decision details")
    p_get.add_argument("id", help="Decision ID")
    p_get.set_defaults(func=cmd_get)

    # Review
    p_review = subparsers.add_parser("review", help="Review decision outcome")
    p_review.add_argument("--id", required=True, help="Decision ID")
    p_review.add_argument("--outcome", required=True, choices=["success", "partial", "failure", "abandoned"])
    p_review.add_argument("--result", help="Actual result")
    p_review.add_argument("--lessons", help="Lessons learned")
    p_review.set_defaults(func=cmd_review)
    
    # Calibration
    p_cal = subparsers.add_parser("calibration", help="Get calibration stats")
    p_cal.add_argument("--project", help="Filter by project")
    p_cal.set_defaults(func=cmd_calibration)

    # Reason Stats
    p_reasons = subparsers.add_parser("reason-stats", help="Get reason-type calibration stats")
    p_reasons.add_argument("--category", help="Filter by category")
    p_reasons.add_argument("--stakes", help="Filter by stakes")
    p_reasons.add_argument("--project", help="Filter by project")
    p_reasons.add_argument("--min-reviewed", type=int, default=3, help="Min reviewed for type stats")
    p_reasons.set_defaults(func=cmd_reason_stats)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
