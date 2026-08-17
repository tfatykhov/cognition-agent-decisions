"""JSONL persistence for graph edges.

Provides load/save utilities for storing graph edges as
newline-delimited JSON (one edge per line).
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from . import GraphEdge

logger = logging.getLogger(__name__)


def _edge_to_json(edge: GraphEdge) -> str:
    """Serialize one edge to a single JSONL line (no trailing newline)."""
    return json.dumps(
        {
            "source_id": edge.source_id,
            "target_id": edge.target_id,
            "edge_type": edge.edge_type,
            "weight": edge.weight,
            "created_at": edge.created_at,
            "created_by": edge.created_by,
            "context": edge.context,
        },
        ensure_ascii=False,
    )


def save_edges_to_jsonl(edges: list[GraphEdge], path: Path) -> None:
    """Atomically write all edges to a JSONL file (full rewrite).

    Writes to a temporary file in the destination directory, fsyncs it, then
    `os.replace()`s it over the target. `os.replace` is atomic on POSIX and on
    Windows, so a reader sees either the complete previous file or the complete
    new one.

    Opening the destination with mode "w" instead would truncate it before the
    first byte is written: a crash, OOM-kill, or full disk partway through would
    leave a truncated file and destroy every previously persisted edge, not just
    the one being written.

    Args:
        edges: Edges to persist.
        path: File path for the JSONL file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    # Same directory as the target: os.replace is only atomic within a filesystem.
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            for edge in edges:
                f.write(_edge_to_json(edge) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def append_edge_to_jsonl(edge: GraphEdge, path: Path) -> None:
    """Append a single edge to a JSONL file.

    Args:
        edge: Edge to append.
        path: File path for the JSONL file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(_edge_to_json(edge) + "\n")


def load_edges_from_jsonl(path: Path) -> list[GraphEdge]:
    """Load edges from a JSONL file.

    Skips invalid lines with a warning.

    Args:
        path: File path for the JSONL file.

    Returns:
        List of parsed GraphEdge objects.
    """
    edges: list[GraphEdge] = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
                edges.append(
                    GraphEdge(
                        source_id=data["source_id"],
                        target_id=data["target_id"],
                        edge_type=data["edge_type"],
                        weight=float(data.get("weight", 1.0)),
                        created_at=data.get("created_at"),
                        created_by=data.get("created_by"),
                        context=data.get("context"),
                    )
                )
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skipping invalid edge at line %d: %s", line_num, e)
    return edges
