"""Agent Card model for A2A discovery.

The Agent Card is served at /.well-known/agent.json and describes
the agent's capabilities, authentication requirements, and contact info.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CstpCapability:
    """CSTP protocol capability declaration."""

    version: str = "1.0"
    methods: tuple[str, ...] = (
        "cstp.queryDecisions",
        "cstp.checkGuardrails",
    )


@dataclass(frozen=True, slots=True)
class AgentCapabilities:
    """Agent capability declarations."""

    cstp: CstpCapability = field(default_factory=CstpCapability)


@dataclass(frozen=True, slots=True)
class AuthenticationScheme:
    """Authentication scheme declaration."""

    schemes: tuple[str, ...] = ("bearer",)


@dataclass(frozen=True, slots=True)
class AgentCard:
    """A2A Agent Card for discovery.

    Served at GET /.well-known/agent.json to allow other agents
    to discover this agent's capabilities.

    Attributes:
        name: Agent identifier.
        description: Human-readable description.
        version: Agent version string.
        url: Base URL for the agent's API.
        capabilities: Supported protocol capabilities.
        authentication: Required authentication schemes.
        contact: Optional contact email.
    """

    name: str
    description: str
    version: str
    url: str
    capabilities: AgentCapabilities = field(default_factory=AgentCapabilities)
    authentication: AuthenticationScheme = field(default_factory=AuthenticationScheme)
    contact: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "url": self.url,
            "capabilities": {
                "cstp": {
                    "version": self.capabilities.cstp.version,
                    "methods": list(self.capabilities.cstp.methods),
                }
            },
            "authentication": {
                "schemes": list(self.authentication.schemes),
            },
        }
        if self.contact:
            result["contact"] = self.contact
        return result
