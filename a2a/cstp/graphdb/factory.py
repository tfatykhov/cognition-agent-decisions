"""Factory for graph store backends.

Provides singleton management and test injection for GraphStore instances.

Note: ``get_graph_store()`` returns the singleton but does **not** call
``initialize()``. The server lifespan hook (``server.py``) is responsible
for calling ``initialize()`` and ``initialize_graph_from_decisions()``
at startup. Test fixtures should call ``await store.initialize()`` after
injection via ``set_graph_store()``.
"""

import logging
import os

from . import GraphStore

logger = logging.getLogger(__name__)

_store: GraphStore | None = None
_initialized: bool = False


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
    """Get or create the singleton GraphStore.

    The caller must ensure ``await store.initialize()`` has been called
    before performing graph operations. The server lifespan hook handles
    this at startup.
    """
    global _store
    if _store is None:
        _store = create_graph_store()
        if not _initialized:
            logger.warning(
                "GraphStore created but not yet initialized. "
                "Call await store.initialize() before use."
            )
    return _store


def mark_initialized() -> None:
    """Mark the graph store as initialized (called by server lifespan)."""
    global _initialized
    _initialized = True


def set_graph_store(store: GraphStore | None) -> None:
    """Set the GraphStore instance (for testing)."""
    global _store, _initialized
    _store = store
    # Test-injected stores are considered initialized
    _initialized = store is not None
