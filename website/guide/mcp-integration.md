# MCP Integration

> **Feature:** F022, F046, F047 | **Status:** Shipped in v0.10.0+

Cognition Engines exposes 11 tools via the [Model Context Protocol](https://modelcontextprotocol.io/) for integration with Claude Code, Claude Desktop, OpenClaw, and any MCP-compliant agent.

## Endpoint

```
http://your-server:9991/mcp
```

Streamable HTTP - handles both POST (tool calls) and GET (SSE events).

## Primary Tools (Start Here)

| Tool | Description |
|------|-------------|
| `pre_action` **(PRIMARY)** | All-in-one pre-action check: queries similar past decisions, evaluates guardrails, fetches calibration context, extracts patterns, and optionally records the decision. One call replaces `query_decisions` + `check_action` + `log_decision`. |
| `get_session_context` **(PRIMARY)** | Full cognitive context for session start: agent profile (accuracy, Brier, tendency), relevant decisions, guardrails, calibration by category, overdue reviews, and confirmed patterns. Available in JSON or markdown for system prompt injection. |

## Granular Tools (Fine-Grained Control)

| Tool | Description |
|------|-------------|
| `query_decisions` | Search past decisions with optional `bridge_side` (prefer `pre_action`) |
| `check_action` | Validate against guardrails (prefer `pre_action`) |
| `log_decision` | Record a new decision with reasoning (prefer `pre_action` with `auto_record`) |
| `review_outcome` | Record what actually happened |
| `get_stats` | Calibration statistics (prefer `get_session_context`) |
| `get_decision` | Full decision details by ID |
| `get_reason_stats` | Which reason types predict success |
| `update_decision` | Update tags/pattern on existing decisions |
| `record_thought` | Capture chain-of-thought reasoning steps |

## Recommended Workflow

```
Session start → get_session_context (load cognitive context)
       ↓
Decision point → pre_action (query + guardrails + record in one call)
       ↓
During work → record_thought (capture reasoning)
       ↓
After work → update_decision (finalize decision text and context)
       ↓
Later → review_outcome (record success/failure for calibration)
```

## Claude Code CLI

Add to your project's `.mcp.json` (or global `~/.claude.json`):

```json
{
  "mcpServers": {
    "decisions": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "http://your-server:9991/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer YOUR_CSTP_TOKEN"
      ]
    }
  }
}
```

On Windows, use `cmd` as the command:

```json
{
  "mcpServers": {
    "decisions": {
      "command": "cmd",
      "args": [
        "/c", "npx", "mcp-remote@latest",
        "http://your-server:9991/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer YOUR_CSTP_TOKEN"
      ]
    }
  }
}
```

## Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "decisions": {
      "command": "npx",
      "args": [
        "mcp-remote@latest",
        "http://your-server:9991/mcp",
        "--allow-http",
        "--header",
        "Authorization: Bearer YOUR_CSTP_TOKEN"
      ]
    }
  }
}
```

## OpenClaw Configuration

Add to your OpenClaw gateway config:

```yaml
mcp:
  servers:
    cognition-engines:
      url: http://your-server:9991/mcp
      headers:
        Authorization: "Bearer your-token"
```

## Stdio Transport

```bash
python -m a2a.mcp_server
```

## Example: Pre-Action Tool

```json
{
  "name": "pre_action",
  "arguments": {
    "action": {
      "description": "Refactor auth module to use JWT",
      "category": "architecture",
      "stakes": "high",
      "confidence": 0.82
    },
    "reasons": [
      {"type": "analysis", "text": "Stateless auth scales better for microservices"},
      {"type": "pattern", "text": "Team successfully used JWT in 2 other services"}
    ],
    "tags": ["auth", "jwt", "refactor"],
    "pattern": "Stateless auth scales better than session-based"
  }
}
```

Returns: `allowed` status, relevant past decisions, guardrail results, calibration context, confirmed patterns, and optionally a recorded `decision_id`.

## Example: Session Context Tool

```json
{
  "name": "get_session_context",
  "arguments": {
    "task_description": "Build authentication service for user API",
    "format": "markdown"
  }
}
```

Returns: markdown-formatted cognitive context ready for system prompt injection, including agent profile, relevant decisions, guardrails, calibration by category, and confirmed patterns.

## vs JSON-RPC

MCP adds session management overhead. For stateless workflows, the [JSON-RPC API](/reference/api) via `cstp.py` is simpler. Use MCP when your agent platform expects it.
