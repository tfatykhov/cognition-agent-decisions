# MCP Quickstart Guide

Connect any MCP-compliant agent to CSTP decision intelligence.

## Claude Desktop

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

## Local Development

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

## Architecture

```
MCP Client (Claude, OpenClaw, etc.)
    │  stdio (JSON-RPC over stdin/stdout)
    ▼
a2a/mcp_server.py (FastMCP bridge)
    │  direct function calls
    ▼
CSTP Services (query, guardrails, etc.)
    │
    ▼
ChromaDB (semantic index) + YAML files (decisions)
```

The MCP server is a thin bridge — it validates inputs via Pydantic schemas,
then delegates to the same services used by the JSON-RPC API.
