# Docker Deployment Guide

This guide covers deploying the CSTP server using Docker.

## Quick Start

1. **Copy environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your values:**
   ```bash
   # Required
   GEMINI_API_KEY=your_key_here
   CSTP_AUTH_TOKENS=your_agent:your_secret_token
   ```

3. **Start the stack:**
   ```bash
   docker-compose up -d
   ```

4. **Verify it's running:**
   ```bash
   curl http://localhost:8100/health
   # {"status":"healthy"}
   ```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | ✅ | - | API key for embeddings |
| `CSTP_AUTH_TOKENS` | ✅ | - | Auth tokens (format: `agent:token,agent2:token2`) |
| `CSTP_HOST` | ❌ | `0.0.0.0` | Server bind address |
| `CSTP_PORT` | ❌ | `8100` | Server port |
| `CHROMA_URL` | ❌ | `http://chromadb:8000` | ChromaDB endpoint |
| `LOG_LEVEL` | ❌ | `INFO` | Logging level |
| `GUARDRAILS_PATHS` | ❌ | - | Colon-separated guardrail directories |

### Agent Card Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CSTP_AGENT_NAME` | `cognition-engines` | Agent name in discovery |
| `CSTP_AGENT_DESCRIPTION` | - | Agent description |
| `CSTP_AGENT_VERSION` | `0.7.0` | Agent version |
| `CSTP_AGENT_URL` | - | Public URL for agent card |
| `CSTP_AGENT_CONTACT` | - | Contact email |

## Building

### Build the image:
```bash
docker build -t cstp-server:latest .
```

### Build with specific tag:
```bash
docker build -t cstp-server:0.7.0 .
```

## Running

### With docker-compose (recommended):
```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f cstp-server

# Stop
docker-compose down
```

### Standalone (with external ChromaDB):
```bash
docker run -d \
  --name cstp-server \
  -p 8100:8100 \
  -e GEMINI_API_KEY=your_key \
  -e CSTP_AUTH_TOKENS=agent:token \
  -e CHROMA_URL=http://your-chromadb:8000 \
  -v ./guardrails:/app/guardrails:ro \
  cstp-server:latest
```

## Health Checks

The server exposes a `/health` endpoint:

```bash
curl http://localhost:8100/health
```

Response:
```json
{"status": "healthy"}
```

Docker Compose uses this for health checking with:
- Interval: 30 seconds
- Timeout: 10 seconds
- Retries: 3
- Start period: 10 seconds

## Volumes

### Guardrails
Mount your guardrail YAML files:
```yaml
volumes:
  - ./guardrails:/app/guardrails:ro
```

### ChromaDB Data
The compose file creates a named volume for persistence:
```yaml
volumes:
  chroma_data:
    driver: local
```

## Networking

Services communicate on the `cstp-network` bridge network. ChromaDB is accessible at `http://chromadb:8000` from the CSTP server.

## Security

### Non-root user
The container runs as `appuser` (UID 1000) for security.

### Read-only mounts
Configuration and guardrails are mounted read-only (`:ro`).

### No secrets in image
All secrets should be passed via environment variables, never baked into the image.

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs cstp-server

# Common issues:
# - GEMINI_API_KEY not set
# - CSTP_AUTH_TOKENS not set
# - ChromaDB not accessible
```

### Health check failing
```bash
# Check if server is responding
docker exec cstp-server curl -f http://localhost:8100/health

# Check ChromaDB connection
docker exec cstp-server curl -f http://chromadb:8000/api/v1/heartbeat
```

### ChromaDB connection issues
```bash
# Ensure ChromaDB is healthy first
docker-compose logs chromadb

# Wait for ChromaDB to be ready
docker-compose up -d chromadb
sleep 10
docker-compose up -d cstp-server
```

## Production Recommendations

1. **Use specific image tags** (not `latest`)
2. **Set resource limits** in docker-compose
3. **Use external secrets management** (Docker Swarm secrets, Kubernetes, etc.)
4. **Enable TLS** with a reverse proxy (nginx, traefik)
5. **Configure log rotation**
6. **Set up monitoring** (Prometheus metrics endpoint coming soon)

## Example: Production docker-compose

```yaml
version: "3.8"

services:
  cstp-server:
    image: cstp-server:0.7.0
    deploy:
      resources:
        limits:
          cpus: '1'
          memory: 512M
        reservations:
          cpus: '0.5'
          memory: 256M
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
    # ... rest of config
```
