"""Tests for CSTP server infrastructure (F001)."""

import pytest
from fastapi.testclient import TestClient

from a2a.server import create_app
from a2a.config import Config, ServerConfig, AgentConfig, AuthConfig, AuthToken


@pytest.fixture
def config() -> Config:
    """Create test configuration."""
    return Config(
        server=ServerConfig(host="127.0.0.1", port=8100),
        agent=AgentConfig(
            name="test-agent",
            description="Test agent",
            version="0.7.0",
            url="http://localhost:8100",
        ),
        auth=AuthConfig(
            enabled=True,
            tokens=[AuthToken(agent="test", token="test-token")],
        ),
    )


@pytest.fixture
def client(config: Config) -> TestClient:
    """Create test client with configured app."""
    app = create_app(config)
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint should return 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_status(self, client: TestClient) -> None:
        """Health endpoint should return healthy status."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"

    def test_health_returns_version(self, client: TestClient) -> None:
        """Health endpoint should return version."""
        response = client.get("/health")
        data = response.json()
        assert data["version"] == "0.7.0"

    def test_health_returns_uptime(self, client: TestClient) -> None:
        """Health endpoint should return uptime."""
        response = client.get("/health")
        data = response.json()
        assert "uptime_seconds" in data
        assert isinstance(data["uptime_seconds"], (int, float))


class TestAgentCardEndpoint:
    """Tests for GET /.well-known/agent.json."""

    def test_agent_card_returns_200(self, client: TestClient) -> None:
        """Agent card endpoint should return 200."""
        response = client.get("/.well-known/agent.json")
        assert response.status_code == 200

    def test_agent_card_returns_name(self, client: TestClient) -> None:
        """Agent card should include name."""
        response = client.get("/.well-known/agent.json")
        data = response.json()
        assert data["name"] == "test-agent"

    def test_agent_card_returns_version(self, client: TestClient) -> None:
        """Agent card should include version."""
        response = client.get("/.well-known/agent.json")
        data = response.json()
        assert data["version"] == "0.7.0"

    def test_agent_card_returns_capabilities(self, client: TestClient) -> None:
        """Agent card should include CSTP capabilities."""
        response = client.get("/.well-known/agent.json")
        data = response.json()
        assert "capabilities" in data
        assert "cstp" in data["capabilities"]
        assert "methods" in data["capabilities"]["cstp"]

    def test_agent_card_lists_methods(self, client: TestClient) -> None:
        """Agent card should list available CSTP methods."""
        response = client.get("/.well-known/agent.json")
        data = response.json()
        methods = data["capabilities"]["cstp"]["methods"]
        assert "cstp.queryDecisions" in methods
        assert "cstp.checkGuardrails" in methods


class TestCstpEndpointAuth:
    """Tests for POST /cstp authentication."""

    def test_cstp_requires_auth(self, client: TestClient) -> None:
        """CSTP endpoint should require authentication."""
        response = client.post("/cstp", json={"jsonrpc": "2.0", "method": "cstp.queryDecisions"})
        assert response.status_code == 401

    def test_cstp_rejects_invalid_token(self, client: TestClient) -> None:
        """CSTP endpoint should reject invalid tokens."""
        response = client.post(
            "/cstp",
            json={"jsonrpc": "2.0", "method": "cstp.queryDecisions"},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert response.status_code == 401

    def test_cstp_accepts_valid_token(self, client: TestClient) -> None:
        """CSTP endpoint should accept valid tokens."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.queryDecisions",
                "id": "test-1",
                "params": {"query": "test"},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert response.status_code == 200


class TestCstpEndpointJsonRpc:
    """Tests for POST /cstp JSON-RPC handling."""

    def test_cstp_returns_jsonrpc_response(self, client: TestClient) -> None:
        """CSTP endpoint should return JSON-RPC response."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.queryDecisions",
                "id": "test-1",
                "params": {"query": "test"},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert data["jsonrpc"] == "2.0"
        assert data["id"] == "test-1"

    def test_cstp_rejects_invalid_json(self, client: TestClient) -> None:
        """CSTP endpoint should reject invalid JSON."""
        response = client.post(
            "/cstp",
            content="not json",
            headers={
                "Authorization": "Bearer test-token",
                "Content-Type": "application/json",
            },
        )
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32700  # Parse error

    def test_cstp_rejects_unknown_method(self, client: TestClient) -> None:
        """CSTP endpoint should reject unknown methods."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.unknownMethod",
                "id": "test-1",
                "params": {},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601  # Method not found

    def test_cstp_rejects_non_cstp_method(self, client: TestClient) -> None:
        """CSTP endpoint should reject non-CSTP methods."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "other.method",
                "id": "test-1",
                "params": {},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32601


class TestQueryDecisionsStub:
    """Tests for cstp.queryDecisions stub."""

    def test_query_decisions_returns_result(self, client: TestClient) -> None:
        """queryDecisions should return stub result."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.queryDecisions",
                "id": "test-1",
                "params": {"query": "test query"},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "result" in data
        assert data["result"]["query"] == "test query"
        assert "decisions" in data["result"]


class TestCheckGuardrailsStub:
    """Tests for cstp.checkGuardrails stub."""

    def test_check_guardrails_returns_result(self, client: TestClient) -> None:
        """checkGuardrails should return stub result."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.checkGuardrails",
                "id": "test-1",
                "params": {"action": {"description": "test action"}},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "result" in data
        assert data["result"]["allowed"] is True
        assert "violations" in data["result"]
