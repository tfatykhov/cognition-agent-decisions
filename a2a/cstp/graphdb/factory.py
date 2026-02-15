"""Factory for graph store backends.

Provides singleton management and test injection for GraphStore instances.
"""

import os

from . import GraphStore

_store: GraphStore | None = None


def create_graph_store() -> GraphStore:
    """Create a GraphStore based on GRAPH_BACKEND env var.

    Supported values:
        - "networkx" (default): NetworkX with JSONL persistence.
        - "memory": In-memory store for testing.
    """
    backend = os.getenv("GRAPH_BACKEND", "networkx")
    match backend:
        case "networkx":
            from .networkx_store import NetworkXGraphStore

            return NetworkXGraphStore()
        case "memory":
            from .memory import MemoryGraphStore

            return MemoryGraphStore()
        case _:
            msg = f"Unknown graph backend: {backend}"
            raise ValueError(msg)


def get_graph_store() -> GraphStore:
    """Get or create the singleton GraphStore."""
    global _store
    if _store is None:
        _store = create_graph_store()
    return _store


def set_graph_store(store: GraphStore | None) -> None:
    """Set the GraphStore instance (for testing)."""
    global _store
    _store = store
