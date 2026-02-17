"""SQLite storage backend for decisions.

Uses WAL mode for concurrent reads, FTS5 for keyword search,
and normalized tables for tags, reasons, bridge, and deliberation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sqlite3
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import DecisionStore, ListQuery, ListResult, StatsQuery, StatsResult

logger = logging.getLogger(__name__)

SCHEMA_SQL = """\
-- Core decisions table
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    confidence REAL NOT NULL,
    category TEXT NOT NULL,
    stakes TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    context TEXT,
    recorded_by TEXT,
    project TEXT,
    feature TEXT,
    pr INTEGER,
    pattern TEXT,
    outcome TEXT,
    outcome_result TEXT,
    outcome_lessons TEXT,
    outcome_notes TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT
);

-- Tags (many-to-many)
CREATE TABLE IF NOT EXISTS decision_tags (
    decision_id TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    PRIMARY KEY (decision_id, tag)
);

-- Reasons supporting each decision
CREATE TABLE IF NOT EXISTS decision_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT NOT NULL REFERENCES decisions(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    text TEXT NOT NULL,
    strength REAL DEFAULT 0.8
);

-- Minsky bridge-definitions (one per decision)
CREATE TABLE IF NOT EXISTS decision_bridge (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(id) ON DELETE CASCADE,
    structure TEXT,
    function TEXT,
    tolerance TEXT,
    enforcement TEXT,
    prevention TEXT
);

-- Deliberation traces (one per decision)
CREATE TABLE IF NOT EXISTS decision_deliberation (
    decision_id TEXT PRIMARY KEY REFERENCES decisions(id) ON DELETE CASCADE,
    inputs_json TEXT,
    steps_json TEXT,
    total_duration_ms INTEGER
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_decisions_created_at ON decisions(created_at);
CREATE INDEX IF NOT EXISTS idx_decisions_category ON decisions(category);
CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status);
CREATE INDEX IF NOT EXISTS idx_decisions_stakes ON decisions(stakes);
CREATE INDEX IF NOT EXISTS idx_decisions_recorded_by ON decisions(recorded_by);
CREATE INDEX IF NOT EXISTS idx_decisions_project ON decisions(project);
CREATE INDEX IF NOT EXISTS idx_decision_tags_tag ON decision_tags(tag);

-- FTS5 virtual table for keyword search
CREATE VIRTUAL TABLE IF NOT EXISTS decisions_fts USING fts5(
    id UNINDEXED,
    decision,
    context,
    pattern,
    content=decisions,
    content_rowid=rowid
);

-- Triggers to keep FTS5 in sync with decisions table
CREATE TRIGGER IF NOT EXISTS decisions_ai AFTER INSERT ON decisions BEGIN
    INSERT INTO decisions_fts(rowid, id, decision, context, pattern)
    VALUES (new.rowid, new.id, new.decision, new.context, new.pattern);
END;

CREATE TRIGGER IF NOT EXISTS decisions_ad AFTER DELETE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, id, decision, context, pattern)
    VALUES ('delete', old.rowid, old.id, old.decision, old.context, old.pattern);
END;

CREATE TRIGGER IF NOT EXISTS decisions_au AFTER UPDATE ON decisions BEGIN
    INSERT INTO decisions_fts(decisions_fts, rowid, id, decision, context, pattern)
    VALUES ('delete', old.rowid, old.id, old.decision, old.context, old.pattern);
    INSERT INTO decisions_fts(rowid, id, decision, context, pattern)
    VALUES (new.rowid, new.id, new.decision, new.context, new.pattern);
END;
"""

# Columns allowed in ORDER BY to prevent SQL injection
_SORTABLE_COLUMNS: frozenset[str] = frozenset({
    "id", "decision", "confidence", "category", "stakes",
    "status", "created_at", "updated_at", "recorded_by", "project",
})

# Fields that can be updated via update_fields()
_UPDATABLE_FIELDS: frozenset[str] = frozenset({
    "decision", "confidence", "category", "stakes", "status",
    "context", "recorded_by", "project", "feature", "pr",
    "pattern", "outcome", "outcome_result", "outcome_lessons",
    "outcome_notes", "reviewed_at",
})

# Fields allowed as count()/list() filters
_FILTER_COLUMNS: frozenset[str] = frozenset({
    "category", "stakes", "status", "recorded_by", "project", "feature",
})


def _now() -> str:
    """Return current UTC timestamp as ISO-8601 string."""
    return datetime.now(UTC).isoformat()


def _sanitize_fts_query(term: str) -> str:
    """Sanitize a search term for FTS5 MATCH.

    Strips FTS5 special operators and wraps each word in double quotes
    so the query is treated as a simple phrase/token search.
    """
    # Remove FTS5 special characters
    cleaned = re.sub(r'["\*\(\)\+\-\^]', " ", term)
    words = cleaned.split()
    if not words:
        return '""'
    # Quote each word individually, joined by implicit AND
    return " ".join(f'"{w}"' for w in words)


class SQLiteDecisionStore(DecisionStore):
    """SQLite-backed decision storage with WAL mode and FTS5 search.

    Configuration via environment variables:
        - CSTP_DB_PATH: Path to SQLite database file (default: data/decisions.db)
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = Path(db_path or os.getenv("CSTP_DB_PATH", "data/decisions.db"))
        self._conn: sqlite3.Connection | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Initialize database connection, enable WAL, create schema."""
        await asyncio.to_thread(self._initialize_sync)

    def _initialize_sync(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self._db_path),
            check_same_thread=False,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA_SQL)
        logger.info("SQLiteDecisionStore initialized at %s", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._conn is not None:
            await asyncio.to_thread(self._conn.close)
            self._conn = None

    # ------------------------------------------------------------------
    # save
    # ------------------------------------------------------------------

    async def save(self, decision_id: str, data: dict[str, Any]) -> bool:
        """Insert or update a decision with all related records."""
        return await asyncio.to_thread(self._save_sync, decision_id, data)

    def _save_sync(self, decision_id: str, data: dict[str, Any]) -> bool:
        assert self._conn is not None  # noqa: S101
        now = _now()
        created_at = data.get("created_at") or data.get("date") or now
        updated_at = now

        try:
            with self._conn:
                # Upsert the core decision row
                self._conn.execute(
                    """
                    INSERT INTO decisions (
                        id, decision, confidence, category, stakes, status,
                        context, recorded_by, project, feature, pr, pattern,
                        outcome, outcome_result, outcome_lessons, outcome_notes,
                        reviewed_at, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        decision=excluded.decision,
                        confidence=excluded.confidence,
                        category=excluded.category,
                        stakes=excluded.stakes,
                        status=excluded.status,
                        context=excluded.context,
                        recorded_by=excluded.recorded_by,
                        project=excluded.project,
                        feature=excluded.feature,
                        pr=excluded.pr,
                        pattern=excluded.pattern,
                        outcome=excluded.outcome,
                        outcome_result=excluded.outcome_result,
                        outcome_lessons=excluded.outcome_lessons,
                        outcome_notes=excluded.outcome_notes,
                        reviewed_at=excluded.reviewed_at,
                        updated_at=excluded.updated_at
                    """,
                    (
                        decision_id,
                        data.get("decision", ""),
                        data.get("confidence", 0.0),
                        data.get("category", ""),
                        data.get("stakes", "medium"),
                        data.get("status", "pending"),
                        data.get("context"),
                        data.get("recorded_by") or data.get("agent_id"),
                        data.get("project"),
                        data.get("feature"),
                        data.get("pr"),
                        data.get("pattern"),
                        data.get("outcome"),
                        data.get("outcome_result") or data.get("actual_result"),
                        data.get("outcome_lessons") or data.get("lessons"),
                        data.get("outcome_notes") or data.get("review_notes"),
                        data.get("reviewed_at"),
                        created_at,
                        updated_at,
                    ),
                )

                # --- Tags ---
                self._conn.execute(
                    "DELETE FROM decision_tags WHERE decision_id = ?",
                    (decision_id,),
                )
                tags = data.get("tags") or []
                if tags:
                    self._conn.executemany(
                        "INSERT OR IGNORE INTO decision_tags (decision_id, tag) "
                        "VALUES (?, ?)",
                        [(decision_id, t) for t in tags],
                    )

                # --- Reasons ---
                self._conn.execute(
                    "DELETE FROM decision_reasons WHERE decision_id = ?",
                    (decision_id,),
                )
                reasons = data.get("reasons") or []
                for r in reasons:
                    self._conn.execute(
                        "INSERT INTO decision_reasons "
                        "(decision_id, type, text, strength) VALUES (?, ?, ?, ?)",
                        (
                            decision_id,
                            r.get("type", ""),
                            r.get("text", ""),
                            r.get("strength", 0.8),
                        ),
                    )

                # --- Bridge ---
                self._conn.execute(
                    "DELETE FROM decision_bridge WHERE decision_id = ?",
                    (decision_id,),
                )
                bridge = data.get("bridge")
                if bridge and isinstance(bridge, dict):
                    self._conn.execute(
                        "INSERT INTO decision_bridge "
                        "(decision_id, structure, function, tolerance, "
                        "enforcement, prevention) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            decision_id,
                            bridge.get("structure"),
                            bridge.get("function"),
                            json.dumps(bridge["tolerance"])
                            if bridge.get("tolerance") else None,
                            json.dumps(bridge["enforcement"])
                            if bridge.get("enforcement") else None,
                            json.dumps(bridge["prevention"])
                            if bridge.get("prevention") else None,
                        ),
                    )

                # --- Deliberation ---
                self._conn.execute(
                    "DELETE FROM decision_deliberation WHERE decision_id = ?",
                    (decision_id,),
                )
                delib = data.get("deliberation")
                if delib and isinstance(delib, dict):
                    self._conn.execute(
                        "INSERT INTO decision_deliberation "
                        "(decision_id, inputs_json, steps_json, "
                        "total_duration_ms) VALUES (?, ?, ?, ?)",
                        (
                            decision_id,
                            json.dumps(delib["inputs"])
                            if delib.get("inputs") else None,
                            json.dumps(delib["steps"])
                            if delib.get("steps") else None,
                            delib.get("total_duration_ms"),
                        ),
                    )

            return True
        except Exception:
            logger.exception("Failed to save decision %s", decision_id)
            return False

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_row(d: dict[str, Any]) -> dict[str, Any]:
        """Normalize DB column names to YAML/API convention."""
        if "outcome_result" in d:
            d["actual_result"] = d.pop("outcome_result")
        if "outcome_lessons" in d:
            d["lessons"] = d.pop("outcome_lessons")
        if "outcome_notes" in d:
            d["review_notes"] = d.pop("outcome_notes")
        return d

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    async def get(self, decision_id: str) -> dict[str, Any] | None:
        """Get a decision by ID, joining tags, reasons, bridge, deliberation."""
        return await asyncio.to_thread(self._get_sync, decision_id)

    def _get_sync(self, decision_id: str) -> dict[str, Any] | None:
        assert self._conn is not None  # noqa: S101

        row = self._conn.execute(
            "SELECT * FROM decisions WHERE id = ?", (decision_id,)
        ).fetchone()
        if row is None:
            return None

        result = self._normalize_row(dict(row))

        # Tags
        tag_rows = self._conn.execute(
            "SELECT tag FROM decision_tags WHERE decision_id = ?",
            (decision_id,),
        ).fetchall()
        result["tags"] = [r["tag"] for r in tag_rows]

        # Reasons
        reason_rows = self._conn.execute(
            "SELECT type, text, strength FROM decision_reasons "
            "WHERE decision_id = ? ORDER BY id",
            (decision_id,),
        ).fetchall()
        result["reasons"] = [dict(r) for r in reason_rows]

        # Bridge
        bridge_row = self._conn.execute(
            "SELECT structure, function, tolerance, enforcement, prevention "
            "FROM decision_bridge WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if bridge_row:
            result["bridge"] = {
                "structure": bridge_row["structure"],
                "function": bridge_row["function"],
                "tolerance": json.loads(bridge_row["tolerance"])
                if bridge_row["tolerance"] else None,
                "enforcement": json.loads(bridge_row["enforcement"])
                if bridge_row["enforcement"] else None,
                "prevention": json.loads(bridge_row["prevention"])
                if bridge_row["prevention"] else None,
            }

        # Deliberation
        delib_row = self._conn.execute(
            "SELECT inputs_json, steps_json, total_duration_ms "
            "FROM decision_deliberation WHERE decision_id = ?",
            (decision_id,),
        ).fetchone()
        if delib_row:
            result["deliberation"] = {
                "inputs": json.loads(delib_row["inputs_json"])
                if delib_row["inputs_json"] else None,
                "steps": json.loads(delib_row["steps_json"])
                if delib_row["steps_json"] else None,
                "total_duration_ms": delib_row["total_duration_ms"],
            }

        return result

    # ------------------------------------------------------------------
    # delete
    # ------------------------------------------------------------------

    async def delete(self, decision_id: str) -> bool:
        """Delete a decision and all related records (cascading)."""
        return await asyncio.to_thread(self._delete_sync, decision_id)

    def _delete_sync(self, decision_id: str) -> bool:
        assert self._conn is not None  # noqa: S101
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "DELETE FROM decisions WHERE id = ?", (decision_id,)
                )
                return cursor.rowcount > 0
        except Exception:
            logger.exception("Failed to delete decision %s", decision_id)
            return False

    # ------------------------------------------------------------------
    # list
    # ------------------------------------------------------------------

    async def list(self, query: ListQuery) -> ListResult:
        """List decisions with SQL-based filtering, sorting, and pagination."""
        return await asyncio.to_thread(self._list_sync, query)

    def _list_sync(self, query: ListQuery) -> ListResult:
        assert self._conn is not None  # noqa: S101

        conditions: list[str] = []
        params: list[Any] = []

        if query.category:
            conditions.append("d.category = ?")
            params.append(query.category)
        if query.stakes:
            conditions.append("d.stakes = ?")
            params.append(query.stakes)
        if query.status:
            conditions.append("d.status = ?")
            params.append(query.status)
        if query.agent:
            conditions.append("d.recorded_by = ?")
            params.append(query.agent)
        if query.project:
            conditions.append("d.project = ?")
            params.append(query.project)
        if query.date_from:
            conditions.append("d.created_at >= ?")
            params.append(query.date_from)
        if query.date_to:
            date_to_val = query.date_to
            if "T" not in date_to_val:
                date_to_val += "T23:59:59"
            conditions.append("d.created_at <= ?")
            params.append(date_to_val)
        if query.tags:
            placeholders = ",".join("?" for _ in query.tags)
            conditions.append(
                f"d.id IN (SELECT decision_id FROM decision_tags "
                f"WHERE tag IN ({placeholders}))"
            )
            params.extend(query.tags)
        if query.search:
            sanitized = _sanitize_fts_query(query.search)
            conditions.append(
                "d.id IN (SELECT id FROM decisions_fts "
                "WHERE decisions_fts MATCH ?)"
            )
            params.append(sanitized)

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        # Validate sort column
        sort_col = query.sort if query.sort in _SORTABLE_COLUMNS else "created_at"
        order = "ASC" if query.order.upper() == "ASC" else "DESC"

        # Count total
        count_sql = f"SELECT COUNT(*) FROM decisions d WHERE {where_clause}"  # noqa: S608
        total = self._conn.execute(count_sql, params).fetchone()[0]

        # Fetch page
        select_sql = (
            f"SELECT d.* FROM decisions d WHERE {where_clause} "  # noqa: S608
            f"ORDER BY d.{sort_col} {order} "
            f"LIMIT ? OFFSET ?"
        )
        rows = self._conn.execute(
            select_sql, [*params, query.limit, query.offset]
        ).fetchall()

        decisions: list[dict[str, Any]] = [
            self._normalize_row(dict(row)) for row in rows
        ]

        # Batch-fetch tags for all decisions (avoids N+1 queries)
        ids = [d["id"] for d in decisions]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            tag_rows = self._conn.execute(
                f"SELECT decision_id, tag FROM decision_tags "  # noqa: S608
                f"WHERE decision_id IN ({placeholders})",
                ids,
            ).fetchall()
            tags_by_id: dict[str, list[str]] = defaultdict(list)
            for r in tag_rows:
                tags_by_id[r["decision_id"]].append(r["tag"])
            for d in decisions:
                d["tags"] = tags_by_id.get(d["id"], [])
        else:
            for d in decisions:
                d["tags"] = []

        return ListResult(
            decisions=decisions,
            total=total,
            limit=query.limit,
            offset=query.offset,
        )

    # ------------------------------------------------------------------
    # stats
    # ------------------------------------------------------------------

    async def stats(self, query: StatsQuery) -> StatsResult:
        """Compute aggregate statistics using SQL GROUP BY queries."""
        return await asyncio.to_thread(self._stats_sync, query)

    def _stats_sync(self, query: StatsQuery) -> StatsResult:
        assert self._conn is not None  # noqa: S101

        conditions: list[str] = []
        params: list[Any] = []

        if query.date_from:
            conditions.append("created_at >= ?")
            params.append(query.date_from)
        if query.date_to:
            date_to_val = query.date_to
            if "T" not in date_to_val:
                date_to_val += "T23:59:59"
            conditions.append("created_at <= ?")
            params.append(date_to_val)
        if query.project:
            conditions.append("project = ?")
            params.append(query.project)

        where = " AND ".join(conditions) if conditions else "1=1"

        # Total
        total = self._conn.execute(
            f"SELECT COUNT(*) FROM decisions WHERE {where}",  # noqa: S608
            params,
        ).fetchone()[0]

        # By category
        by_category: dict[str, int] = {}
        for row in self._conn.execute(
            f"SELECT category, COUNT(*) as cnt FROM decisions "  # noqa: S608
            f"WHERE {where} GROUP BY category",
            params,
        ):
            by_category[row["category"]] = row["cnt"]

        # By stakes
        by_stakes: dict[str, int] = {}
        for row in self._conn.execute(
            f"SELECT stakes, COUNT(*) as cnt FROM decisions "  # noqa: S608
            f"WHERE {where} GROUP BY stakes",
            params,
        ):
            by_stakes[row["stakes"]] = row["cnt"]

        # By status
        by_status: dict[str, int] = {}
        for row in self._conn.execute(
            f"SELECT status, COUNT(*) as cnt FROM decisions "  # noqa: S608
            f"WHERE {where} GROUP BY status",
            params,
        ):
            by_status[row["status"]] = row["cnt"]

        # By agent
        by_agent: dict[str, int] = {}
        for row in self._conn.execute(
            f"SELECT recorded_by, COUNT(*) as cnt FROM decisions "  # noqa: S608
            f"WHERE {where} AND recorded_by IS NOT NULL GROUP BY recorded_by",
            params,
        ):
            by_agent[row["recorded_by"]] = row["cnt"]

        # By day
        by_day: list[dict[str, Any]] = []
        for row in self._conn.execute(
            f"SELECT strftime('%Y-%m-%d', created_at) as date, "  # noqa: S608
            f"COUNT(*) as count FROM decisions "
            f"WHERE {where} GROUP BY date ORDER BY date DESC LIMIT 30",
            params,
        ):
            by_day.append({"date": row["date"], "count": row["count"]})

        # Top tags
        top_tags: list[dict[str, Any]] = []
        if conditions:
            tag_sql = (
                f"SELECT t.tag, COUNT(*) as count "  # noqa: S608
                f"FROM decision_tags t "
                f"JOIN decisions d ON t.decision_id = d.id "
                f"WHERE {where} "
                f"GROUP BY t.tag ORDER BY count DESC LIMIT 20"
            )
        else:
            tag_sql = (
                "SELECT tag, COUNT(*) as count FROM decision_tags "
                "GROUP BY tag ORDER BY count DESC LIMIT 20"
            )
        for row in self._conn.execute(tag_sql, params):
            top_tags.append({"tag": row["tag"], "count": row["count"]})

        # Recent activity (respects the same project/date filters)
        recent_activity: dict[str, int] = {}
        for label, interval in [
            ("last24h", "-1 day"),
            ("last7d", "-7 days"),
            ("last30d", "-30 days"),
        ]:
            activity_conditions = list(conditions)
            activity_params = list(params)
            activity_conditions.append("created_at >= datetime('now', ?)")
            activity_params.append(interval)
            activity_where = " AND ".join(activity_conditions)
            row = self._conn.execute(
                f"SELECT COUNT(*) FROM decisions "  # noqa: S608
                f"WHERE {activity_where}",
                activity_params,
            ).fetchone()
            recent_activity[label] = row[0]

        return StatsResult(
            total=total,
            by_category=by_category,
            by_stakes=by_stakes,
            by_status=by_status,
            by_agent=by_agent,
            by_day=by_day,
            top_tags=top_tags,
            recent_activity=recent_activity,
        )

    # ------------------------------------------------------------------
    # update_outcome
    # ------------------------------------------------------------------

    async def update_outcome(
        self,
        decision_id: str,
        outcome: str,
        result: str | None = None,
        lessons: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Update outcome fields and set reviewed_at timestamp."""
        return await asyncio.to_thread(
            self._update_outcome_sync, decision_id, outcome, result, lessons, notes
        )

    def _update_outcome_sync(
        self,
        decision_id: str,
        outcome: str,
        result: str | None,
        lessons: str | None,
        notes: str | None,
    ) -> bool:
        assert self._conn is not None  # noqa: S101
        now = _now()
        try:
            with self._conn:
                cursor = self._conn.execute(
                    "UPDATE decisions SET "
                    "outcome = ?, outcome_result = ?, outcome_lessons = ?, "
                    "outcome_notes = ?, status = 'reviewed', "
                    "reviewed_at = ?, updated_at = ? "
                    "WHERE id = ?",
                    (outcome, result, lessons, notes, now, now, decision_id),
                )
                return cursor.rowcount > 0
        except Exception:
            logger.exception(
                "Failed to update outcome for decision %s", decision_id
            )
            return False

    # ------------------------------------------------------------------
    # update_fields
    # ------------------------------------------------------------------

    async def update_fields(self, decision_id: str, **fields: Any) -> bool:
        """Update specific fields on a decision."""
        return await asyncio.to_thread(
            self._update_fields_sync, decision_id, fields
        )

    def _update_fields_sync(
        self, decision_id: str, fields: dict[str, Any]
    ) -> bool:
        assert self._conn is not None  # noqa: S101

        # Handle child-table fields separately
        tags = fields.pop("tags", None)
        delib = fields.pop("deliberation", None)
        reasons = fields.pop("reasons", None)
        bridge = fields.pop("bridge", None)

        # Filter to allowed columns only
        safe_fields = {
            k: v for k, v in fields.items() if k in _UPDATABLE_FIELDS
        }

        has_child = (
            tags is not None or delib is not None
            or reasons is not None or bridge is not None
        )
        if not safe_fields and not has_child:
            return False

        try:
            with self._conn:
                if safe_fields:
                    safe_fields["updated_at"] = _now()
                    set_clause = ", ".join(f"{k} = ?" for k in safe_fields)
                    values = list(safe_fields.values())
                    values.append(decision_id)
                    cursor = self._conn.execute(
                        f"UPDATE decisions SET {set_clause} WHERE id = ?",  # noqa: S608
                        values,
                    )
                    if cursor.rowcount == 0:
                        return False

                # Verify the decision exists for child-table-only updates
                if not safe_fields and has_child:
                    row = self._conn.execute(
                        "SELECT 1 FROM decisions WHERE id = ?",
                        (decision_id,),
                    ).fetchone()
                    if row is None:
                        return False

                if tags is not None:
                    self._conn.execute(
                        "DELETE FROM decision_tags WHERE decision_id = ?",
                        (decision_id,),
                    )
                    if tags:
                        self._conn.executemany(
                            "INSERT OR IGNORE INTO decision_tags "
                            "(decision_id, tag) VALUES (?, ?)",
                            [(decision_id, t) for t in tags],
                        )

                if delib is not None and isinstance(delib, dict):
                    self._conn.execute(
                        "DELETE FROM decision_deliberation "
                        "WHERE decision_id = ?",
                        (decision_id,),
                    )
                    self._conn.execute(
                        "INSERT INTO decision_deliberation "
                        "(decision_id, inputs_json, steps_json, "
                        "total_duration_ms) VALUES (?, ?, ?, ?)",
                        (
                            decision_id,
                            json.dumps(delib.get("inputs"))
                            if delib.get("inputs") else None,
                            json.dumps(delib.get("steps"))
                            if delib.get("steps") else None,
                            delib.get("total_duration_ms"),
                        ),
                    )

                if reasons is not None:
                    self._conn.execute(
                        "DELETE FROM decision_reasons "
                        "WHERE decision_id = ?",
                        (decision_id,),
                    )
                    for r in reasons:
                        if isinstance(r, dict):
                            self._conn.execute(
                                "INSERT INTO decision_reasons "
                                "(decision_id, type, text, strength) "
                                "VALUES (?, ?, ?, ?)",
                                (
                                    decision_id,
                                    r.get("type", ""),
                                    r.get("text", ""),
                                    r.get("strength", 0.8),
                                ),
                            )

                if bridge is not None:
                    self._conn.execute(
                        "DELETE FROM decision_bridge "
                        "WHERE decision_id = ?",
                        (decision_id,),
                    )
                    if isinstance(bridge, dict) and bridge:
                        self._conn.execute(
                            "INSERT INTO decision_bridge "
                            "(decision_id, structure, function, "
                            "tolerance, enforcement, prevention) "
                            "VALUES (?, ?, ?, ?, ?, ?)",
                            (
                                decision_id,
                                bridge.get("structure"),
                                bridge.get("function"),
                                json.dumps(bridge["tolerance"])
                                if bridge.get("tolerance") else None,
                                json.dumps(bridge["enforcement"])
                                if bridge.get("enforcement") else None,
                                json.dumps(bridge["prevention"])
                                if bridge.get("prevention") else None,
                            ),
                        )

                # Update timestamp when child-table-only changes were made
                if not safe_fields and has_child:
                    self._conn.execute(
                        "UPDATE decisions SET updated_at = ? WHERE id = ?",
                        (_now(), decision_id),
                    )

                return True
        except Exception:
            logger.exception(
                "Failed to update fields for decision %s", decision_id
            )
            return False

    # ------------------------------------------------------------------
    # count
    # ------------------------------------------------------------------

    async def count(self, **filters: Any) -> int:
        """Count decisions matching optional filters."""
        return await asyncio.to_thread(self._count_sync, filters)

    def _count_sync(self, filters: dict[str, Any]) -> int:
        assert self._conn is not None  # noqa: S101

        conditions: list[str] = []
        params: list[Any] = []

        for key, value in filters.items():
            if key in _FILTER_COLUMNS and value is not None:
                conditions.append(f"{key} = ?")
                params.append(value)

        where = " AND ".join(conditions) if conditions else "1=1"
        row = self._conn.execute(
            f"SELECT COUNT(*) FROM decisions WHERE {where}",  # noqa: S608
            params,
        ).fetchone()
        return row[0]
