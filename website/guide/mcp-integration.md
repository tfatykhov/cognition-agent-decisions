# MCP Integration

> **Feature:** F022 | **Status:** Shipped in v0.10.0

Cognition Engines exposes 7 tools via the [Model Context Protocol](https://modelcontextprotocol.io/) for integration with Claude Desktop, OpenClaw, and any MCP-compliant agent.

## Endpoint

```
http://your-server:9991/mcp
```

Streamable HTTP - handles both POST (tool calls) and GET (SSE events).

## Available Tools

| Tool | Description |
|------|-------------|
| `query_decisions` | Search past decisions with optional `bridge_side` |
| `check_action` | Validate against guardrails |
| `log_decision` | Record a new decision with reasoning |
| `review_outcome` | Record what actually happened |
| `get_stats` | Calibration statistics |
| `get_decision` | Full decision details by ID |
| `get_reason_stats` | Which reason types predict success |

## Claude Desktop Configuration

Add to your Claude Desktop MCP config:

```json
{
  "mcpServers": {
    "cognition-engines": {
      "url": "http://your-server:9991/mcp",
      "headers": {
        "Authorization": "Bearer your-token"
      }
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

## Example: Query Tool

```json
{
  "name": "query_decisions",
  "arguments": {
    "query": "handling API rate limits",
    "bridge_side": "function",
    "limit": 5
  }
}
```

Returns matching decisions with summaries, confidence scores, outcomes, and distances.

## vs JSON-RPC

MCP adds session management overhead. For stateless workflows, the [JSON-RPC API](/reference/api) via `cstp.py` is simpler. Use MCP when your agent platform expects it.
