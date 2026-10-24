"""A2A/CSTP Server Package.

Cognition State Transfer Protocol implementation for cognition-agent-decisions.
Provides HTTP API for decision queries and guardrail checks.
"""

from ._version import __version__
from .server import create_app, run_server

__all__ = ["__version__", "create_app", "run_server"]
