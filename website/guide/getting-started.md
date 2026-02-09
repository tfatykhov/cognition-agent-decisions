# Installation Guide

This guide covers three installation methods: Docker (recommended for production), local development, and integration as a skill.

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | ≥ 3.11 | Core runtime |
| Docker + Docker Compose | Latest | Container deployment |
| Gemini API Key | — | Text embeddings (`text-embedding-004`) |
| ChromaDB | ≥ 0.4 | Vector database |

### Obtaining a Gemini API Key

1. Visit [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Create a new API key
3. Save it — you'll need it for configuration

---

## Method 1: Docker (Recommended)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cd cognition-agent-decisions

# 2. Create environment file
cp .env.example .env

# 3. Edit .env with your settings
#    At minimum, set:
#    - GEMINI_API_KEY=your_key_here
#    - CSTP_AUTH_TOKENS=myagent:mysecrettoken

# 4. Start services
docker compose up -d

# 5. Verify
curl http://localhost:8100/health
```

### What Gets Started

| Service | Port | Description |
|---------|------|-------------|
| `cstp-server` | 8100 | CSTP API server |
| `chromadb` | 8000 | ChromaDB vector database |

### Docker Compose Details

```yaml
services:
  cstp-server:
    build: .
    ports:
      - "8100:8100"
    environment:
      - GEMINI_API_KEY=${GEMINI_API_KEY}
      - CSTP_AUTH_TOKENS=${CSTP_AUTH_TOKENS}
      - CHROMA_URL=http://chromadb:8000
    volumes:
      - ./config:/app/config:ro
      - ./guardrails:/app/guardrails:ro
      - decisions_data:/app/decisions
    depends_on:
      chromadb:
        condition: service_healthy

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 10s
      timeout: 5s
      retries: 5
```

### Persistent Volumes

| Volume | Purpose |
|--------|---------|
| `decisions_data` | Recorded decision YAML files |
| `chroma_data` | ChromaDB index data |

### Custom Guardrails

Mount your guardrail YAML files:

```yaml
volumes:
  - ./my-guardrails:/app/custom-guardrails:ro
environment:
  - GUARDRAILS_PATHS=/app/guardrails:/app/custom-guardrails
```

### Rebuilding

```bash
# Rebuild after code changes
docker compose build --no-cache cstp-server

# Restart services
docker compose up -d

# View logs
docker compose logs -f cstp-server
```

---

## Method 2: Local Development

### Step 1: Clone and Set Up Environment

```bash
# Clone
git clone https://github.com/tfatykhov/cognition-agent-decisions.git
cd cognition-agent-decisions

# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate

# Activate (Linux/macOS)
source .venv/bin/activate
```

### Step 2: Install Dependencies

```bash
# Install with pip (including A2A server dependencies)
python -m pip install -e ".[a2a,dev]"

# Install with MCP support
python -m pip install -e ".[a2a,mcp,dev]"

# Or with uv (faster)
pip install uv
uv pip install -e ".[a2a,mcp,dev]"
```

**Dependency groups:**

- **Core:** `pyyaml`, `chromadb`, `rank-bm25`
- **`[a2a]`:** `fastapi`, `uvicorn`, `httpx`, `python-multipart`
- **`[mcp]`:** `mcp` (Model Context Protocol SDK)
- **`[dev]`:** `pytest`, `pytest-asyncio`, `pytest-cov`, `mypy`, `ruff`

### Step 3: Start ChromaDB

You need ChromaDB running independently:

```bash
# Option A: Docker
docker run -d --name chromadb -p 8000:8000 chromadb/chroma:latest

# Option B: Python (in-process)
pip install chromadb
chroma run --host 0.0.0.0 --port 8000
```

### Step 4: Configure Environment

```bash
# Create .env file
cp .env.example .env

# Set required variables
$env:GEMINI_API_KEY = "your_gemini_api_key"
$env:CSTP_AUTH_TOKENS = "myagent:mysecrettoken"
$env:CHROMA_URL = "http://localhost:8000"
```

### Step 5: Start the CSTP Server

```bash
# Using the package script
cstp-server --config config/server.yaml

# Or directly with Python
python -m uvicorn a2a.server:app --host 0.0.0.0 --port 8100

# Or with the entry point
python a2a/server.py --config config/server.yaml --port 8100
```

### Step 6: Verify

```bash
# Health check
curl http://localhost:8100/health

# Agent card
curl http://localhost:8100/.well-known/agent.json

# Query decisions (requires auth)
curl -X POST http://localhost:8100/cstp `
  -H "Authorization: Bearer myagent:mysecrettoken" `
  -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"cstp.queryDecisions","params":{"query":"test"},"id":"1"}'
```

### Step 7: Run Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=src/cognition_engines --cov=a2a --cov-report=term-missing

# Run specific test module
python -m pytest tests/test_guardrails.py -v

# Type checking
python -m mypy src/ a2a/ --ignore-missing-imports

# Linting
python -m ruff check src/ a2a/
```

---

## Method 3: Integration as Library

Use Cognition Engines directly in your Python agent without the HTTP server.

### Install

```bash
pip install cognition-engines
# Or from source:
pip install -e /path/to/cognition-agent-decisions
```

### Usage

```python
from cognition_engines.accelerators.semantic_index import get_index
from cognition_engines.guardrails.engine import get_engine, load_default_guardrails
from cognition_engines.patterns.detector import PatternDetector

# --- Semantic Index ---
index = get_index()
index.index_decisions([{
    "title": "Use Redis for caching",
    "category": "architecture",
    "confidence": 0.85,
    "decision": "Chose Redis over Memcached for caching layer",
}])

results = index.query("caching solution", n_results=5)

# --- Guardrails ---
load_default_guardrails()
engine = get_engine()
allowed, results = engine.check({
    "category": "deployment",
    "stakes": "high",
    "affects_production": True,
    "code_review_completed": True,
})

# --- Pattern Detection ---
detector = PatternDetector()
detector.load_from_directory("decisions/")
report = detector.full_report()
```

---

## Method 4: OpenClaw Skill

If using the [OpenClaw](https://openclaw.ai) agent framework:

```bash
# Copy the skill into your OpenClaw workspace
cp -r skills/cognition-engines /path/to/openclaw/workspace/skills/

# Copy the CLI client
cp scripts/cstp.py /path/to/openclaw/workspace/scripts/

# Configure credentials
echo 'CSTP_URL=http://your-server:8100' >> /path/to/openclaw/workspace/.secrets/cstp.env
echo 'CSTP_TOKEN=your-token' >> /path/to/openclaw/workspace/.secrets/cstp.env
```

The skill provides a `SKILL.md` with decision workflow instructions, and `cstp.py` gives the agent CLI access to query, check, record, and review decisions.

---

## Method 5: MCP Quick Start

Connect any MCP-compliant agent to CSTP decision intelligence. The MCP server exposes 7 tools (`query_decisions`, `check_action`, `log_decision`, `review_outcome`, `get_stats`, `get_decision`, `get_reason_stats`) via two transports.

### Streamable HTTP (Remote)

The CSTP server exposes MCP at `/mcp` on the same port (8100):

```bash
# Claude Code
claude mcp add --transport http cstp-decisions http://your-server:8100/mcp

# Any MCP client — point to:
http://your-server:8100/mcp
```

### stdio (Local / Docker)

```bash
# Via Docker (recommended — container has all deps)
docker exec -i cstp python -m a2a.mcp_server

# Local development
pip install -e ".[mcp]"
export CHROMA_URL=http://localhost:8000
export GEMINI_API_KEY=your-key
python -m a2a.mcp_server
```

### Claude Desktop

Add to `claude_desktop_config.json`:

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

> See [MCP Integration Guide](/guide/mcp-integration) for full details, schemas, and examples.

---

## Troubleshooting

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| `GEMINI_API_KEY not found` | Missing API key | Set `GEMINI_API_KEY` in `.env` or environment |
| `ChromaDB connection refused` | ChromaDB not running | Start ChromaDB with Docker or `chroma run` |
| `401 Unauthorized` | Invalid or missing token | Check `CSTP_AUTH_TOKENS` format: `agent:token` |
| `ModuleNotFoundError: cognition_engines` | Package not installed | Run `pip install -e .` |
| `Docker build fails at uv` | Build tools missing | The Dockerfile includes `gcc`/`g++` — ensure Docker build doesn't cache stale layers |

### Port Conflicts

Default ports:

| Service | Default Port | Environment Variable |
|---------|-------------|---------------------|
| CSTP Server | 8100 | `CSTP_PORT` |
| ChromaDB | 8000 | `CHROMA_URL` (full URL) |
| Dashboard | 5001 | `DASHBOARD_PORT` |

Override with environment variables:

```bash
$env:CSTP_PORT = "9100"
$env:CHROMA_URL = "http://localhost:9000"
```
