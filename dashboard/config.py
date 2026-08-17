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

    def security_errors(self) -> list[str]:
        """Config problems that must never reach a running server.

        A subset of `validate()`: only the settings whose absence leaves the
        dashboard open. An unset DASHBOARD_PASS defaults to "" and would
        otherwise admit any request presenting username `admin` and an empty
        password. The SECRET_KEY default is a warning, not an open door, so it
        is deliberately excluded here.
        """
        errors: list[str] = []
        if not self.dashboard_pass:
            errors.append("DASHBOARD_PASS is required")
        return errors


# Global config instance
config = Config()


def enforce_security_config(cfg: Config | None = None) -> None:
    """Abort startup if the configuration would leave the dashboard unauthenticated.

    Called at import time by app.py rather than from main(). The distinction
    matters: the shipped Dockerfile runs `gunicorn app:app`, which imports the
    module and never calls main(), so a guard living only in main() does not run
    in any containerized deployment — which is every deployment we ship.
    """
    errors = (cfg or config).security_errors()
    if errors:
        raise RuntimeError(
            "Refusing to start with an insecure dashboard configuration: "
            + "; ".join(errors)
        )
