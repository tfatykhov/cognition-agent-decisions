"""Tests for config.py environment variable support."""

import pytest

from a2a.config import Config, _parse_auth_tokens


class TestParseAuthTokens:
    """Tests for _parse_auth_tokens function."""

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        result = _parse_auth_tokens("")
        assert result == []

    def test_single_token(self) -> None:
        """Single agent:token pair is parsed."""
        result = _parse_auth_tokens("emerson:secret123")
        assert len(result) == 1
        assert result[0].agent == "emerson"
        assert result[0].token == "secret123"

    def test_multiple_tokens(self) -> None:
        """Multiple comma-separated pairs are parsed."""
        result = _parse_auth_tokens("agent1:token1,agent2:token2")
        assert len(result) == 2
        assert result[0].agent == "agent1"
        assert result[0].token == "token1"
        assert result[1].agent == "agent2"
        assert result[1].token == "token2"

    def test_whitespace_handling(self) -> None:
        """Whitespace around pairs is stripped."""
        result = _parse_auth_tokens("  agent1:token1 , agent2:token2  ")
        assert len(result) == 2
        assert result[0].agent == "agent1"
        assert result[1].agent == "agent2"

    def test_invalid_format_skipped(self) -> None:
        """Pairs without colon are skipped."""
        result = _parse_auth_tokens("valid:token,invalid")
        assert len(result) == 1
        assert result[0].agent == "valid"

    def test_empty_agent_skipped(self) -> None:
        """Empty agent name is skipped."""
        result = _parse_auth_tokens(":token")
        assert result == []

    def test_empty_token_skipped(self) -> None:
        """Empty token is skipped."""
        result = _parse_auth_tokens("agent:")
        assert result == []


class TestConfigFromEnv:
    """Tests for Config.from_env classmethod."""

    def test_defaults_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default values when no env vars set."""
        # Clear relevant env vars
        for var in [
            "CSTP_HOST",
            "CSTP_PORT",
            "CSTP_AUTH_TOKENS",
            "CSTP_AGENT_NAME",
        ]:
            monkeypatch.delenv(var, raising=False)

        config = Config.from_env()
        assert config.server.host == "0.0.0.0"
        assert config.server.port == 8100
        assert config.agent.name == "cognition-engines"
        assert config.auth.tokens == []

    def test_reads_server_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Server config read from env vars."""
        monkeypatch.setenv("CSTP_HOST", "127.0.0.1")
        monkeypatch.setenv("CSTP_PORT", "9000")

        config = Config.from_env()
        assert config.server.host == "127.0.0.1"
        assert config.server.port == 9000

    def test_reads_agent_config(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Agent config read from env vars."""
        monkeypatch.setenv("CSTP_AGENT_NAME", "test-agent")
        monkeypatch.setenv("CSTP_AGENT_DESCRIPTION", "Test description")
        monkeypatch.setenv("CSTP_AGENT_VERSION", "1.0.0")
        monkeypatch.setenv("CSTP_AGENT_URL", "https://example.com")
        monkeypatch.setenv("CSTP_AGENT_CONTACT", "test@example.com")

        config = Config.from_env()
        assert config.agent.name == "test-agent"
        assert config.agent.description == "Test description"
        assert config.agent.version == "1.0.0"
        assert config.agent.url == "https://example.com"
        assert config.agent.contact == "test@example.com"

    def test_reads_auth_tokens(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Auth tokens parsed from env var."""
        monkeypatch.setenv("CSTP_AUTH_TOKENS", "agent1:secret1,agent2:secret2")

        config = Config.from_env()
        assert len(config.auth.tokens) == 2
        assert config.auth.tokens[0].agent == "agent1"
        assert config.auth.tokens[0].token == "secret1"
        assert config.auth.tokens[1].agent == "agent2"
