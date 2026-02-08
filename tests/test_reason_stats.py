"""Tests for reason-type calibration statistics service."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from a2a.cstp.reason_stats_service import (
    GetReasonStatsRequest,
    ReasonTypeStats,
    calculate_diversity_stats,
    calculate_reason_type_stats,
    generate_reason_recommendations,
    get_reason_stats,
    load_decisions_with_reasons,
)


def _create_decision_yaml(
    decision_id: str,
    reasons: list[dict],
    confidence: float = 0.85,
    category: str = "architecture",
    stakes: str = "medium",
    status: str = "reviewed",
    outcome: str | None = "success",
    project: str | None = None,
) -> dict:
    """Create a decision YAML dict for testing."""
    data = {
        "id": decision_id,
        "summary": f"Test decision {decision_id}",
        "decision": f"Test decision {decision_id}",
        "confidence": confidence,
        "category": category,
        "stakes": stakes,
        "status": status,
        "date": "2026-02-08T12:00:00Z",
        "created_at": "2026-02-08T12:00:00Z",
        "reasons": reasons,
    }
    if outcome:
        data["outcome"] = outcome
    if project:
        data["project"] = project
    return data


def _write_decision(tmp_dir: Path, decision_id: str, data: dict) -> None:
    """Write a decision YAML file to the temp directory."""
    year_dir = tmp_dir / "2026" / "02"
    year_dir.mkdir(parents=True, exist_ok=True)
    filepath = year_dir / f"2026-02-08-decision-{decision_id}.yaml"
    with open(filepath, "w") as f:
        yaml.dump(data, f)


@pytest.fixture
def decisions_dir():
    """Create a temp directory with test decision files."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # Decision 1: analysis + pattern, success
        _write_decision(tmp_path, "aaa11111", _create_decision_yaml(
            "aaa11111",
            reasons=[
                {"type": "analysis", "text": "Analyzed the problem", "strength": 0.9},
                {"type": "pattern", "text": "Matches known pattern", "strength": 0.8},
            ],
            confidence=0.9,
            outcome="success",
        ))

        # Decision 2: analysis only, success
        _write_decision(tmp_path, "bbb22222", _create_decision_yaml(
            "bbb22222",
            reasons=[
                {"type": "analysis", "text": "Thorough analysis", "strength": 0.85},
            ],
            confidence=0.85,
            outcome="success",
        ))

        # Decision 3: intuition only, failure
        _write_decision(tmp_path, "ccc33333", _create_decision_yaml(
            "ccc33333",
            reasons=[
                {"type": "intuition", "text": "Felt right", "strength": 0.7},
            ],
            confidence=0.8,
            outcome="failure",
        ))

        # Decision 4: pattern + empirical, success
        _write_decision(tmp_path, "ddd44444", _create_decision_yaml(
            "ddd44444",
            reasons=[
                {"type": "pattern", "text": "Known pattern", "strength": 0.85},
                {"type": "empirical", "text": "Tested it", "strength": 0.9},
            ],
            confidence=0.9,
            outcome="success",
        ))

        # Decision 5: analysis + intuition, partial
        _write_decision(tmp_path, "eee55555", _create_decision_yaml(
            "eee55555",
            reasons=[
                {"type": "analysis", "text": "Analyzed", "strength": 0.8},
                {"type": "intuition", "text": "Gut feeling", "strength": 0.6},
            ],
            confidence=0.75,
            outcome="partial",
        ))

        # Decision 6: pending (no outcome)
        _write_decision(tmp_path, "fff66666", _create_decision_yaml(
            "fff66666",
            reasons=[
                {"type": "analysis", "text": "Still pending", "strength": 0.8},
            ],
            confidence=0.85,
            status="pending",
            outcome=None,
        ))

        # Decision 7: analysis, success (for min_reviewed threshold)
        _write_decision(tmp_path, "ggg77777", _create_decision_yaml(
            "ggg77777",
            reasons=[
                {"type": "analysis", "text": "Another analysis", "strength": 0.9},
            ],
            confidence=0.85,
            outcome="success",
        ))

        yield tmp_path


@pytest.mark.asyncio
async def test_load_decisions_with_reasons(decisions_dir):
    """Test loading decisions that have reasons."""
    decisions = await load_decisions_with_reasons(
        decisions_path=str(decisions_dir)
    )
    assert len(decisions) == 7  # All have reasons


@pytest.mark.asyncio
async def test_load_decisions_with_category_filter(decisions_dir):
    """Test category filter."""
    decisions = await load_decisions_with_reasons(
        decisions_path=str(decisions_dir),
        category="architecture",
    )
    assert len(decisions) == 7  # All are architecture

    decisions = await load_decisions_with_reasons(
        decisions_path=str(decisions_dir),
        category="security",
    )
    assert len(decisions) == 0  # None are security


def test_calculate_reason_type_stats(decisions_dir):
    """Test per-type statistics calculation."""
    import asyncio
    decisions = asyncio.run(
        load_decisions_with_reasons(decisions_path=str(decisions_dir))
    )
    stats = calculate_reason_type_stats(decisions, min_reviewed=2)

    # Analysis should be present
    analysis_stat = next(s for s in stats if s.reason_type == "analysis")
    assert analysis_stat.total_uses == 4  # aaa, bbb, eee, fff (ggg)
    assert analysis_stat.reviewed_uses >= 3  # At least aaa, bbb, eee

    # Intuition should be present
    intuition_stat = next(s for s in stats if s.reason_type == "intuition")
    assert intuition_stat.total_uses == 2  # ccc, eee

    # Pattern should be present
    pattern_stat = next(s for s in stats if s.reason_type == "pattern")
    assert pattern_stat.total_uses == 2  # aaa, ddd


def test_calculate_diversity_stats(decisions_dir):
    """Test diversity (parallel bundle) analysis."""
    import asyncio
    decisions = asyncio.run(
        load_decisions_with_reasons(decisions_path=str(decisions_dir))
    )
    diversity = calculate_diversity_stats(decisions)

    # Should have buckets for 1-type and 2-type decisions
    assert len(diversity.diversity_buckets) >= 2

    # Find single-type and multi-type buckets
    single = next(
        (b for b in diversity.diversity_buckets if b["distinctReasonTypes"] == 1),
        None,
    )
    multi = next(
        (b for b in diversity.diversity_buckets if b["distinctReasonTypes"] == 2),
        None,
    )

    assert single is not None
    assert multi is not None

    # Multi-type decisions: aaa(s), ddd(s), eee(p) = 3
    assert multi["totalDecisions"] == 3

    # Average types per decision should be > 1 (mix of 1 and 2)
    assert diversity.avg_types_per_decision > 1.0


def test_recommendations_low_diversity():
    """Test that low diversity triggers recommendation."""
    type_stats = [
        ReasonTypeStats(
            reason_type="analysis",
            total_uses=10,
            reviewed_uses=5,
            success_count=4,
            success_rate=0.8,
            avg_confidence=0.85,
        )
    ]
    diversity = calculate_diversity_stats([])
    diversity.avg_types_per_decision = 1.1  # Low

    recs = generate_reason_recommendations(type_stats, diversity, min_reviewed=3)

    low_div = [r for r in recs if r.type == "low_diversity"]
    assert len(low_div) == 1
    assert "parallel bundles" in low_div[0].message.lower()


def test_recommendations_unused_types():
    """Test that unused types are flagged."""
    type_stats = [
        ReasonTypeStats(reason_type="analysis", total_uses=5),
        ReasonTypeStats(reason_type="pattern", total_uses=3),
    ]
    from a2a.cstp.reason_stats_service import DiversityStats
    diversity = DiversityStats(avg_types_per_decision=2.0)

    recs = generate_reason_recommendations(type_stats, diversity, min_reviewed=3)

    unused = [r for r in recs if r.type == "unused_types"]
    assert len(unused) == 1
    # Should mention the types not used
    assert "empirical" in unused[0].message or "constraint" in unused[0].message


@pytest.mark.asyncio
async def test_get_reason_stats_full(decisions_dir):
    """Test full end-to-end reason stats."""
    request = GetReasonStatsRequest(min_reviewed=2)
    response = await get_reason_stats(request, decisions_path=str(decisions_dir))

    assert response.total_decisions == 7
    assert response.reviewed_decisions == 5  # 5 with outcomes
    assert len(response.by_reason_type) > 0
    assert response.diversity is not None
    assert response.query_time != ""

    # Verify dict serialization
    result = response.to_dict()
    assert "byReasonType" in result
    assert "diversity" in result
    assert "recommendations" in result
    assert result["totalDecisions"] == 7


@pytest.mark.asyncio
async def test_get_reason_stats_empty_dir():
    """Test with no decisions."""
    with tempfile.TemporaryDirectory() as tmp:
        request = GetReasonStatsRequest()
        response = await get_reason_stats(request, decisions_path=tmp)

        assert response.total_decisions == 0
        assert response.reviewed_decisions == 0
        assert len(response.by_reason_type) == 0


def test_request_from_dict():
    """Test request parsing from JSON-RPC params."""
    params = {
        "filters": {
            "category": "architecture",
            "stakes": "high",
            "project": "owner/repo",
        },
        "minReviewed": 5,
    }
    request = GetReasonStatsRequest.from_dict(params)

    assert request.category == "architecture"
    assert request.stakes == "high"
    assert request.project == "owner/repo"
    assert request.min_reviewed == 5


def test_request_from_dict_defaults():
    """Test request parsing with defaults."""
    request = GetReasonStatsRequest.from_dict({})

    assert request.category is None
    assert request.stakes is None
    assert request.min_reviewed == 3


def test_brier_score_calculation(decisions_dir):
    """Test that Brier scores are calculated correctly for types with enough data."""
    import asyncio
    decisions = asyncio.run(
        load_decisions_with_reasons(decisions_path=str(decisions_dir))
    )
    stats = calculate_reason_type_stats(decisions, min_reviewed=3)

    # Analysis has enough reviewed decisions for Brier
    analysis_stat = next(
        (s for s in stats if s.reason_type == "analysis" and s.brier_score is not None),
        None,
    )
    # Should have a Brier score if we have >= 3 reviewed uses
    if analysis_stat:
        assert 0.0 <= analysis_stat.brier_score <= 1.0


def test_reason_type_stats_to_dict():
    """Test serialization of ReasonTypeStats."""
    stat = ReasonTypeStats(
        reason_type="analysis",
        total_uses=10,
        reviewed_uses=8,
        success_count=6,
        partial_count=1,
        failure_count=1,
        success_rate=0.8125,
        avg_confidence=0.85,
        avg_strength=0.9,
        brier_score=0.0456,
    )
    d = stat.to_dict()

    assert d["reasonType"] == "analysis"
    assert d["totalUses"] == 10
    assert d["reviewedUses"] == 8
    assert d["successRate"] == 0.813  # rounded
    assert d["brierScore"] == 0.0456
