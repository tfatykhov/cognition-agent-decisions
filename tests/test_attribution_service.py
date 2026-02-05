"""Unit tests for attribution_service.py."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml

from a2a.cstp.attribution_service import (
    AttributeOutcomesRequest,
    attribute_outcomes,
    find_pending_decisions,
    is_pr_stable,
    update_decision_outcome,
)


def create_pending_decision(
    tmp_path: Path,
    decision_id: str,
    project: str,
    pr: int | None = None,
    days_old: int = 0,
) -> Path:
    """Helper to create a pending decision file."""
    year_dir = tmp_path / "2026" / "02"
    year_dir.mkdir(parents=True, exist_ok=True)

    decision_date = datetime.now(UTC) - timedelta(days=days_old)

    data = {
        "id": decision_id,
        "summary": f"Test decision {decision_id}",
        "category": "code-review",
        "confidence": 0.85,
        "status": "pending",
        "date": decision_date.isoformat(),
        "project": project,
    }

    if pr is not None:
        data["pr"] = pr

    file_path = year_dir / f"2026-02-05-decision-{decision_id}.yaml"
    with open(file_path, "w") as f:
        yaml.dump(data, f)

    return file_path


class TestAttributeOutcomesRequest:
    """Tests for AttributeOutcomesRequest."""

    def test_from_dict_valid(self) -> None:
        """Parses valid request."""
        data = {
            "project": "owner/repo",
            "since": "2026-01-01",
            "stabilityDays": 7,
            "dryRun": True,
        }
        req = AttributeOutcomesRequest.from_dict(data)

        assert req.project == "owner/repo"
        assert req.since == "2026-01-01"
        assert req.stability_days == 7
        assert req.dry_run is True

    def test_from_dict_missing_project_raises(self) -> None:
        """Missing project raises ValueError."""
        with pytest.raises(ValueError, match="project is required"):
            AttributeOutcomesRequest.from_dict({})

    def test_defaults(self) -> None:
        """Default values are applied."""
        data = {"project": "owner/repo"}
        req = AttributeOutcomesRequest.from_dict(data)

        assert req.stability_days == 14
        assert req.dry_run is False
        assert req.since is None


class TestFindPendingDecisions:
    """Tests for find_pending_decisions."""

    @pytest.mark.asyncio
    async def test_finds_pending_for_project(self, tmp_path: Path) -> None:
        """Finds pending decisions for project."""
        create_pending_decision(tmp_path, "dec1", "owner/repo", pr=1)
        create_pending_decision(tmp_path, "dec2", "owner/repo", pr=2)
        create_pending_decision(tmp_path, "dec3", "other/repo", pr=3)

        results = await find_pending_decisions(
            project="owner/repo",
            decisions_path=str(tmp_path),
        )

        assert len(results) == 2
        ids = [data["id"] for _, data in results]
        assert "dec1" in ids
        assert "dec2" in ids
        assert "dec3" not in ids

    @pytest.mark.asyncio
    async def test_skips_reviewed(self, tmp_path: Path) -> None:
        """Skips reviewed decisions."""
        path = create_pending_decision(tmp_path, "dec1", "owner/repo", pr=1)

        # Mark as reviewed
        with open(path) as f:
            data = yaml.safe_load(f)
        data["status"] = "reviewed"
        with open(path, "w") as f:
            yaml.dump(data, f)

        results = await find_pending_decisions(
            project="owner/repo",
            decisions_path=str(tmp_path),
        )

        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_empty_when_no_match(self, tmp_path: Path) -> None:
        """Returns empty when no matching project."""
        create_pending_decision(tmp_path, "dec1", "other/repo", pr=1)

        results = await find_pending_decisions(
            project="owner/repo",
            decisions_path=str(tmp_path),
        )

        assert len(results) == 0


class TestIsPrStable:
    """Tests for is_pr_stable."""

    def test_stable_when_old_enough(self) -> None:
        """Returns True when decision is old enough."""
        old_date = (datetime.now(UTC) - timedelta(days=20)).isoformat()

        result = is_pr_stable(
            pr_number=1,
            project="owner/repo",
            stability_days=14,
            decision_date=old_date,
        )

        assert result is True

    def test_not_stable_when_too_recent(self) -> None:
        """Returns False when decision is too recent."""
        recent_date = (datetime.now(UTC) - timedelta(days=5)).isoformat()

        result = is_pr_stable(
            pr_number=1,
            project="owner/repo",
            stability_days=14,
            decision_date=recent_date,
        )

        assert result is False

    def test_handles_date_only_format(self) -> None:
        """Handles YYYY-MM-DD format."""
        old_date = (datetime.now(UTC) - timedelta(days=20)).strftime("%Y-%m-%d")

        result = is_pr_stable(
            pr_number=1,
            project="owner/repo",
            stability_days=14,
            decision_date=old_date,
        )

        assert result is True


class TestUpdateDecisionOutcome:
    """Tests for update_decision_outcome."""

    @pytest.mark.asyncio
    async def test_updates_decision_file(self, tmp_path: Path) -> None:
        """Updates decision file with outcome."""
        path = create_pending_decision(tmp_path, "dec1", "owner/repo", pr=1)

        result = await update_decision_outcome(
            path=path,
            outcome="success",
            reason="PR stable",
            dry_run=False,
        )

        assert result is True

        # Verify file was updated
        with open(path) as f:
            data = yaml.safe_load(f)

        assert data["status"] == "reviewed"
        assert data["outcome"] == "success"
        assert data["auto_attributed"] is True
        assert data["attribution_reason"] == "PR stable"

    @pytest.mark.asyncio
    async def test_dry_run_doesnt_write(self, tmp_path: Path) -> None:
        """Dry run doesn't modify file."""
        path = create_pending_decision(tmp_path, "dec1", "owner/repo", pr=1)

        result = await update_decision_outcome(
            path=path,
            outcome="success",
            reason="PR stable",
            dry_run=True,
        )

        assert result is True

        # Verify file was NOT updated
        with open(path) as f:
            data = yaml.safe_load(f)

        assert data["status"] == "pending"
        assert "outcome" not in data


class TestAttributeOutcomes:
    """Integration tests for attribute_outcomes."""

    @pytest.mark.asyncio
    async def test_attributes_stable_prs(self, tmp_path: Path) -> None:
        """Attributes success to stable PRs."""
        # Old decision (should be attributed)
        create_pending_decision(tmp_path, "old1", "owner/repo", pr=1, days_old=20)
        # Recent decision (should be skipped)
        create_pending_decision(tmp_path, "new1", "owner/repo", pr=2, days_old=5)

        request = AttributeOutcomesRequest(
            project="owner/repo",
            stability_days=14,
        )
        response = await attribute_outcomes(request, decisions_path=str(tmp_path))

        assert response.processed == 2
        assert response.attributed["stable"] == 1
        assert response.attributed["skipped"] == 1
        assert len(response.decisions) == 1
        assert response.decisions[0].id == "old1"
        assert response.decisions[0].outcome == "success"

    @pytest.mark.asyncio
    async def test_skips_decisions_without_pr(self, tmp_path: Path) -> None:
        """Skips decisions without PR number."""
        create_pending_decision(tmp_path, "no-pr", "owner/repo", pr=None, days_old=20)

        request = AttributeOutcomesRequest(project="owner/repo")
        response = await attribute_outcomes(request, decisions_path=str(tmp_path))

        assert response.processed == 1
        assert response.attributed["skipped"] == 1
        assert len(response.decisions) == 0

    @pytest.mark.asyncio
    async def test_dry_run_doesnt_modify(self, tmp_path: Path) -> None:
        """Dry run reports but doesn't modify."""
        path = create_pending_decision(tmp_path, "dec1", "owner/repo", pr=1, days_old=20)

        request = AttributeOutcomesRequest(
            project="owner/repo",
            dry_run=True,
        )
        response = await attribute_outcomes(request, decisions_path=str(tmp_path))

        assert response.attributed["stable"] == 1
        assert len(response.decisions) == 1

        # Verify file was NOT modified
        with open(path) as f:
            data = yaml.safe_load(f)
        assert data["status"] == "pending"
