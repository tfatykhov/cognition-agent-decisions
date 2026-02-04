"""CSTP HTTP Server.

FastAPI-based server exposing CSTP methods via JSON-RPC 2.0.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import time

from fastapi import FastAPI, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import AuthManager, set_auth_manager, verify_bearer_token
from .config import Config
from .cstp import CstpDispatcher, get_dispatcher, register_methods
from .models import AgentCard, AgentCapabilities, HealthResponse
from .models.jsonrpc import (
    JsonRpcRequest,
    JsonRpcError,
    JsonRpcResponse,
    PARSE_ERROR,
    INVALID_REQUEST,
)


# Server start time for uptime calculation
_start_time: float = 0.0

# Server configuration
_config: Config | None = None


def get_config() -> Config:
    """Get the server configuration.

    Returns:
        Server configuration.

    Raises:
        RuntimeError: If config not loaded.
    """
    if _config is None:
        raise RuntimeError("Configuration not loaded")
    return _config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Initializes auth manager and dispatcher on startup.
    """
    global _start_time, _config

    _start_time = time.time()

    # Load configuration
    config_path = Path("config/server.yaml")
    _config = Config.from_yaml(config_path)

    # Initialize auth manager
    auth_manager = AuthManager(_config)
    set_auth_manager(auth_manager)

    # Initialize dispatcher with methods
    dispatcher = get_dispatcher()
    register_methods(dispatcher)

    yield

    # Cleanup (if needed)


def create_app(config: Config | None = None) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Optional configuration (uses default if not provided).

    Returns:
        Configured FastAPI application.
    """
    global _config
    if config:
        _config = config

    app = FastAPI(
        title="CSTP Server",
        description="Cognition State Transfer Protocol - Decision Intelligence API",
        version="0.7.0",
        lifespan=lifespan,
    )

    # Configure CORS
    cors_origins = _config.server.cors_origins if _config else ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routes
    _register_routes(app)

    return app


def _register_routes(app: FastAPI) -> None:
    """Register all API routes.

    Args:
        app: FastAPI application.
    """

    @app.get("/health")
    async def health() -> JSONResponse:
        """Health check endpoint."""
        uptime = time.time() - _start_time if _start_time else 0.0
        response = HealthResponse(
            status="healthy",
            version="0.7.0",
            uptime_seconds=uptime,
            timestamp=datetime.now(timezone.utc),
        )
        return JSONResponse(content=response.to_dict())

    @app.get("/.well-known/agent.json")
    async def agent_card() -> JSONResponse:
        """Agent Card endpoint for A2A discovery."""
        config = get_config()
        card = AgentCard(
            name=config.agent.name,
            description=config.agent.description,
            version=config.agent.version,
            url=config.agent.url,
            capabilities=AgentCapabilities(),
            contact=config.agent.contact,
        )
        return JSONResponse(content=card.to_dict())

    @app.post("/cstp")
    async def cstp_endpoint(
        request: Request,
        agent_id: str = Depends(verify_bearer_token),
    ) -> JSONResponse:
        """JSON-RPC 2.0 endpoint for CSTP methods.

        Args:
            request: FastAPI request object.
            agent_id: Authenticated agent ID from bearer token.

        Returns:
            JSON-RPC response.
        """
        # Parse request body
        try:
            body = await request.json()
        except Exception:
            error_response = JsonRpcResponse.failure(
                None,
                JsonRpcError(code=PARSE_ERROR, message="Invalid JSON"),
            )
            return JSONResponse(content=error_response.to_dict())

        # Validate basic structure
        if not isinstance(body, dict):
            error_response = JsonRpcResponse.failure(
                None,
                JsonRpcError(code=INVALID_REQUEST, message="Request must be an object"),
            )
            return JSONResponse(content=error_response.to_dict())

        # Build request object
        rpc_request = JsonRpcRequest(
            method=body.get("method", ""),
            params=body.get("params", {}),
            id=body.get("id"),
            jsonrpc=body.get("jsonrpc", ""),
        )

        # Dispatch to handler
        dispatcher = get_dispatcher()
        response = await dispatcher.dispatch(rpc_request, agent_id)

        return JSONResponse(content=response.to_dict())


def run_server(
    host: str = "0.0.0.0",
    port: int = 8100,
    config_path: str | None = None,
) -> None:
    """Run the CSTP server.

    Args:
        host: Bind address.
        port: Bind port.
        config_path: Path to configuration file.
    """
    import uvicorn

    global _config

    # Load configuration
    if config_path:
        _config = Config.from_yaml(Path(config_path))
    else:
        _config = Config()

    # Override with arguments
    _config.server.host = host
    _config.server.port = port

    app = create_app(_config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CSTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8100, help="Bind port")
    parser.add_argument("--config", help="Path to config file")

    args = parser.parse_args()
    run_server(host=args.host, port=args.port, config_path=args.config)
