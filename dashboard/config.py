"""Configuration from environment variables."""
from dataclasses import dataclass
from os import environ


@dataclass(frozen=True)
class Config:
    """Dashboard configuration loaded from environment.
    
    All settings are loaded from environment variables with sensible defaults.
    Required variables: CSTP_TOKEN, DASHBOARD_PASS
    """
    
    cstp_url: str = environ.get("CSTP_URL", "http://localhost:9991")
    cstp_token: str = environ.get("CSTP_TOKEN", "")
    dashboard_user: str = environ.get("DASHBOARD_USER", "admin")
    dashboard_pass: str = environ.get("DASHBOARD_PASS", "")
    dashboard_port: int = int(environ.get("DASHBOARD_PORT", "8080"))
    secret_key: str = environ.get("SECRET_KEY", "dev-secret-change-me")
    
    def validate(self) -> list[str]:
        """Validate required config.
        
        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        if not self.cstp_token:
            errors.append("CSTP_TOKEN is required")
        if not self.dashboard_pass:
            errors.append("DASHBOARD_PASS is required")
        if self.secret_key == "dev-secret-change-me":
            errors.append("SECRET_KEY should be changed in production")
        return errors


# Global config instance
config = Config()
