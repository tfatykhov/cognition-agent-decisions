"""
Append-only event store with SHA-256 hash chain for F055 Decision Provenance.

Every event carries an evidence_class (observed | attested) which is included in
the hash preimage, making it tamper-evident. The two classes must never be blended:

  observed  — third-party events from a system the subject does not control
               (GitHub PR opens, commits, reviews, approvals, merges)
  attested  — first-party CSTP records correlated via cstp.linkEvidence

Hash preimage (UTF-8, fields joined by newline):
    {seq}\\n{ts}\\n{event_type}\\n{evidence_class}\\n{canonical_json(payload)}\\n{prev_hash}

Note: `source` is intentionally excluded from the hash preimage. It identifies the
ingest origin but does not affect tamper-evidence.
"""

import hashlib
import json
import os
import sqlite3
from datetime import UTC, datetime
from typing import Optional

DEFAULT_DB_PATH = os.environ.get("PROVENANCE_DB", "provenance.db")

EVIDENCE_CLASS_OBSERVED = "observed"
EVIDENCE_CLASS_ATTESTED = "attested"
_VALID_CLASSES = frozenset({EVIDENCE_CLASS_OBSERVED, EVIDENCE_CLASS_ATTESTED})

CREATE_SCHEMA_SQL = """
PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS events (
    seq            INTEGER PRIMARY KEY AUTOINCREMENT,
    ts             TEXT NOT NULL,
    source         TEXT NOT NULL,
    event_type     TEXT NOT NULL,
    evidence_class TEXT NOT NULL CHECK(evidence_class IN ('observed', 'attested')),
    payload_json   TEXT NOT NULL,
    prev_hash      TEXT NOT NULL,
    hash           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bundle_metadata (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    generated_at TEXT NOT NULL,
    head_hash    TEXT NOT NULL,
    format       TEXT NOT NULL
);
"""


def canonical_json(obj: dict) -> str:
    """Canonical JSON: sorted keys, no whitespace, UTF-8-safe."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_hash(
    seq: int,
    ts: str,
    event_type: str,
    evidence_class: str,
    payload: dict,
    prev_hash: str,
) -> str:
    """Compute SHA-256 hash for an event record.

    Preimage (UTF-8):
        "{seq}\\n{ts}\\n{event_type}\\n{evidence_class}\\n{canonical_json(payload)}\\n{prev_hash}"
    """
    preimage = (
        f"{seq}\n{ts}\n{event_type}\n{evidence_class}\n"
        f"{canonical_json(payload)}\n{prev_hash}"
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create tables if they do not exist. Safe to call multiple times."""
    with sqlite3.connect(db_path) as conn:
        conn.executescript(CREATE_SCHEMA_SQL)
        conn.commit()


def append_event(
    source: str,
    event_type: str,
    evidence_class: str,
    payload: dict,
    ts: str | None = None,
    db_path: str = DEFAULT_DB_PATH,
) -> tuple[int, str]:
    """Append an event to the chain. Returns (seq, hash).

    evidence_class must be 'observed' or 'attested'. Enforced both here
    and by a DB CHECK constraint.

    ts should be an ISO 8601 string from the source data to ensure chain
    determinism across re-runs. Defaults to current UTC time if omitted.
    """
    if evidence_class not in _VALID_CLASSES:
        raise ValueError(
            f"evidence_class must be 'observed' or 'attested', got: {evidence_class!r}"
        )
    if ts is None:
        ts = datetime.now(UTC).isoformat()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT seq, hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()

        prev_hash = row["hash"] if row else ""
        next_seq = (row["seq"] + 1) if row else 1

        h = compute_hash(next_seq, ts, event_type, evidence_class, payload, prev_hash)

        conn.execute(
            "INSERT INTO events "
            "(ts, source, event_type, evidence_class, payload_json, prev_hash, hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ts, source, event_type, evidence_class, canonical_json(payload), prev_hash, h),
        )
        conn.commit()
        return next_seq, h


def get_events(
    db_path: str = DEFAULT_DB_PATH,
    evidence_class: str | None = None,
) -> list[dict]:
    """Return events in seq order as dicts. Optionally filter by evidence_class."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if evidence_class is not None:
            rows = conn.execute(
                "SELECT seq, ts, source, event_type, evidence_class, payload_json, prev_hash, hash "
                "FROM events WHERE evidence_class = ? ORDER BY seq",
                (evidence_class,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT seq, ts, source, event_type, evidence_class, payload_json, prev_hash, hash "
                "FROM events ORDER BY seq"
            ).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        d["payload"] = json.loads(d["payload_json"])
        result.append(d)
    return result


def get_head_hash(db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    """Return the hash of the most recent event, or None if the store is empty."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT hash FROM events ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None


def verify_chain(
    db_path: str = DEFAULT_DB_PATH,
    expected_head_hash: Optional[str] = None,
) -> Optional[int]:
    """Walk the entire chain and verify each event's hash.

    Returns the seq of the first broken record, or None if the chain is intact.
    Returns 0 if the chain is internally intact but its head hash does not match
    expected_head_hash — indicating tail truncation (deleted events at the end).
    Callers that omit expected_head_hash see behaviour identical to pre-P1 code.
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT seq, ts, event_type, evidence_class, payload_json, prev_hash, hash "
            "FROM events ORDER BY seq"
        ).fetchall()

    prev_hash = ""
    actual_head_hash = None
    for row in rows:
        payload = json.loads(row["payload_json"])
        expected = compute_hash(
            row["seq"], row["ts"], row["event_type"],
            row["evidence_class"], payload, prev_hash,
        )
        if expected != row["hash"]:
            return row["seq"]
        if row["prev_hash"] != prev_hash:
            return row["seq"]
        prev_hash = row["hash"]
        actual_head_hash = row["hash"]

    if expected_head_hash is not None and actual_head_hash != expected_head_hash:
        return 0  # Tail truncated: chain internally valid but head doesn't match

    return None


def event_count(db_path: str = DEFAULT_DB_PATH) -> int:
    """Return total number of events in the store."""
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]


def store_bundle_head_hash(
    head_hash: str,
    fmt: str,
    db_path: str = DEFAULT_DB_PATH,
) -> None:
    """Persist the head hash at bundle generation time for future verification (P2 fix)."""
    generated_at = datetime.now(UTC).isoformat()
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO bundle_metadata (generated_at, head_hash, format) VALUES (?, ?, ?)",
            (generated_at, head_hash, fmt),
        )
        conn.commit()


def get_last_bundle_head_hash(db_path: str = DEFAULT_DB_PATH) -> Optional[str]:
    """Return the head hash from the most recent bundle generation, or None."""
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT head_hash FROM bundle_metadata ORDER BY id DESC LIMIT 1"
        ).fetchone()
    return row[0] if row else None
