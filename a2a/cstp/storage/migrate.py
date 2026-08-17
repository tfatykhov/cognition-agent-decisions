"""Auto-migration from YAML files to SQLite.

On server startup, if CSTP_STORAGE=sqlite and the database is empty,
automatically imports all existing YAML decision files into SQLite.

Can also be run as a CLI command:
    python -m a2a.cstp.storage.migrate [--decisions-dir DIR] [--db-path PATH] [--force]
"""

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

import yaml

from . import DecisionStore

logger = logging.getLogger(__name__)

DECISIONS_PATH = os.getenv("DECISIONS_PATH", "decisions")


def _parse_yaml_decision(yaml_file: Path) -> tuple[str, dict[str, Any]] | None:
    """Parse a YAML decision file and extract decision ID.

    Args:
        yaml_file: Path to a YAML decision file.

    Returns:
        Tuple of (decision_id, data_dict) or None if parsing fails.
    """
    try:
        with open(yaml_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or not isinstance(data, dict):
            return None

        # Extract ID from filename: YYYY-MM-DD-decision-XXXXXXXX.yaml
        filename = yaml_file.stem
        parts = filename.rsplit("-decision-", 1)
        if len(parts) == 2:
            decision_id = parts[1]
        else:
            decision_id = data.get("id", filename)

        # Ensure id is in the data dict
        data["id"] = decision_id

        return decision_id, data

    except Exception:
        logger.debug("Failed to parse %s", yaml_file, exc_info=True)
        return None


async def migrate_yaml_to_store(
    store: DecisionStore,
    decisions_dir: str | None = None,
) -> int:
    """Import all YAML decision files into a DecisionStore.

    Scans the decisions directory for YAML files and inserts each
    into the store via save(). Uses upsert semantics so it's safe
    to re-run (idempotent).

    Args:
        store: Initialized DecisionStore to import into.
        decisions_dir: Path to decisions directory (default: DECISIONS_PATH env).

    Returns:
        Number of decisions successfully imported.
    """
    base = Path(decisions_dir or DECISIONS_PATH)

    if not base.exists():
        logger.info("Decisions directory %s does not exist, nothing to migrate", base)
        return 0

    yaml_files = list(base.rglob("*-decision-*.yaml"))
    if not yaml_files:
        logger.info("No YAML decision files found in %s", base)
        return 0

    imported = 0
    errors = 0

    for yaml_file in yaml_files:
        result = _parse_yaml_decision(yaml_file)
        if result is None:
            errors += 1
            continue

        decision_id, data = result

        try:
            await store.save(decision_id, data)
            imported += 1
        except Exception:
            logger.warning("Failed to import %s", yaml_file, exc_info=True)
            errors += 1

    logger.info(
        "YAML migration complete: %d imported, %d errors, %d total files",
        imported,
        errors,
        len(yaml_files),
    )

    return imported


async def auto_migrate_if_incomplete(
    store: DecisionStore,
    decisions_dir: str | None = None,
) -> int:
    """Auto-migrate YAML decisions into store if any are still missing.

    Called during server startup.

    Resumability matters here. The previous gate was "only run when the store is
    empty", but `migrate_yaml_to_store` commits one record at a time with no
    surrounding transaction. A crash after the first save left a non-empty store,
    so the next startup skipped migration permanently and the remaining YAML
    decisions became invisible to every read path. Comparing the store count to
    the number of YAML files instead means an interrupted run simply resumes; the
    saves are upserts, so re-importing is harmless.

    Note: if some YAML files are unparseable the count can never reach the file
    total, so this re-runs each startup. That is idempotent and logged, and the
    per-file parse warnings say which files are the problem.

    Args:
        store: Initialized DecisionStore to check and populate.
        decisions_dir: Path to decisions directory.

    Returns:
        Number of decisions imported (0 if nothing was missing).
    """
    base = Path(decisions_dir or DECISIONS_PATH)
    if not base.exists():
        logger.info("Decisions directory %s does not exist, nothing to migrate", base)
        return 0

    yaml_files = list(base.rglob("*-decision-*.yaml"))
    if not yaml_files:
        logger.info("No YAML decision files found in %s", base)
        return 0

    try:
        count = await store.count()
    except Exception:
        logger.warning("Could not check store count, skipping auto-migration", exc_info=True)
        return 0

    if count >= len(yaml_files):
        logger.info(
            "Store has %d decisions for %d YAML files, skipping auto-migration",
            count,
            len(yaml_files),
        )
        return 0

    logger.info(
        "Store has %d of %d YAML decisions, running auto-migration...",
        count,
        len(yaml_files),
    )
    return await migrate_yaml_to_store(store, decisions_dir)


# Back-compat alias: the gate is no longer "is the store empty", but callers
# outside this module may still import the old name.
auto_migrate_if_empty = auto_migrate_if_incomplete


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _cli() -> None:
    """Command-line interface for migration."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate YAML decisions to SQLite",
    )
    parser.add_argument(
        "--decisions-dir",
        default=DECISIONS_PATH,
        help="Path to decisions directory (default: %(default)s)",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("CSTP_DB_PATH", "data/decisions.db"),
        help="Path to SQLite database (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force migration even if store already has data",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    from .sqlite import SQLiteDecisionStore

    async def run() -> None:
        store = SQLiteDecisionStore(db_path=args.db_path)
        await store.initialize()

        if args.force:
            count = await migrate_yaml_to_store(store, args.decisions_dir)
        else:
            count = await auto_migrate_if_empty(store, args.decisions_dir)

        await store.close()
        print(f"Done. {count} decisions imported.")

    asyncio.run(run())


if __name__ == "__main__":
    _cli()
