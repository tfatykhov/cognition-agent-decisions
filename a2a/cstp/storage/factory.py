"""Factory for decision store backends.

Provides singleton management and test injection for DecisionStore instances.

Note: ``get_decision_store()`` returns the singleton but does **not** call
``initialize()``. The server lifespan hook is responsible for calling
``initialize()`` at startup. Test fixtures should call
``await store.initialize()`` after injection via ``set_decision_store()``.
"""

import logging
import os

from . import DecisionStore

logger = logging.getLogger(__name__)

_store: DecisionStore | None = None
_initialized: bool = False


DEFAULT_BACKEND = "sqlite"


def create_decision_store() -> DecisionStore:
    """Create a DecisionStore based on CSTP_STORAGE env var.

    Supported values:
        - "sqlite" (default): SQLite with WAL mode and FTS5.
        - "yaml": YAML filesystem store (legacy, single-user/dev only).
        - "memory": In-memory store for testing.

    The default is sqlite because the vector, graph, and BM25 subsystems all
    assume a queryable, crash-safe decision store underneath them. YAML offers
    no WAL, no FTS5, and no concurrent-write protection, so it warns loudly.
    """
    backend = os.getenv("CSTP_STORAGE", DEFAULT_BACKEND)
    match backend:
        case "sqlite":
            from .sqlite import SQLiteDecisionStore

            return SQLiteDecisionStore()
        case "yaml":
            from .yaml_fs import YAMLFileSystemStore

            logger.warning(
                "CSTP_STORAGE=yaml: the flat-file store has no WAL, no FTS5, and no "
                "concurrent-write protection. Suitable for single-user local use only "
                "— set CSTP_STORAGE=sqlite for any shared or multi-agent deployment."
            )
            return YAMLFileSystemStore()
        case "memory":
            from .memory import MemoryDecisionStore

            return MemoryDecisionStore()
        case _:
            msg = f"Unknown storage backend: {backend}"
            raise ValueError(msg)


def get_decision_store() -> DecisionStore:
    """Get or create the singleton DecisionStore.

    The caller must ensure ``await store.initialize()`` has been called
    before performing storage operations. The server lifespan hook handles
    this at startup.
    """
    global _store
    if _store is None:
        _store = create_decision_store()
        if not _initialized:
            logger.warning(
                "DecisionStore created but not yet initialized. "
                "Call await store.initialize() before use."
            )
    return _store


def mark_initialized() -> None:
    """Mark the decision store as initialized (called by server lifespan)."""
    global _initialized
    _initialized = True


def set_decision_store(store: DecisionStore | None) -> None:
    """Set the DecisionStore instance (for testing)."""
    global _store, _initialized
    _store = store
    # Test-injected stores are considered initialized
    _initialized = store is not None
