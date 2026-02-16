# MCP Integration

> **Feature:** F022, F044, F045, F046, F047 | **Status:** Shipped in v0.12.0

Cognition Engines exposes 14+ tools via the [Model Context Protocol](https://modelcontextprotocol.io/) for integration with Claude Code, Claude Desktop, OpenClaw, and any MCP-compliant agent.

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
| `ready` **(PRIMARY)** | Prioritized cognitive maintenance queue: overdue reviews, calibration drift, stale decisions. Filter by priority, type, category. |

## Graph Tools (F045)

| Tool | Description |
|------|-------------|
| `link_decisions` | Create typed edges between decisions (`relates_to`, `supersedes`, `depends_on`) with optional weight |
| `get_graph` | Query subgraph around a decision with configurable depth and edge type filters. Returns nodes with metadata and weighted edges. |

## Granular Tools (Fine-Grained Control)

| Tool | Description |
|------|-------------|
| `query_decisions` | Search past decisions with optional `bridge_side` (prefer `pre_action`) |
| `check_action` | Validate against guardrails (prefer `pre_action`) |
| `log_decision` | Record a decision manually — **last resort** when `pre_action` wasn't used |
| `review_outcome` | Record what actually happened |
| `get_stats` | Calibration statistics (prefer `get_session_context`) |
| `get_decision` | Full decision details by ID |
| `get_reason_stats` | Which reason types predict success |
| `update_decision` | Update tags/pattern on existing decisions |
| `record_thought` | Capture chain-of-thought reasoning steps |

## Recommended Workflow

```
Session start    → get_session_context       (load cognitive context)
       ↓
Maintenance      → ready                     (check for overdue reviews, drift)
       ↓
Decision point   → pre_action                (query + guardrails + record)
                   (auto_record: true)        → returns decisionId
       ↓
During work      → record_thought            (capture reasoning)
                   (decision_id: from above)  → thoughts attach in real-time
       ↓
After work       → update_decision           (finalize decision text)
                   (id: decisionId)
       ↓
Link related     → link_decisions            (explicit relationships)
       ↓
Later            → review_outcome            (record success/failure)
```

### Multi-Agent Isolation

When multiple agents share a single MCP connection (e.g. Claude Code sub-agents), pass `agent_id` to isolate deliberation streams:

```
pre_action(agent_id: "planner", ...)           → decisionId: "abc123"
record_thought(agent_id: "planner", decision_id: "abc123", text: "...")
update_decision(id: "abc123", ...)
```

Each agent's thoughts are tracked via composite keys (`agent:{id}:decision:{id}`), preventing cross-contamination.

### When to Use `log_decision`

`log_decision` is a **last resort** for recording decisions without prior context. Use it only when:
- The agent didn't call `pre_action` (legacy or spontaneous decision)
- You need full manual control over all fields
- No deliberation tracking is needed

For the standard flow, `pre_action(auto_record: true)` + `record_thought` + `update_decision` is always preferred.

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
