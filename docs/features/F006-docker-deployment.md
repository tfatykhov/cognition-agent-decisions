# F006: Docker Deployment Support

| Field | Value |
|-------|-------|
| Feature ID | F006 |
| Status | Implemented |
| Priority | P2 |
| Depends On | F001 (Server Infrastructure) |
| Blocks | None |
| Decision | 944b8647 |

---

## Summary

Add Docker support for running the CSTP server as a containerized service, including Dockerfile, docker-compose.yml, and example environment configuration.

## Goals

1. Production-ready Dockerfile with multi-stage build
2. docker-compose.yml for local development
3. Example environment file with all required variables
4. Health check integration
5. Documentation for deployment

## Non-Goals

- Kubernetes manifests (future)
- Helm charts (future)
- CI/CD pipeline integration (separate task)

---

## Implementation Plan

### Phase 1: Core Docker Files

#### 1.1 Dockerfile

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# --- Builder stage ---
FROM base AS builder

# Install uv for fast dependency resolution
RUN pip install uv

# Copy dependency files
COPY pyproject.toml ./

# Install dependencies
RUN uv pip install --system -e ".[a2a]"

# --- Runtime stage ---
FROM base AS runtime

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY . .

# Create non-root user
RUN useradd --create-home --shell /bin/bash appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8100

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8100/health || exit 1

# Default command
CMD ["python", "-m", "a2a.server", "--host", "0.0.0.0", "--port", "8100"]
```

#### 1.2 docker-compose.yml

```yaml
version: "3.8"

services:
  cstp-server:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: cstp-server
    ports:
      - "8100:8100"
    env_file:
      - .env
    environment:
      - CHROMA_URL=http://chromadb:8000
    volumes:
      - ./config:/app/config:ro
      - ./guardrails:/app/guardrails:ro
    depends_on:
      chromadb:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8100/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

  chromadb:
    image: chromadb/chroma:latest
    container_name: chromadb
    ports:
      - "8000:8000"
    volumes:
      - chroma_data:/chroma/chroma
    environment:
      - ANONYMIZED_TELEMETRY=false
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/heartbeat"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped

volumes:
  chroma_data:
```

#### 1.3 .env.example

```bash
# =============================================================================
# CSTP Server Configuration
# =============================================================================
# Copy this file to .env and fill in the values

# --- Required ---

# Gemini API key for embeddings (text-embedding-004)
GEMINI_API_KEY=your_gemini_api_key_here

# --- Server Configuration ---

# Server bind address (default: 0.0.0.0)
CSTP_HOST=0.0.0.0

# Server port (default: 8100)
CSTP_PORT=8100

# --- ChromaDB Configuration ---

# ChromaDB URL (default: http://chromadb:8000)
CHROMA_URL=http://chromadb:8000

# ChromaDB auth token (optional)
# CHROMA_TOKEN=

# --- Authentication ---

# Comma-separated list of agent:token pairs for authentication
# Format: agent1:token1,agent2:token2
CSTP_AUTH_TOKENS=emerson:your_secret_token_here

# --- Guardrails Configuration ---

# Colon-separated paths to guardrail directories (optional)
# GUARDRAILS_PATHS=/app/guardrails:/custom/guardrails

# --- Logging ---

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO

# --- Optional: Agent Card ---

# Agent name for discovery
CSTP_AGENT_NAME=cognition-engines

# Agent description
CSTP_AGENT_DESCRIPTION=Decision Intelligence Service

# Agent URL (for agent card)
CSTP_AGENT_URL=http://localhost:8100
```

### Phase 2: Configuration Updates

#### 2.1 Update config.py to read from environment

```python
# Support environment variable overrides
import os

def from_env() -> Config:
    """Create config from environment variables."""
    return Config(
        server=ServerConfig(
            host=os.getenv("CSTP_HOST", "0.0.0.0"),
            port=int(os.getenv("CSTP_PORT", "8100")),
        ),
        agent=AgentConfig(
            name=os.getenv("CSTP_AGENT_NAME", "cognition-engines"),
            description=os.getenv("CSTP_AGENT_DESCRIPTION", "Decision Intelligence"),
            version="0.7.0",
            url=os.getenv("CSTP_AGENT_URL", "http://localhost:8100"),
        ),
        auth=AuthConfig(
            enabled=True,
            tokens=_parse_auth_tokens(os.getenv("CSTP_AUTH_TOKENS", "")),
        ),
    )

def _parse_auth_tokens(tokens_str: str) -> list[AuthToken]:
    """Parse CSTP_AUTH_TOKENS env var."""
    tokens = []
    for pair in tokens_str.split(","):
        if ":" in pair:
            agent, token = pair.split(":", 1)
            tokens.append(AuthToken(agent=agent.strip(), token=token.strip()))
    return tokens
```

#### 2.2 Update server.py entrypoint

```python
# Add CLI support for Docker
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="CSTP Server")
    parser.add_argument("--host", default=os.getenv("CSTP_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("CSTP_PORT", "8100")))
    parser.add_argument("--config", help="Path to config YAML (overrides env)")
    
    args = parser.parse_args()
    run_server(host=args.host, port=args.port, config_path=args.config)
```

### Phase 3: Documentation

#### 3.1 Update README.md

Add "Docker Deployment" section:
- Quick start with docker-compose
- Environment variable reference
- Production deployment tips
- Health check endpoints

#### 3.2 Create docs/DOCKER.md

Detailed Docker deployment guide:
- Building the image
- Running with docker-compose
- Running standalone
- Connecting to external ChromaDB
- Security considerations
- Monitoring and logging

---

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `Dockerfile` | Create | Multi-stage production build |
| `docker-compose.yml` | Create | Local dev with ChromaDB |
| `.env.example` | Create | Example environment file |
| `.dockerignore` | Create | Exclude unnecessary files |
| `a2a/config.py` | Modify | Add env var support |
| `a2a/server.py` | Modify | Add CLI entrypoint |
| `README.md` | Modify | Add Docker quick start |
| `docs/DOCKER.md` | Create | Full deployment guide |

---

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ | - | Gemini API key for embeddings |
| `CSTP_HOST` | ❌ | `0.0.0.0` | Server bind address |
| `CSTP_PORT` | ❌ | `8100` | Server port |
| `CHROMA_URL` | ❌ | `http://chromadb:8000` | ChromaDB endpoint |
| `CHROMA_TOKEN` | ❌ | - | ChromaDB auth token |
| `CSTP_AUTH_TOKENS` | ✅ | - | Agent authentication tokens |
| `GUARDRAILS_PATHS` | ❌ | - | Custom guardrail directories |
| `LOG_LEVEL` | ❌ | `INFO` | Logging verbosity |
| `CSTP_AGENT_NAME` | ❌ | `cognition-engines` | Agent card name |
| `CSTP_AGENT_DESCRIPTION` | ❌ | - | Agent card description |
| `CSTP_AGENT_URL` | ❌ | - | Agent card URL |

---

## Acceptance Criteria

1. `docker build .` succeeds
2. `docker-compose up` starts server + ChromaDB
3. Health check passes at `/health`
4. Authentication works with env-configured tokens
5. Guardrails load from mounted volume
6. Queries work against ChromaDB
7. Graceful shutdown on SIGTERM

---

## Estimated Effort

- **Phase 1 (Docker files)**: 1-2 hours
- **Phase 2 (Config updates)**: 1 hour
- **Phase 3 (Documentation)**: 1 hour

**Total**: ~4 hours
