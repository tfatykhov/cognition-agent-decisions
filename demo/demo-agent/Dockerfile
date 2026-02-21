FROM python:3.11-slim

WORKDIR /app

# Install MCP client and httpx
RUN pip install --no-cache-dir "mcp>=1.0,<2.0" "httpx>=0.27,<1.0"

COPY agent.py .

CMD ["python", "agent.py"]
