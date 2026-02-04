"""A2A/CSTP Server Package.

Cognition State Transfer Protocol implementation for cognition-agent-decisions.
Provides HTTP API for decision queries and guardrail checks.
"""

from .server import create_app, run_server

__all__ = ["create_app", "run_server"]
__version__ = "0.7.0"
