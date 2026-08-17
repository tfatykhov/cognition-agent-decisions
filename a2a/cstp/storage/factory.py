"""Factory for decision store backends.

Provides singleton management and test injection for DecisionStore instances.

Note: ``get_decision_store()`` returns the singleton but does **not** call
``initialize()``. The server lifespan hook is responsible for calling
``initialize()`` at startup. Test fixtures should call
``await store.initialize()`` after injection via ``set_decision_store()``.
"""

import logging
import os
from typing import Any

from . import DecisionStore

logger = logging.getLogger(__name__)

_store: DecisionStore | None = None
_initialized: bool = False


DEFAULT_BACKEND = "sqlite"


def resolve_backend(storage_config: Any | None = None) -> tuple[str, str | None]:
    """Resolve the effective backend name and db path.

    Precedence: environment variable, then loaded YAML config, then the default.
    Env wins so that a container can override a baked-in config file.

    `storage_config` is the `StorageConfig` loaded from `--config` YAML, if any.
    Passing it matters since F058 flipped the default to sqlite: without it a
    deployment whose server.yaml explicitly asks for `backend: yaml` would be
    silently switched to sqlite, because the factory only ever read env vars.
    """
    env_backend = os.getenv("CSTP_STORAGE")
    env_path = os.getenv("CSTP_DB_PATH")

    cfg_backend = getattr(storage_config, "backend", None)
    cfg_path = getattr(storage_config, "db_path", None)

    return (env_backend or cfg_backend or DEFAULT_BACKEND, env_path or cfg_path)


def create_decision_store(storage_config: Any | None = None) -> DecisionStore:
    """Create a DecisionStore from config and CSTP_STORAGE / CSTP_DB_PATH.

    Supported values:
        - "sqlite" (default): SQLite with WAL mode and FTS5.
        - "yaml": YAML filesystem store (legacy, single-user/dev only).
        - "memory": In-memory store for testing.

    The default is sqlite because the vector, graph, and BM25 subsystems all
    assume a queryable, crash-safe decision store underneath them. YAML offers
    no WAL, no FTS5, and no concurrent-write protection, so it warns loudly.
    """
    backend, db_path = resolve_backend(storage_config)
    # if/elif rather than match: static analysers do not treat `case _` as proving
    # exhaustiveness, so a match here reads as a function that can fall through and
    # implicitly return None.
    if backend == "sqlite":
        from .sqlite import SQLiteDecisionStore

        return SQLiteDecisionStore(db_path)

    if backend == "yaml":
        from .yaml_fs import YAMLFileSystemStore

        logger.warning(
            "CSTP_STORAGE=yaml: the flat-file store has no WAL, no FTS5, and no "
            "concurrent-write protection. Suitable for single-user local use only "
            "— set CSTP_STORAGE=sqlite for any shared or multi-agent deployment."
        )
        return YAMLFileSystemStore()

    if backend == "memory":
        from .memory import MemoryDecisionStore

        return MemoryDecisionStore()

    msg = f"Unknown storage backend: {backend}"
    raise ValueError(msg)


def get_decision_store(storage_config: Any | None = None) -> DecisionStore:
    """Get or create the singleton DecisionStore.

    The caller must ensure ``await store.initialize()`` has been called
    before performing storage operations. The server lifespan hook handles
    this at startup and passes the loaded `StorageConfig`; later callers get
    the already-created singleton, so the argument is only read once.
    """
    global _store
    if _store is None:
        _store = create_decision_store(storage_config)
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
