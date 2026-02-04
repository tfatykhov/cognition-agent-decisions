"""Server configuration management.

Loads configuration from YAML file and environment variables.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import os
import yaml


@dataclass(slots=True)
class AuthToken:
    """Authentication token configuration.

    Attributes:
        agent: Agent identifier.
        token: Bearer token value.
    """

    agent: str
    token: str


@dataclass(slots=True)
class AuthConfig:
    """Authentication configuration.

    Attributes:
        enabled: Whether authentication is required.
        tokens: List of valid tokens.
    """

    enabled: bool = True
    tokens: list[AuthToken] = field(default_factory=list)

    def validate_token(self, token: str) -> str | None:
        """Validate a bearer token.

        Uses constant-time comparison to prevent timing attacks.

        Args:
            token: Bearer token to validate.

        Returns:
            Agent ID if valid, None if invalid.
        """
        import secrets

        for auth_token in self.tokens:
            if secrets.compare_digest(auth_token.token, token):
                return auth_token.agent
        return None


@dataclass(slots=True)
class AgentConfig:
    """Agent identity configuration.

    Attributes:
        name: Agent identifier.
        description: Human-readable description.
        version: Agent version string.
        url: Base URL for the agent's API.
        contact: Optional contact email.
    """

    name: str = "cognition-engines"
    description: str = "Decision intelligence for AI agents"
    version: str = "0.7.0"
    url: str = "http://localhost:8100"
    contact: str | None = None


@dataclass(slots=True)
class ServerConfig:
    """HTTP server configuration.

    Attributes:
        host: Bind address.
        port: Bind port.
        cors_origins: Allowed CORS origins.
    """

    host: str = "0.0.0.0"
    port: int = 8100
    cors_origins: list[str] = field(default_factory=lambda: ["*"])


@dataclass(slots=True)
class Config:
    """Complete server configuration.

    Attributes:
        server: HTTP server settings.
        agent: Agent identity settings.
        auth: Authentication settings.
    """

    server: ServerConfig = field(default_factory=ServerConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)

    @classmethod
    def from_yaml(cls, path: Path) -> "Config":
        """Load configuration from YAML file.

        Environment variables in format ${VAR_NAME} are expanded.

        Args:
            path: Path to YAML configuration file.

        Returns:
            Loaded configuration.
        """
        if not path.exists():
            return cls()

        content = path.read_text()
        data = yaml.safe_load(content)
        if not data:
            return cls()

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> "Config":
        """Create config from dictionary."""
        config = cls()

        # Server config
        if "server" in data:
            srv = data["server"]
            config.server = ServerConfig(
                host=srv.get("host", config.server.host),
                port=srv.get("port", config.server.port),
                cors_origins=srv.get("cors_origins", config.server.cors_origins),
            )

        # Agent config
        if "agent" in data:
            agent = data["agent"]
            config.agent = AgentConfig(
                name=agent.get("name", config.agent.name),
                description=agent.get("description", config.agent.description),
                version=agent.get("version", config.agent.version),
                url=agent.get("url", config.agent.url),
                contact=agent.get("contact"),
            )

        # Auth config
        if "auth" in data:
            auth = data["auth"]
            tokens: list[AuthToken] = []
            for token_data in auth.get("tokens", []):
                token_value = token_data.get("token", "")
                # Expand environment variables
                if token_value.startswith("${") and token_value.endswith("}"):
                    env_var = token_value[2:-1]
                    token_value = os.environ.get(env_var, "")
                tokens.append(
                    AuthToken(
                        agent=token_data.get("agent", ""),
                        token=token_value,
                    )
                )
            config.auth = AuthConfig(
                enabled=auth.get("enabled", True),
                tokens=tokens,
            )

        return config
