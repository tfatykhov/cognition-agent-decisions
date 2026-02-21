FROM python:3.11-slim

WORKDIR /app

# Install MCP client and httpx
RUN pip install --no-cache-dir mcp httpx

COPY agent.py .

CMD ["python", "agent.py"]
