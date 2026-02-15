"""JSONL persistence for graph edges.

Provides load/save utilities for storing graph edges as
newline-delimited JSON (one edge per line).
"""

import json
import logging
from pathlib import Path

from . import GraphEdge

logger = logging.getLogger(__name__)


def save_edges_to_jsonl(edges: list[GraphEdge], path: Path) -> None:
    """Write all edges to a JSONL file (full rewrite).

    Args:
        edges: Edges to persist.
        path: File path for the JSONL file.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for edge in edges:
            line = json.dumps(
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
            f.write(line + "\n")


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
