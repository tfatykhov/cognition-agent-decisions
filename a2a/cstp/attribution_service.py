"""Attribution service for automatic outcome linking.

Provides mechanisms to automatically attribute outcomes to decisions
based on PR stability and file:line matching.
"""

import logging
import os
import tempfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from .decision_service import DECISIONS_PATH

logger = logging.getLogger(__name__)


@dataclass
class AttributionResult:
    """Result of attributing an outcome to a decision."""

    id: str
    outcome: str
    reason: str
    path: str
    updated: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "outcome": self.outcome,
            "reason": self.reason,
            "path": self.path,
            "updated": self.updated,
        }


@dataclass
class AttributeOutcomesRequest:
    """Request to attribute outcomes to decisions."""

    project: str
    since: str | None = None
    stability_days: int = 14
    dry_run: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AttributeOutcomesRequest":
        """Create from dictionary (JSON-RPC params)."""
        project = data.get("project")
        if not project:
            raise ValueError("project is required")

        return cls(
            project=project,
            since=data.get("since"),
            stability_days=data.get("stabilityDays", 14),
            dry_run=data.get("dryRun", False),
        )


@dataclass
class AttributeOutcomesResponse:
    """Response from outcome attribution."""

    processed: int
    attributed: dict[str, int] = field(default_factory=dict)
    decisions: list[AttributionResult] = field(default_factory=list)
    query_time: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "processed": self.processed,
            "attributed": self.attributed,
            "decisions": [d.to_dict() for d in self.decisions],
            "queryTime": self.query_time,
        }


async def find_pending_decisions(
    project: str,
    since: str | None = None,
    decisions_path: str | None = None,
) -> list[tuple[Path, dict[str, Any]]]:
    """Find pending decisions for a project.

    Args:
        project: Project to filter by (owner/repo).
        since: Only decisions after this date.
        decisions_path: Override for decisions directory.

    Returns:
        List of (path, data) tuples for pending decisions.
    """
    base = Path(decisions_path or DECISIONS_PATH)
    results: list[tuple[Path, dict[str, Any]]] = []

    if not base.exists():
        return results

    for yaml_file in base.rglob("*-decision-*.yaml"):
        try:
            with open(yaml_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            # Must be pending
            if data.get("status") != "pending":
                continue

            # Must match project
            if data.get("project") != project:
                continue

            # Check date filter
            if since:
                decision_date = data.get("date", "")
                if isinstance(decision_date, str):
                    date_str = decision_date[:10]
                    if date_str < since:
                        continue

            results.append((yaml_file, data))

        except Exception:
            continue

    return results


def is_pr_stable(
    pr_number: int,
    project: str,
    stability_days: int,
    decision_date: str,
) -> bool:
    """Check if a PR is stable (no bugs reported within stability window).

    This is a simplified check based on decision age.
    A real implementation would query GitHub issues.

    Args:
        pr_number: PR number.
        project: Project identifier.
        stability_days: Days to consider stable.
        decision_date: When the decision was made.

    Returns:
        True if PR is considered stable.
    """
    try:
        # Parse decision date
        if "T" in decision_date:
            dt = datetime.fromisoformat(decision_date.replace("Z", "+00:00"))
        else:
            dt = datetime.strptime(decision_date, "%Y-%m-%d").replace(tzinfo=UTC)

        # Check if enough time has passed
        now = datetime.now(UTC)
        age = now - dt
        return age.days >= stability_days

    except Exception:
        return False


async def update_decision_outcome(
    path: Path,
    outcome: str,
    reason: str,
    dry_run: bool = False,
) -> bool:
    """Update a decision file with outcome.

    Uses atomic write (tempfile + os.replace).

    Args:
        path: Path to decision file.
        outcome: Outcome value (success, partial, failure, abandoned).
        reason: Reason for the attribution.
        dry_run: If True, don't actually write.

    Returns:
        True if updated successfully.
    """
    if dry_run:
        return True

    # Tracked outside the try so the handler knows whether there is anything to
    # undo: any failure after the file has been flipped to `reviewed` must put it
    # back, or the outcome is stranded forever — later attribution runs skip a
    # non-pending file and migration skips a decision whose store row exists.
    original_bytes: bytes | None = None
    yaml_written = False

    try:
        original_bytes = path.read_bytes()

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        data["status"] = "reviewed"
        data["outcome"] = outcome
        data["reviewed_at"] = datetime.now(UTC).isoformat()
        data["auto_attributed"] = True
        data["attribution_reason"] = reason

        # Atomic write
        temp_fd, temp_path = tempfile.mkstemp(suffix=".yaml", dir=path.parent)
        try:
            with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)
            os.replace(temp_path, path)
            yaml_written = True
        except Exception:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # F050: the store is what calibration and listDecisions read, so a YAML-only
        # attribution would never reach a Brier score. This path previously wrote no
        # store record at all.
        decision_id = data.get("id") or path.stem.rsplit("-decision-", 1)[-1]
        from .storage.factory import get_decision_store

        store = get_decision_store()
        if await store.get(decision_id) is None:
            # Not yet migrated. Insert the full record — already carrying the
            # outcome — rather than deferring to the next startup migration.
            # Returning True without it would be the worst of both: the YAML is no
            # longer pending so attribution never revisits it, while list and
            # calibration reads stay blind to the decision until a restart.
            logger.info(
                "Decision %s absent from store; inserting it with the attribution",
                decision_id,
            )
            inserted = await store.save(decision_id, data)
            if inserted is False:
                logger.error(
                    "Decision store rejected insert of %s; rolling back the YAML",
                    decision_id,
                )
                _rollback(path, original_bytes)
                return False
            return True

        updated = await store.update_outcome(
            decision_id=decision_id,
            outcome=outcome,
            result=None,
            lessons=None,
            notes=reason,
        )
        if updated is False:
            logger.error(
                "Decision store rejected auto-attributed outcome for %s; "
                "rolling back the YAML so the attribution can be retried",
                decision_id,
            )
            _rollback(path, original_bytes)
            return False
        return True

    except Exception as e:
        # Covers a raising store as well as a raising write. SQLite surfaces some
        # failures as exceptions rather than a False return, so restoring only on
        # the False path would still strand the outcome.
        logger.warning("Failed to update decision %s: %s", path, e)
        if yaml_written:
            _rollback(path, original_bytes)
        return False


def _rollback(path: Path, original_bytes: bytes | None) -> None:
    """Restore a decision file to its pre-attribution contents."""
    if original_bytes is None:
        return
    try:
        path.write_bytes(original_bytes)
    except Exception as e:  # pragma: no cover - only on a second, disk-level failure
        logger.error(
            "Could not roll back %s after a failed attribution: %s — the file may "
            "now be marked reviewed without a matching store record",
            path,
            e,
        )


async def attribute_outcomes(
    request: AttributeOutcomesRequest,
    decisions_path: str | None = None,
) -> AttributeOutcomesResponse:
    """Attribute outcomes to pending decisions.

    Currently implements PR stability check:
    - If decision has PR and is older than stability_days, mark as success.

    Args:
        request: The attribution request.
        decisions_path: Override for decisions directory.

    Returns:
        Attribution response with results.
    """
    now = datetime.now(UTC)

    # Find pending decisions for project
    pending = await find_pending_decisions(
        project=request.project,
        since=request.since,
        decisions_path=decisions_path,
    )

    results: list[AttributionResult] = []
    counts = {"stable": 0, "skipped": 0}

    for path, data in pending:
        decision_id = data.get("id", "unknown")
        pr_number = data.get("pr")
        decision_date = data.get("date", "")

        # Skip if no PR associated
        if pr_number is None:
            counts["skipped"] += 1
            continue

        # Check PR stability
        if is_pr_stable(pr_number, request.project, request.stability_days, decision_date):
            reason = f"PR #{pr_number} stable for {request.stability_days} days"

            updated = await update_decision_outcome(
                path=path,
                outcome="success",
                reason=reason,
                dry_run=request.dry_run,
            )

            results.append(
                AttributionResult(
                    id=decision_id,
                    outcome="success",
                    reason=reason,
                    path=str(path),
                    updated=updated,
                )
            )
            counts["stable"] += 1
        else:
            counts["skipped"] += 1

    return AttributeOutcomesResponse(
        processed=len(pending),
        attributed=counts,
        decisions=results,
        query_time=now.isoformat(),
    )
