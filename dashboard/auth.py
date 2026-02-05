"""Basic authentication for Flask routes."""
from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import Response, request

from .config import Config


def check_auth(username: str, password: str, config: Config) -> bool:
    """Validate credentials against config.
    
    Args:
        username: Provided username
        password: Provided password
        config: Config instance with expected credentials
        
    Returns:
        True if credentials match
    """
    return (
        username == config.dashboard_user
        and password == config.dashboard_pass
    )


def authenticate() -> Response:
    """Return 401 response requesting authentication."""
    return Response(
        "Authentication required",
        401,
        {"WWW-Authenticate": 'Basic realm="CSTP Dashboard"'},
    )


def requires_auth(config: Config) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator factory for Basic Auth protection.
    
    Args:
        config: Config instance with credentials
        
    Returns:
        Decorator that protects routes with Basic Auth
        
    Example:
        auth = requires_auth(config)
        
        @app.route("/protected")
        @auth
        def protected_route():
            return "secret"
    """
    def decorator(f: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(f)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            auth = request.authorization
            if not auth or not check_auth(auth.username, auth.password, config):
                return authenticate()
            return f(*args, **kwargs)
        return decorated
    return decorator
