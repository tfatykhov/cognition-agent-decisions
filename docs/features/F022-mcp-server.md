# F022: MCP Server Implementation Plan

## 1. Overview
Implement an **MCP (Model Context Protocol) Server** for the CSTP Decision Engine.
This allows any MCP-compliant agent (Claude Desktop, OpenClaw, other AI assistants) to natively discover and use CSTP capabilities without custom client code.

## 2. Architecture
- **Bridge Pattern:** Create `a2a/mcp_server.py` that wraps the existing `Dispatcher`.
- **Transport:** Support Standard Input/Output (stdio) for local agents and SSE (Server-Sent Events) for remote.
- **Protocol:** Implement MCP v1.0.0-rc.1 spec.

## 3. Exposed Tools (Resources & Prompts)

The MCP server will expose CSTP methods as **Tools**:

| CSTP Method | MCP Tool Name | Description |
|-------------|---------------|-------------|
| `cstp.queryDecisions` | `query_decisions` | Find similar past decisions using semantic search |
| `cstp.checkGuardrails` | `check_action` | Validate an intended action against safety policies |
| `cstp.recordDecision` | `log_decision` | Record a final decision to the immutable log |
| `cstp.reviewDecision` | `review_outcome` | Record the outcome of a past decision |
| `cstp.getCalibration` | `get_stats` | Get accuracy and Brier score metrics |

## 4. Implementation Phases

### Phase 1: Core MCP Bridge (2 Days)
- [ ] Add `mcp` python package dependency
- [ ] Create `a2a/mcp_server.py` using `mcp.server.fastmcp`
- [ ] Map `query_decisions` tool to `dispatcher.query_decisions`
- [ ] Map `check_action` tool to `dispatcher.check_guardrails`
- [ ] Verify local stdio connection with Claude Desktop

### Phase 2: Full Tool Suite (2 Days)
- [ ] Map `log_decision` (record)
- [ ] Map `review_outcome` (review)
- [ ] Map `get_stats` (calibration)
- [ ] Add input schema validation (Pydantic models)

### Phase 3: Docker & Deployment (1 Day)
- [ ] Update `Dockerfile` to expose MCP entrypoint
- [ ] Add SSE (HTTP) transport support for remote agents
- [ ] Update documentation with "How to connect via MCP"

## 5. Usage Example (Claude Desktop Config)

```json
{
  "mcpServers": {
    "cstp": {
      "command": "docker",
      "args": ["exec", "-i", "cstp", "uv", "run", "python", "-m", "a2a.mcp_server"]
    }
  }
}
```

## 6. Success Criteria
1.  **Discovery:** Agent sees `query_decisions` and `check_action` in its tool list.
2.  **Execution:** Agent can successfully query past decisions via the tool.
3.  **Safety:** Guardrails are enforced exactly as they are in the JSON-RPC API.
