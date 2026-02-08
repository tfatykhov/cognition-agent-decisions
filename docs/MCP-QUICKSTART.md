# MCP Quickstart Guide

Connect any MCP-compliant agent to CSTP decision intelligence.

## Remote Access (Streamable HTTP)

The CSTP server exposes MCP tools via Streamable HTTP at `/mcp`:

```
http://your-server:8100/mcp
```

### Claude Code

```bash
claude mcp add --transport http cstp-decisions http://your-server:8100/mcp
```

### Any MCP Client

Point your MCP client to `http://your-server:8100/mcp` using the
Streamable HTTP transport. The endpoint handles both POST (tool calls)
and GET (event streams) on the same path.

## Local Access (stdio)

### Claude Desktop

Add to your Claude Desktop config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cstp": {
      "command": "docker",
      "args": ["exec", "-i", "cstp", "python", "-m", "a2a.mcp_server"],
      "env": {}
    }
  }
}
```

> **Note:** The CSTP container must be running. The MCP server inherits
> all environment variables (CHROMA_URL, GEMINI_API_KEY, etc.) from the container.

### Local Development

```bash
# Install with MCP support
pip install ".[mcp]"

# Set required environment variables
export CHROMA_URL=http://localhost:8000
export GEMINI_API_KEY=your-key
export DECISIONS_PATH=./decisions

# Run MCP server (stdio)
python -m a2a.mcp_server
```

## Available Tools

### `query_decisions`

Find similar past decisions using semantic search, keyword matching, or hybrid retrieval.

**Input:**
```json
{
  "query": "database migration strategy",
  "limit": 5,
  "retrieval_mode": "hybrid",
  "filters": {
    "category": "architecture",
    "project": "owner/repo"
  }
}
```

**Output:** List of matching decisions with IDs, titles, confidence scores, categories,
stakes, dates, and similarity distances.

### `check_action`

Validate an intended action against safety guardrails.

**Input:**
```json
{
  "description": "Deploy to production without tests",
  "stakes": "high",
  "confidence": 0.6
}
```

**Output:** Whether the action is allowed, any blocking violations, and warnings.

### `log_decision`

Record a decision to the immutable decision log.

**Input:**
```json
{
  "decision": "Use PostgreSQL for the new service",
  "confidence": 0.85,
  "category": "architecture",
  "stakes": "high",
  "context": "Evaluated PostgreSQL vs MongoDB for the analytics service",
  "reasons": [
    {"type": "analysis", "text": "Need ACID transactions for financial data"},
    {"type": "pattern", "text": "Team has strong PostgreSQL expertise"}
  ],
  "project": "owner/repo",
  "pr": 42
}
```

**Output:** Decision ID, file path, indexed status, and timestamp.

### `review_outcome`

Record the outcome of a past decision for calibration.

**Input:**
```json
{
  "id": "a1b2c3d4",
  "outcome": "success",
  "actual_result": "PostgreSQL handled the load well, no issues",
  "lessons": "ACID transactions were indeed critical for data integrity"
}
```

**Output:** Review status, updated path, and reindex confirmation.

### `get_stats`

Get calibration statistics to assess decision-making quality.

**Input:**
```json
{
  "category": "architecture",
  "window": "90d"
}
```

**Output:** Brier score, accuracy, confidence distribution, decision counts,
and confidence variance metrics.

## Architecture

```
MCP Client (Claude Code, OpenClaw, etc.)
    │
    ├── Streamable HTTP ──► :8100/mcp ──► StreamableHTTPSessionManager
    │                                         │
    └── stdio ────────────► a2a.mcp_server ───┤
                                              │
                                         MCP Server (5 tools)
                                              │  direct function calls
                                              ▼
                                     CSTP Services (query, guardrails,
                                         decisions, calibration)
                                              │
                                              ▼
                                     ChromaDB + YAML files
```

The MCP server is a thin bridge — it validates inputs via Pydantic schemas,
then delegates to the same services used by the JSON-RPC API. Both stdio and
Streamable HTTP transports share the same `Server` instance and tool handlers.
