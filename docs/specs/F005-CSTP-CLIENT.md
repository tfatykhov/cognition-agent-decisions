# F005: CSTP Client

| Field | Value |
|-------|-------|
| Feature ID | F005 |
| Status | Draft |
| Priority | P1 |
| Depends On | F001 (Server Infrastructure) |
| Blocks | None |
| Decision | a42a3514 |

---

## Summary

Implement CSTP client library for calling remote agents' CSTP endpoints.

## Goals

1. Python client library for CSTP methods
2. CLI for manual calls
3. Auto-retry with backoff
4. Connection pooling
5. Agent registry for known agents

## Non-Goals

- Agent discovery service
- Automatic failover
- Load balancing

---

## Specification

### Client Library

```python
# a2a/client.py

from typing import Optional, List
import httpx

class CstpClient:
    """Client for calling CSTP endpoints on remote agents."""
    
    def __init__(
        self,
        agent_url: str,
        token: str,
        timeout: float = 30.0,
        retries: int = 3,
    ):
        self.agent_url = agent_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.retries = retries
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"Authorization": f"Bearer {token}"},
        )
    
    async def query_decisions(
        self,
        query: str,
        category: Optional[str] = None,
        min_confidence: Optional[float] = None,
        limit: int = 10,
    ) -> QueryDecisionsResponse:
        """Query remote agent's decision history."""
        ...
    
    async def check_guardrails(
        self,
        description: str,
        category: Optional[str] = None,
        stakes: str = "medium",
        confidence: Optional[float] = None,
        context: Optional[dict] = None,
    ) -> CheckGuardrailsResponse:
        """Check action against remote agent's guardrails."""
        ...
    
    async def announce_intent(
        self,
        intent: str,
        context: Optional[str] = None,
        category: Optional[str] = None,
        stakes: str = "medium",
        confidence: Optional[float] = None,
        correlation_id: Optional[str] = None,
    ) -> AnnounceIntentResponse:
        """Announce intent to remote agent."""
        ...
    
    async def get_agent_card(self) -> AgentCard:
        """Fetch remote agent's Agent Card."""
        ...
    
    async def close(self):
        """Close HTTP client."""
        await self._client.aclose()
```

### JSON-RPC Call

```python
async def _call(
    self,
    method: str,
    params: dict,
) -> dict:
    """Make JSON-RPC call with retry."""
    
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": str(uuid.uuid4()),
        "params": params,
    }
    
    for attempt in range(self.retries):
        try:
            response = await self._client.post(
                f"{self.agent_url}/cstp",
                json=request,
            )
            response.raise_for_status()
            
            result = response.json()
            
            if "error" in result:
                raise CstpError(
                    code=result["error"]["code"],
                    message=result["error"]["message"],
                )
            
            return result["result"]
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited, backoff
                await asyncio.sleep(2 ** attempt)
                continue
            raise
        
        except httpx.RequestError:
            if attempt < self.retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue
            raise
    
    raise CstpError(-32000, "Max retries exceeded")
```

### Agent Registry

```python
# a2a/registry.py

from pathlib import Path
import yaml

class AgentRegistry:
    """Registry of known CSTP agents."""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        self._agents: Dict[str, AgentConfig] = {}
        self._load()
    
    def _load(self):
        """Load agents from config file."""
        if self.config_path.exists():
            config = yaml.safe_load(self.config_path.read_text())
            for agent in config.get("agents", []):
                self._agents[agent["name"]] = AgentConfig(
                    name=agent["name"],
                    url=agent["url"],
                    token=os.environ.get(agent["token_env"]),
                )
    
    def get(self, name: str) -> Optional[AgentConfig]:
        """Get agent config by name."""
        return self._agents.get(name)
    
    def list(self) -> List[str]:
        """List known agent names."""
        return list(self._agents.keys())
    
    def client(self, name: str) -> CstpClient:
        """Get client for named agent."""
        agent = self.get(name)
        if not agent:
            raise ValueError(f"Unknown agent: {name}")
        return CstpClient(agent.url, agent.token)
```

### CLI

```bash
# Query decisions
uv run a2a/cli.py query "database migration" --agent security-policy

# Check guardrails  
uv run a2a/cli.py check "Deploy to production" --agent security-policy --stakes high

# Announce intent
uv run a2a/cli.py announce "Deploy auth service" --agent security-policy --stakes high

# Get agent card
uv run a2a/cli.py agent-card --agent security-policy

# List known agents
uv run a2a/cli.py agents
```

### CLI Implementation

```python
# a2a/cli.py

import click
import asyncio
from .client import CstpClient
from .registry import AgentRegistry

@click.group()
def cli():
    """CSTP Client CLI"""
    pass

@cli.command()
@click.argument("query")
@click.option("--agent", required=True, help="Target agent name or URL")
@click.option("--category", help="Filter by category")
@click.option("--limit", default=10, help="Max results")
def query(query: str, agent: str, category: str, limit: int):
    """Query remote agent's decisions."""
    
    async def run():
        registry = AgentRegistry(Path("config/agents.yaml"))
        client = registry.client(agent)
        
        try:
            result = await client.query_decisions(
                query=query,
                category=category,
                limit=limit,
            )
            
            for decision in result.decisions:
                click.echo(f"- [{decision.id}] {decision.title}")
                click.echo(f"  Confidence: {decision.confidence:.0%}")
                click.echo(f"  Distance: {decision.distance:.3f}")
                click.echo()
        finally:
            await client.close()
    
    asyncio.run(run())

@cli.command()
@click.argument("description")
@click.option("--agent", required=True)
@click.option("--stakes", default="medium")
@click.option("--confidence", type=float)
def check(description: str, agent: str, stakes: str, confidence: float):
    """Check action against remote guardrails."""
    
    async def run():
        registry = AgentRegistry(Path("config/agents.yaml"))
        client = registry.client(agent)
        
        try:
            result = await client.check_guardrails(
                description=description,
                stakes=stakes,
                confidence=confidence,
            )
            
            if result.allowed:
                click.echo("✅ Allowed")
            else:
                click.echo("❌ Blocked")
                for v in result.violations:
                    click.echo(f"  - {v.guardrailId}: {v.message}")
        finally:
            await client.close()
    
    asyncio.run(run())
```

---

## Configuration

### agents.yaml

```yaml
agents:
  - name: "security-policy"
    url: "https://security.example.com"
    token_env: "CSTP_TOKEN_SECURITY"
    
  - name: "claude-ops"
    url: "https://claude-ops.example.com"
    token_env: "CSTP_TOKEN_CLAUDE"
    
  - name: "local"
    url: "http://localhost:8100"
    token_env: "CSTP_TOKEN_LOCAL"

defaults:
  timeout_seconds: 30
  retries: 3
```

---

## Implementation Tasks

- [ ] Create `CstpClient` class
- [ ] Implement `query_decisions` method
- [ ] Implement `check_guardrails` method
- [ ] Implement `announce_intent` method
- [ ] Implement `get_agent_card` method
- [ ] Add retry logic with exponential backoff
- [ ] Create `AgentRegistry` class
- [ ] Implement CLI commands
- [ ] Add config file loading
- [ ] Write unit tests with mocked server
- [ ] Write integration test against real server

---

## Acceptance Criteria

1. `CstpClient` successfully calls all CSTP methods
2. Retry logic handles transient failures
3. Rate limiting (429) triggers backoff
4. Registry loads agents from config
5. CLI commands work for all methods
6. Errors map to `CstpError` exceptions
7. Connection pooling reuses HTTP client
