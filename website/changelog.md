# Changelog

## v0.10.0 - Decision Intelligence with Auto-Capture
*February 8, 2026*

Every decision now automatically captures its full cognitive context - deliberation traces, bridge-definitions, and related decision links - with zero client changes.

### Features
- **F022: MCP Server** - 7 native MCP tools at `/mcp`
- **F023: Deliberation Traces** - auto-capture query/check as structured inputs
- **F024: Bridge-Definitions** - structure/function dual descriptions with directional search
- **F025: Related Decisions** - auto-populated graph edges from query results
- `cstp.getDecision` - full decision details by ID
- `cstp.getReasonStats` - reason-type calibration analytics
- Agent Quick Start Guide for onboarding other agents

### No Breaking Changes
All features are additive and backward-compatible.

## v0.8.0 - Decision Intelligence Platform
*February 5, 2026*

- CSTP server with JSON-RPC 2.0 API
- Hybrid retrieval (BM25 + semantic)
- Drift alerts and confidence variance monitoring
- Docker deployment with dashboard
