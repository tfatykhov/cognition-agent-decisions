"""Health check response model."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class HealthResponse:
    """Health check response.

    Attributes:
        status: Health status ("healthy" or "unhealthy").
        version: Server version string.
        uptime_seconds: Seconds since server start.
        timestamp: Current server time.
    """

    status: str
    version: str
    uptime_seconds: float
    timestamp: datetime

    def to_dict(self) -> dict[str, str | float]:
        """Convert to JSON-serializable dictionary."""
        return {
            "status": self.status,
            "version": self.version,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp.isoformat(),
        }
