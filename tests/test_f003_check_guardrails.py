"""Tests for F003: cstp.checkGuardrails implementation."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from a2a.auth import AuthManager, set_auth_manager
from a2a.config import AgentConfig, AuthConfig, AuthToken, Config, ServerConfig
from a2a.cstp import get_dispatcher, register_methods
from a2a.cstp.guardrails_service import EvaluationResult, GuardrailResult
from a2a.cstp.models import (
    ActionContext,
    AgentInfo,
    CheckGuardrailsRequest,
    CheckGuardrailsResponse,
    GuardrailViolation,
)
from a2a.server import create_app


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

    auth_manager = AuthManager(config)
    set_auth_manager(auth_manager)
    app.state.auth_manager = auth_manager
    app.state.config = config
    app.state.start_time = 0.0

    dispatcher = get_dispatcher()
    register_methods(dispatcher)
    app.state.dispatcher = dispatcher

    return TestClient(app)


class TestActionContext:
    """Tests for ActionContext model."""

    def test_from_dict_minimal(self) -> None:
        """Minimal action should parse."""
        data = {"description": "Deploy to production"}
        ctx = ActionContext.from_dict(data)
        assert ctx.description == "Deploy to production"
        assert ctx.stakes == "medium"
        assert ctx.category is None

    def test_from_dict_full(self) -> None:
        """Full action should parse."""
        data = {
            "description": "Deploy auth service",
            "category": "architecture",
            "stakes": "high",
            "confidence": 0.85,
            "context": {"affectsProduction": True},
        }
        ctx = ActionContext.from_dict(data)
        assert ctx.description == "Deploy auth service"
        assert ctx.category == "architecture"
        assert ctx.stakes == "high"
        assert ctx.confidence == 0.85
        assert ctx.context["affectsProduction"] is True

    def test_from_dict_missing_description(self) -> None:
        """Missing description should raise."""
        with pytest.raises(ValueError, match="Missing required field: action.description"):
            ActionContext.from_dict({})


class TestAgentInfo:
    """Tests for AgentInfo model."""

    def test_from_dict_none(self) -> None:
        """None should create empty AgentInfo."""
        info = AgentInfo.from_dict(None)
        assert info.id is None
        assert info.url is None

    def test_from_dict_full(self) -> None:
        """Full dict should parse."""
        data = {"id": "emerson", "url": "https://emerson.example.com"}
        info = AgentInfo.from_dict(data)
        assert info.id == "emerson"
        assert info.url == "https://emerson.example.com"


class TestCheckGuardrailsRequest:
    """Tests for CheckGuardrailsRequest parsing."""

    def test_from_params_minimal(self) -> None:
        """Minimal params should parse."""
        params = {"action": {"description": "Test action"}}
        req = CheckGuardrailsRequest.from_params(params)
        assert req.action.description == "Test action"
        assert req.agent.id is None

    def test_from_params_full(self) -> None:
        """Full params should parse."""
        params = {
            "action": {
                "description": "Deploy to production",
                "category": "architecture",
                "stakes": "high",
            },
            "agent": {"id": "emerson", "url": "https://emerson.example.com"},
        }
        req = CheckGuardrailsRequest.from_params(params)
        assert req.action.description == "Deploy to production"
        assert req.action.category == "architecture"
        assert req.agent.id == "emerson"

    def test_from_params_missing_action(self) -> None:
        """Missing action should raise."""
        with pytest.raises(ValueError, match="Missing required parameter: action"):
            CheckGuardrailsRequest.from_params({})


class TestGuardrailViolation:
    """Tests for GuardrailViolation serialization."""

    def test_to_dict_minimal(self) -> None:
        """Minimal violation should serialize."""
        v = GuardrailViolation(
            guardrail_id="test-rule",
            name="Test Rule",
            message="Violated test rule",
            severity="block",
        )
        data = v.to_dict()
        assert data["guardrailId"] == "test-rule"
        assert data["name"] == "Test Rule"
        assert data["message"] == "Violated test rule"
        assert data["severity"] == "block"
        assert "suggestion" not in data

    def test_to_dict_with_suggestion(self) -> None:
        """Violation with suggestion should serialize."""
        v = GuardrailViolation(
            guardrail_id="test-rule",
            name="Test Rule",
            message="Violated",
            severity="warn",
            suggestion="Fix this issue",
        )
        data = v.to_dict()
        assert data["suggestion"] == "Fix this issue"


class TestCheckGuardrailsResponse:
    """Tests for CheckGuardrailsResponse serialization."""

    def test_to_dict_allowed(self) -> None:
        """Allowed response should serialize."""
        response = CheckGuardrailsResponse(
            allowed=True,
            violations=[],
            warnings=[],
            evaluated=5,
            evaluated_at=datetime(2026, 2, 4, 21, 0, 0, tzinfo=UTC),
            agent="test-agent",
        )
        data = response.to_dict()
        assert data["allowed"] is True
        assert data["violations"] == []
        assert data["warnings"] == []
        assert data["evaluated"] == 5
        assert "2026-02-04" in data["evaluatedAt"]
        assert data["agent"] == "test-agent"

    def test_to_dict_blocked(self) -> None:
        """Blocked response should serialize."""
        response = CheckGuardrailsResponse(
            allowed=False,
            violations=[
                GuardrailViolation(
                    guardrail_id="no-prod",
                    name="No Production",
                    message="Production blocked",
                    severity="block",
                )
            ],
            warnings=[],
            evaluated=5,
            evaluated_at=datetime(2026, 2, 4, 21, 0, 0, tzinfo=UTC),
            agent="test-agent",
        )
        data = response.to_dict()
        assert data["allowed"] is False
        assert len(data["violations"]) == 1
        assert data["violations"][0]["guardrailId"] == "no-prod"


class TestCheckGuardrailsEndpoint:
    """Integration tests for cstp.checkGuardrails endpoint."""

    def test_missing_action_param(self, client: TestClient) -> None:
        """Missing action param should return error."""
        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.checkGuardrails",
                "id": "test-1",
                "params": {},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == -32602

    @patch("a2a.cstp.dispatcher.evaluate_guardrails")
    @patch("a2a.cstp.dispatcher.log_guardrail_check")
    def test_check_returns_allowed(
        self,
        mock_log: AsyncMock,
        mock_eval: AsyncMock,
        client: TestClient,
    ) -> None:
        """Valid check should return allowed."""
        mock_eval.return_value = EvaluationResult(
            allowed=True,
            violations=[],
            warnings=[],
            evaluated=5,
        )

        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.checkGuardrails",
                "id": "test-1",
                "params": {
                    "action": {
                        "description": "Deploy to staging",
                        "category": "architecture",
                        "stakes": "medium",
                    }
                },
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()

        assert "result" in data
        assert data["result"]["allowed"] is True
        assert data["result"]["evaluated"] == 5
        mock_log.assert_called_once()

    @patch("a2a.cstp.dispatcher.evaluate_guardrails")
    @patch("a2a.cstp.dispatcher.log_guardrail_check")
    def test_check_returns_blocked(
        self,
        mock_log: AsyncMock,
        mock_eval: AsyncMock,
        client: TestClient,
    ) -> None:
        """Blocking violation should return blocked."""
        mock_eval.return_value = EvaluationResult(
            allowed=False,
            violations=[
                GuardrailResult(
                    guardrail_id="no-prod-without-review",
                    name="Production Requires Review",
                    message="Code review required",
                    severity="block",
                )
            ],
            warnings=[],
            evaluated=5,
        )

        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.checkGuardrails",
                "id": "test-1",
                "params": {
                    "action": {
                        "description": "Deploy to production",
                        "category": "architecture",
                        "stakes": "high",
                        "context": {"affectsProduction": True},
                    }
                },
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()

        assert "result" in data
        assert data["result"]["allowed"] is False
        assert len(data["result"]["violations"]) == 1
        assert data["result"]["violations"][0]["guardrailId"] == "no-prod-without-review"

    @patch("a2a.cstp.dispatcher.evaluate_guardrails")
    @patch("a2a.cstp.dispatcher.log_guardrail_check")
    def test_check_with_warnings(
        self,
        mock_log: AsyncMock,
        mock_eval: AsyncMock,
        client: TestClient,
    ) -> None:
        """Warnings should be included but not block."""
        mock_eval.return_value = EvaluationResult(
            allowed=True,
            violations=[],
            warnings=[
                GuardrailResult(
                    guardrail_id="prefer-staged",
                    name="Prefer Staged Rollout",
                    message="Consider staged rollout",
                    severity="warn",
                )
            ],
            evaluated=5,
        )

        response = client.post(
            "/cstp",
            json={
                "jsonrpc": "2.0",
                "method": "cstp.checkGuardrails",
                "id": "test-1",
                "params": {"action": {"description": "Deploy"}},
            },
            headers={"Authorization": "Bearer test-token"},
        )
        data = response.json()

        assert data["result"]["allowed"] is True
        assert len(data["result"]["warnings"]) == 1
        assert data["result"]["warnings"][0]["severity"] == "warn"
